from collections.abc import Sequence
from pathlib import Path

import polars as pl
from google.cloud import bigquery
from google.oauth2.service_account import Credentials

PROJECT_ID = "ebmdatalab"
LOCATION = "EU"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CREDENTIALS_PATH = REPO_ROOT / "bq-service-account.json"

QueryParameter = (
    bigquery.ArrayQueryParameter
    | bigquery.RangeQueryParameter
    | bigquery.ScalarQueryParameter
    | bigquery.StructQueryParameter
)


def get_bigquery_client() -> bigquery.Client:
    credentials = Credentials.from_service_account_file(
        DEFAULT_CREDENTIALS_PATH
    )
    return bigquery.Client(
        project=PROJECT_ID, credentials=credentials, location=LOCATION
    )


def query_to_polars(
    sql_path: Path,
    *,
    schema: dict[str, pl.DataType],
    query_parameters: Sequence[QueryParameter] = (),
    client: bigquery.Client | None = None,
) -> pl.DataFrame:
    """Run a SQL file in BigQuery and return its rows as a Polars DataFrame."""
    if client is None:
        client = get_bigquery_client()

    sql = sql_path.read_text()
    job_config = bigquery.QueryJobConfig(
        query_parameters=list(query_parameters),
    )
    results = client.query(sql, job_config=job_config).result()
    rows = [dict(row.items()) for row in results]
    return pl.DataFrame(rows, schema=schema)
