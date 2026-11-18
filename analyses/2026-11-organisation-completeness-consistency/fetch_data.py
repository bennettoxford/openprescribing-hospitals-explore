from pathlib import Path

import polars as pl
from google.cloud import bigquery
from summarise import successor_anchors

from oph_utils.bigquery import query_to_polars

ANALYSIS_DIR = Path(__file__).resolve().parent
SQL_DIR = ANALYSIS_DIR / "sql"
DATA_DIR = ANALYSIS_DIR / "data"

ORGANISATION_SCHEMA = {
    "ods_code": pl.String,
    "ods_name": pl.String,
    "successors": pl.String,
    "ultimate_successors": pl.String,
    "predecessors": pl.String,
    "legal_closed_date": pl.Date,
    "operational_closed_date": pl.Date,
    "legal_open_date": pl.Date,
    "operational_open_date": pl.Date,
}

MONTHLY_PRODUCTS_SCHEMA = {
    "ods_code": pl.String,
    "year_month": pl.Date,
    "n_products": pl.Int64,
}

AGGREGATED_PRODUCTS_SCHEMA = MONTHLY_PRODUCTS_SCHEMA

DATA_STATUS_SCHEMA = {
    "file_type": pl.String,
    "min_month": pl.Date,
    "max_month": pl.Date,
}


def fetch_organisations() -> pl.DataFrame:
    """Return every organisation in the OpenPrescribing Hospitals ODS table."""
    return query_to_polars(
        SQL_DIR / "organisations.sql",
        schema=ORGANISATION_SCHEMA,
    )


def fetch_monthly_products() -> pl.DataFrame:
    """Return the number of products with a positive quantity each trust-month."""
    return query_to_polars(
        SQL_DIR / "monthly_products.sql",
        schema=MONTHLY_PRODUCTS_SCHEMA,
    )


def fetch_aggregated_products(organisations: pl.DataFrame) -> pl.DataFrame:
    """Return distinct product counts after predecessors roll into the successor."""
    anchors = successor_anchors(organisations)
    codes = list(anchors)
    return query_to_polars(
        SQL_DIR / "aggregated_products.sql",
        schema=AGGREGATED_PRODUCTS_SCHEMA,
        query_parameters=[
            bigquery.ArrayQueryParameter("ods_codes", "STRING", codes),
            bigquery.ArrayQueryParameter(
                "anchors",
                "STRING",
                [anchors[code] for code in codes],
            ),
        ],
    )


def fetch_data_status() -> pl.DataFrame:
    """Return the first and last month of each SCMD file type."""
    return query_to_polars(
        SQL_DIR / "data_status.sql",
        schema=DATA_STATUS_SCHEMA,
    )


def write_extracts(
    organisations: pl.DataFrame,
    monthly_products: pl.DataFrame,
    data_status: pl.DataFrame,
    aggregated_products: pl.DataFrame,
    data_dir: Path = DATA_DIR,
) -> None:
    """Write the extracts the report reads."""
    data_dir.mkdir(parents=True, exist_ok=True)
    organisations.write_csv(data_dir / "organisations.csv")
    monthly_products.write_csv(data_dir / "monthly_products.csv")
    data_status.write_csv(data_dir / "data_status.csv")
    aggregated_products.write_csv(data_dir / "aggregated_products.csv")


def main() -> None:
    organisations = fetch_organisations()
    monthly_products = fetch_monthly_products()
    data_status = fetch_data_status()
    aggregated_products = fetch_aggregated_products(organisations)
    write_extracts(
        organisations,
        monthly_products,
        data_status,
        aggregated_products,
    )
    print(DATA_DIR)


if __name__ == "__main__":
    main()
