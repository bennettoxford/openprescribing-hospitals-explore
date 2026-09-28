"""Build the dm+d VMP list for the UK AWaRe categories.

The category list and form rules are local CSV files. VTM rows and VMP rows
come from a local CSV when that file exists. The script queries BigQuery and
writes the CSV when the file is missing. The script writes one CSV for the
final VMP list.
"""

import argparse
from pathlib import Path

import polars as pl

from oph_utils.bigquery import query_to_polars

ANALYSIS_DIR = Path(__file__).resolve().parent
CATEGORIES_PATH = ANALYSIS_DIR / "aware_categories.csv"
EXCLUDED_FORMS_PATH = ANALYSIS_DIR / "excluded_forms.csv"
VTM_SQL_PATH = ANALYSIS_DIR / "sql" / "vtms.sql"
VMP_SQL_PATH = ANALYSIS_DIR / "sql" / "vmp_forms.sql"
DATA_DIR = ANALYSIS_DIR / "data"
VTM_CACHE_PATH = DATA_DIR / "vtms.csv"
VMP_CACHE_PATH = DATA_DIR / "vmp_forms.csv"
OUTPUT_PATH = DATA_DIR / "aware_vmp_list.csv"

VTM_SCHEMA = {"id": pl.Int64, "nm": pl.String}
VMP_FORM_SCHEMA = {
    "vmp_id": pl.Int64,
    "vmp_nm": pl.String,
    "invalid_vmp": pl.Boolean,
    "vtm_id": pl.Int64,
    "vtm_nm": pl.String,
    "form": pl.String,
    "who_route_codes_for_ddd": pl.String,
    "atc": pl.String,
}
OUTPUT_COLUMNS = [
    "Antibiotic",
    "vtm_nm",
    "vtm_id",
    "vmp_nm",
    "vmp_id",
    "vmp_atc_route",
    "category_route",
    "aware_2019",
    "aware_2024",
]


def load_categories(path: Path) -> pl.DataFrame:
    """Read the category file and use empty strings for a missing route."""
    return (
        pl.read_csv(path)
        .rename({"antibiotic": "Antibiotic"})
        .with_columns(
            pl.col("route").fill_null(""),
            pl.col("atc_route").fill_null(""),
        )
        .select("Antibiotic", "route", "atc_route", "aware_2019", "aware_2024")
        .sort("Antibiotic", "atc_route")
    )


def load_excluded_forms(path: Path) -> pl.DataFrame:
    """Read form rules. Each rule is a suffix match or an exact match."""
    excluded_forms = pl.read_csv(path)
    match_types = set(excluded_forms.get_column("match_type").unique().to_list())
    unknown = match_types - {"suffix", "exact"}
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown form match types: {names}")
    return excluded_forms


def load_cached_query(
    sql_path: Path,
    cache_path: Path,
    schema: dict[str, pl.DataType],
) -> pl.DataFrame:
    """Read a query result from CSV, or run the SQL file and write that CSV."""
    if cache_path.exists():
        return pl.read_csv(cache_path, schema=schema)

    frame = query_to_polars(sql_path, schema=schema)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_csv(cache_path)
    return frame


def match_categories_to_vtms(
    categories: pl.DataFrame, vtms: pl.DataFrame
) -> pl.DataFrame:
    """Keep a VTM when its name contains the antibiotic name.

    The match is DIRECT when the names are equal. It is ASSUMED when the VTM
    name is longer. Drop every ASSUMED match for a VTM name that matches more
    than one category row with no ATC route.
    """
    matches = (
        categories.join(vtms, how="cross")
        .filter(pl.col("nm").str.contains(pl.col("Antibiotic"), literal=True))
        .with_columns(
            pl.when(pl.col("nm") == pl.col("Antibiotic"))
            .then(pl.lit("DIRECT"))
            .otherwise(pl.lit("ASSUMED"))
            .alias("match_type")
        )
    )
    duplicate_names = (
        matches.filter(pl.col("atc_route").fill_null("") == "")
        .group_by("nm")
        .len()
        .filter(pl.col("len") > 1)
        .get_column("nm")
    )
    unwanted = matches.filter(
        pl.col("nm").is_in(duplicate_names.to_list())
        & (pl.col("match_type") == "ASSUMED")
    )
    return (
        matches.join(
            unwanted.select("Antibiotic", "nm"),
            on=["Antibiotic", "nm"],
            how="anti",
        )
        .select("Antibiotic", "nm", "id", "atc_route", "aware_2019", "aware_2024")
        .sort("Antibiotic", "nm")
    )


def _form_is_excluded(form: pl.Expr, excluded_forms: pl.DataFrame) -> pl.Expr:
    suffixes = (
        excluded_forms.filter(pl.col("match_type") == "suffix")
        .get_column("pattern")
        .to_list()
    )
    exact_forms = (
        excluded_forms.filter(pl.col("match_type") == "exact")
        .get_column("pattern")
        .to_list()
    )
    checks: list[pl.Expr] = []
    if suffixes:
        suffix_checks = [form.str.ends_with(pattern) for pattern in suffixes]
        checks.append(pl.any_horizontal(suffix_checks))
    if exact_forms:
        checks.append(form.is_in(exact_forms))
    if not checks:
        return pl.lit(False)
    if len(checks) == 1:
        return checks[0]
    return pl.any_horizontal(checks)


def prepare_vmp_rows(
    vmp_forms: pl.DataFrame,
    excluded_forms: pl.DataFrame,
) -> pl.DataFrame:
    """Drop excluded forms and keep one row for each VMP and WHO route.

    ``who_route_codes_for_ddd`` is the route list from ``vmp_data``. Codes are
    separated by ``|``. An empty list stays one row with a null route.
    """
    kept_forms = vmp_forms.filter(
        pl.col("form").is_not_null()
        & ~_form_is_excluded(pl.col("form"), excluded_forms)
    )
    route_list = pl.col("who_route_codes_for_ddd")
    return (
        kept_forms.with_columns(
            pl.when(route_list.fill_null("") == "")
            .then(pl.lit(None, dtype=pl.String))
            .otherwise(route_list)
            .str.split("|")
            .alias("atc_route")
        )
        .explode("atc_route", empty_as_null=True)
        .select(
            "vmp_id",
            "vmp_nm",
            "invalid_vmp",
            "vtm_id",
            "vtm_nm",
            "atc_route",
            "atc",
        )
        .unique()
    )


def match_vmps(vtm_matches: pl.DataFrame, vmp_rows: pl.DataFrame) -> pl.DataFrame:
    """Keep a VMP when the category has no route, or the routes are equal."""
    return (
        vtm_matches.rename(
            {"id": "vtm_id", "nm": "vtm_nm", "atc_route": "category_route"}
        )
        .join(
            vmp_rows.rename({"atc_route": "vmp_atc_route", "vtm_nm": "vmp_vtm_nm"}),
            on="vtm_id",
            how="inner",
        )
        .filter(
            (pl.col("category_route").fill_null("") == "")
            | (pl.col("category_route") == pl.col("vmp_atc_route"))
        )
        .select(OUTPUT_COLUMNS)
        .unique()
        .sort("Antibiotic", "vtm_nm", "vmp_id")
    )


def build_vmp_list(
    categories: pl.DataFrame,
    vtms: pl.DataFrame,
    vmp_forms: pl.DataFrame,
    excluded_forms: pl.DataFrame,
) -> pl.DataFrame:
    """Return the final AWaRe VMP list."""
    vtm_matches = match_categories_to_vtms(categories, vtms)
    vmp_rows = prepare_vmp_rows(vmp_forms, excluded_forms)
    return match_vmps(vtm_matches, vmp_rows)


def write_vmp_list(output_path: Path = OUTPUT_PATH) -> Path:
    """Read the local inputs, then write the VMP list."""
    categories = load_categories(CATEGORIES_PATH)
    excluded_forms = load_excluded_forms(EXCLUDED_FORMS_PATH)
    vtms = load_cached_query(VTM_SQL_PATH, VTM_CACHE_PATH, VTM_SCHEMA)
    vmp_forms = load_cached_query(VMP_SQL_PATH, VMP_CACHE_PATH, VMP_FORM_SCHEMA)
    vmp_list = build_vmp_list(categories, vtms, vmp_forms, excluded_forms)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vmp_list.write_csv(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write the dm+d VMP list for the UK AWaRe categories."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="CSV path for the VMP list.",
    )
    args = parser.parse_args()
    print(write_vmp_list(args.output))


if __name__ == "__main__":
    main()
