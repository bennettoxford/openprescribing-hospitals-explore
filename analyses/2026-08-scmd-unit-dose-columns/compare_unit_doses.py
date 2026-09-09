from pathlib import Path

import polars as pl
from fetch_data import TARGET as PROVISIONAL_CSV
from fetch_oph_data import OUTPUT_CSV as VMP_CSV
from fetch_oph_data import VMP_FETCH_SCHEMA

OUTPUT_CSV = Path(__file__).resolve().parent / "data" / "unit_dose_comparison.csv"

STATUS_AGREE = "agree"
STATUS_DISAGREE = "disagree"
STATUS_MISSING_FROM_VMP_DATA = "missing_from_vmp_data"
STATUS_VMP_UDFS_UOM_MISSING = "vmp_udfs_uom_missing"
STATUS_PROVISIONAL_UDFS_UOM_MISSING = "provisional_udfs_uom_missing"
STATUS_VMP_UDFS_MISSING = "vmp_udfs_missing"
STATUS_PROVISIONAL_UDFS_MISSING = "provisional_udfs_missing"
STATUS_VMP_UNIT_DOSE_UOM_MISSING = "vmp_unit_dose_uom_missing"
STATUS_PROVISIONAL_UNIT_DOSE_UOM_MISSING = "provisional_unit_dose_uom_missing"

UDFS_REL_TOL = 1e-3

UOM_COLUMNS = ("provisional_udfs_uom", "provisional_unit_dose_uom")


def check_uom_consistency(rows: pl.DataFrame) -> None:
    """Stop with an error when one VMP reports more than one unit of measure."""
    for column in UOM_COLUMNS:
        inconsistent = (
            rows.group_by("vmp_code")
            .agg(pl.col(column).drop_nulls().n_unique().alias("n_uoms"))
            .filter(pl.col("n_uoms") > 1)
        )
        if inconsistent.height:
            codes = ", ".join(sorted(inconsistent.get_column("vmp_code").to_list()))
            raise ValueError(
                f"VMPs with more than one {column} value in the provisional "
                f"extract: {codes}"
            )


def implied_udfs_expr() -> pl.Expr:
    quantity_udfs = pl.col("quantity_udfs")
    quantity_unit_dose = pl.col("quantity_unit_dose")
    return (
        pl.when(
            quantity_udfs.is_not_null()
            & quantity_unit_dose.is_not_null()
            & (quantity_unit_dose != 0)
        )
        .then(quantity_udfs / quantity_unit_dose)
        .otherwise(None)
    )


def udfs_consistent_expr() -> pl.Expr:
    n_values = pl.col("provisional_udfs_n")
    udfs_min = pl.col("provisional_udfs_min")
    udfs_max = pl.col("provisional_udfs_max")
    scale = pl.max_horizontal(udfs_min.abs(), udfs_max.abs(), pl.lit(1e-12))
    close = (udfs_max - udfs_min).abs() <= (UDFS_REL_TOL * scale)
    return pl.when(n_values <= 1).then(pl.lit(True)).otherwise(close.fill_null(False))


def load_provisional_vmps(csv_path: Path) -> pl.DataFrame:
    """Return one row per VMP with its provisional UDFS unit and value."""
    rows = (
        pl.read_csv(
            csv_path,
            columns=[
                "VMP_SNOMED_CODE",
                "VMP_PRODUCT_NAME",
                "VMP_UDFS_UNIT_OF_MEASURE_NAME",
                "VMP_UNIT_DOSE_UNIT_OF_MEASURE_NAME",
                "TOTAL_QUANTITY_IN_VMP_UDFS_UNIT_OF_MEASURE",
                "TOTAL_QUANTITY_IN_VMP_UNIT_DOSE_UNIT_OF_MEASURE",
            ],
        )
        .rename(
            {
                "VMP_SNOMED_CODE": "vmp_code",
                "VMP_PRODUCT_NAME": "vmp_product_name",
                "VMP_UDFS_UNIT_OF_MEASURE_NAME": "provisional_udfs_uom",
                "VMP_UNIT_DOSE_UNIT_OF_MEASURE_NAME": ("provisional_unit_dose_uom"),
                "TOTAL_QUANTITY_IN_VMP_UDFS_UNIT_OF_MEASURE": "quantity_udfs",
                "TOTAL_QUANTITY_IN_VMP_UNIT_DOSE_UNIT_OF_MEASURE": (
                    "quantity_unit_dose"
                ),
            }
        )
        .drop_nulls("vmp_code")
        .with_columns(pl.col("vmp_code").cast(pl.String))
        .with_columns(implied_udfs_expr().alias("provisional_udfs"))
    )
    check_uom_consistency(rows)
    return (
        rows.group_by("vmp_code")
        .agg(
            pl.col("vmp_product_name").drop_nulls().first(),
            pl.col("provisional_udfs_uom").drop_nulls().first(),
            pl.col("provisional_unit_dose_uom").drop_nulls().first(),
            pl.col("provisional_udfs").drop_nulls().first().alias("provisional_udfs"),
            pl.col("provisional_udfs").drop_nulls().min().alias("provisional_udfs_min"),
            pl.col("provisional_udfs").drop_nulls().max().alias("provisional_udfs_max"),
            pl.col("provisional_udfs").drop_nulls().len().alias("provisional_udfs_n"),
        )
        .with_columns(udfs_consistent_expr().alias("provisional_udfs_consistent"))
        .drop("provisional_udfs_n")
    )


def load_vmp_rows(csv_path: Path) -> pl.DataFrame:
    """Read the VMP rows saved by fetch_oph_data.py."""
    return pl.read_csv(csv_path, schema_overrides=VMP_FETCH_SCHEMA)


def normalised_uom_expr(column: str) -> pl.Expr:
    stripped = pl.col(column).str.strip_chars()
    return (
        pl.when(stripped.is_null() | (stripped == ""))
        .then(None)
        .otherwise(stripped.str.to_lowercase())
    )


def numeric_match_expr(left: str, right: str) -> pl.Expr:
    scale = pl.max_horizontal(pl.col(left).abs(), pl.col(right).abs(), pl.lit(1e-12))
    close = (pl.col(left) - pl.col(right)).abs() <= (UDFS_REL_TOL * scale)
    return pl.col(left).eq_missing(pl.col(right)) | close.fill_null(False)


def classify_status(
    *,
    left: str,
    right: str,
    match: pl.Expr,
    missing_vmp: str,
    missing_provisional: str,
) -> pl.Expr:
    return (
        pl.when(~pl.col("in_vmp_data").fill_null(False))
        .then(pl.lit(STATUS_MISSING_FROM_VMP_DATA))
        .when(match)
        .then(pl.lit(STATUS_AGREE))
        .when(pl.col(left).is_not_null() & pl.col(right).is_null())
        .then(pl.lit(missing_vmp))
        .when(pl.col(left).is_null() & pl.col(right).is_not_null())
        .then(pl.lit(missing_provisional))
        .otherwise(pl.lit(STATUS_DISAGREE))
    )


def compare_unit_doses(provisional: pl.DataFrame, vmp: pl.DataFrame) -> pl.DataFrame:
    """Compare provisional UDFS and unit dose units with vmp_data for each VMP."""
    vmp_marked = vmp.with_columns(pl.lit(True).alias("in_vmp_data"))
    joined = provisional.join(vmp_marked, on="vmp_code", how="left")
    return joined.with_columns(
        normalised_uom_expr("provisional_udfs_uom").alias("provisional_udfs_uom_norm"),
        normalised_uom_expr("provisional_unit_dose_uom").alias(
            "provisional_unit_dose_uom_norm"
        ),
        normalised_uom_expr("udfs_uom").alias("vmp_udfs_uom_norm"),
        normalised_uom_expr("unit_dose_uom").alias("vmp_unit_dose_uom_norm"),
    ).with_columns(
        (
            pl.col("provisional_udfs_uom_norm").is_not_null()
            & pl.col("provisional_unit_dose_uom_norm").is_not_null()
            & (
                pl.col("provisional_udfs_uom_norm")
                == pl.col("provisional_unit_dose_uom_norm")
            )
        ).alias("provisional_units_match"),
        classify_status(
            left="provisional_udfs_uom_norm",
            right="vmp_udfs_uom_norm",
            match=pl.col("provisional_udfs_uom_norm").eq_missing(
                pl.col("vmp_udfs_uom_norm")
            ),
            missing_vmp=STATUS_VMP_UDFS_UOM_MISSING,
            missing_provisional=STATUS_PROVISIONAL_UDFS_UOM_MISSING,
        ).alias("status"),
        classify_status(
            left="provisional_udfs",
            right="udfs",
            match=numeric_match_expr("provisional_udfs", "udfs"),
            missing_vmp=STATUS_VMP_UDFS_MISSING,
            missing_provisional=STATUS_PROVISIONAL_UDFS_MISSING,
        ).alias("udfs_status"),
        classify_status(
            left="provisional_unit_dose_uom_norm",
            right="vmp_unit_dose_uom_norm",
            match=pl.col("provisional_unit_dose_uom_norm").eq_missing(
                pl.col("vmp_unit_dose_uom_norm")
            ),
            missing_vmp=STATUS_VMP_UNIT_DOSE_UOM_MISSING,
            missing_provisional=STATUS_PROVISIONAL_UNIT_DOSE_UOM_MISSING,
        ).alias("unit_dose_uom_status"),
    )


def main() -> pl.DataFrame:
    provisional = load_provisional_vmps(PROVISIONAL_CSV)
    vmp = load_vmp_rows(VMP_CSV)
    comparison = compare_unit_doses(provisional, vmp)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    comparison.write_csv(OUTPUT_CSV)
    return comparison


if __name__ == "__main__":
    main()
