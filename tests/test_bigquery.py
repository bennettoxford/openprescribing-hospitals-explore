from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
from google.cloud import bigquery

from oph_utils.bigquery import query_to_polars

SCHEMA = {
    "code": pl.String,
    "value": pl.Int64,
}


def test_query_to_polars_runs_sql_file(tmp_path: Path) -> None:
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("SELECT code, value FROM example WHERE code = @code")
    parameter = bigquery.ScalarQueryParameter("code", "STRING", "abc")
    row = MagicMock()
    row.items.return_value = [("code", "abc"), ("value", 12)]
    query_job = MagicMock()
    query_job.result.return_value = [row]
    client = MagicMock()
    client.query.return_value = query_job

    result = query_to_polars(
        sql_path,
        schema=SCHEMA,
        query_parameters=[parameter],
        client=client,
    )

    assert result.to_dicts() == [{"code": "abc", "value": 12}]
    job_config = client.query.call_args.kwargs["job_config"]
    client.query.assert_called_once_with(
        sql_path.read_text(),
        job_config=job_config,
    )
    assert job_config.query_parameters == [parameter]
    query_job.result.assert_called_once_with()


def test_query_to_polars_returns_schema_for_no_rows(tmp_path: Path) -> None:
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("SELECT code, value FROM example")
    client = MagicMock()
    client.query.return_value.result.return_value = []

    result = query_to_polars(sql_path, schema=SCHEMA, client=client)

    assert result.height == 0
    assert result.schema == pl.Schema(SCHEMA)
