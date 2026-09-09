from pathlib import Path
from unittest.mock import MagicMock

import fetch_oph_data as fetch_oph
import polars as pl
import pytest
from google.cloud import bigquery


def write_provisional_csv(path: Path, rows: str) -> Path:
    path.write_text(
        "YEAR_MONTH,ODS_CODE,VMP_SNOMED_CODE,VMP_PRODUCT_NAME,"
        "VMP_UNIT_DOSE_UNIT_OF_MEASURE_NAME\n" + rows
    )
    return path


def test_load_vmp_codes(tmp_path: Path) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,TABLET\n"
        "202606,RDE,111,Alpha,TABLET\n"
        "202606,RYJ,222,Beta,ML\n"
        "202606,RYJ,,Missing,ML\n",
    )

    vmp_codes = fetch_oph.load_vmp_codes(csv_path)

    assert sorted(vmp_codes) == ["111", "222"]


def test_fetch_vmp_rows_returns_empty_when_no_codes() -> None:
    client = MagicMock()

    result = fetch_oph.fetch_vmp_rows([], client=client)

    assert result.height == 0
    client.query.assert_not_called()


def test_fetch_vmp_rows_queries_vmp_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = pl.DataFrame(
        {
            "vmp_code": ["111"],
            "udfs": [1.0],
            "udfs_uom": ["tablet"],
            "unit_dose_uom": ["tablet"],
            "df_ind": ["Discrete"],
        },
        schema=fetch_oph.VMP_FETCH_SCHEMA,
    )
    query_to_polars = MagicMock(return_value=expected)
    monkeypatch.setattr(fetch_oph, "query_to_polars", query_to_polars)
    client = MagicMock()

    result = fetch_oph.fetch_vmp_rows(["111", "222"], client=client)

    assert result.equals(expected)
    query_to_polars.assert_called_once_with(
        fetch_oph.VMP_QUERY,
        schema=fetch_oph.VMP_FETCH_SCHEMA,
        query_parameters=[
            bigquery.ArrayQueryParameter("vmp_codes", "STRING", ["111", "222"])
        ],
        client=client,
    )


def test_main_writes_vmp_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,TABLET\n",
    )
    output_path = tmp_path / "vmp_data.csv"
    monkeypatch.setattr(fetch_oph, "PROVISIONAL_CSV", csv_path)
    monkeypatch.setattr(fetch_oph, "OUTPUT_CSV", output_path)
    monkeypatch.setattr(
        fetch_oph,
        "fetch_vmp_rows",
        lambda codes: pl.DataFrame(
            {
                "vmp_code": codes,
                "udfs": [1.0],
                "udfs_uom": ["tablet"],
                "unit_dose_uom": ["tablet"],
                "df_ind": ["Discrete"],
            }
        ),
    )

    vmp = fetch_oph.main()

    assert vmp.get_column("vmp_code").to_list() == ["111"]
    assert output_path.exists()
