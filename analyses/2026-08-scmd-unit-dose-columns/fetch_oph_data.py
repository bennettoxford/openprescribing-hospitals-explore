from pathlib import Path

import polars as pl
from fetch_data import TARGET as PROVISIONAL_CSV
from google.cloud import bigquery

from oph_utils.bigquery import query_to_polars

VMP_QUERY = Path(__file__).resolve().parent / "fetch_vmp_rows.sql"
OUTPUT_CSV = Path(__file__).resolve().parent / "data" / "vmp_data.csv"

VMP_FETCH_SCHEMA = {
    "vmp_code": pl.String,
    "udfs": pl.Float64,
    "udfs_uom": pl.String,
    "unit_dose_uom": pl.String,
    "df_ind": pl.String,
}


def load_vmp_codes(csv_path: Path) -> list[str]:
    """Return the unique VMP codes in the provisional SCMD extract."""
    return (
        pl.read_csv(csv_path, columns=["VMP_SNOMED_CODE"])
        .drop_nulls("VMP_SNOMED_CODE")
        .get_column("VMP_SNOMED_CODE")
        .cast(pl.String)
        .unique()
        .to_list()
    )


def fetch_vmp_rows(
    vmp_codes: list[str],
    *,
    client: bigquery.Client | None = None,
) -> pl.DataFrame:
    """Return VMP rows from vmp_data for the given VMP codes."""
    if not vmp_codes:
        return pl.DataFrame(schema=VMP_FETCH_SCHEMA)

    return query_to_polars(
        VMP_QUERY,
        schema=VMP_FETCH_SCHEMA,
        query_parameters=[
            bigquery.ArrayQueryParameter("vmp_codes", "STRING", vmp_codes),
        ],
        client=client,
    )


def main() -> pl.DataFrame:
    vmp_codes = load_vmp_codes(PROVISIONAL_CSV)
    vmp = fetch_vmp_rows(vmp_codes)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    vmp.write_csv(OUTPUT_CSV)
    return vmp


if __name__ == "__main__":
    main()
