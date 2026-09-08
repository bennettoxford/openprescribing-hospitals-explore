from pathlib import Path

import compare_unit_doses as compare
import polars as pl
import pytest


def write_provisional_csv(path: Path, rows: str) -> Path:
    path.write_text(
        "YEAR_MONTH,ODS_CODE,VMP_SNOMED_CODE,VMP_PRODUCT_NAME,"
        "VMP_UNIT_DOSE_UNIT_OF_MEASURE_NAME\n" + rows
    )
    return path


def test_load_provisional_vmps(tmp_path: Path) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,TABLET\n"
        "202606,RDE,111,Alpha,TABLET\n"
        "202606,RYJ,222,Beta,ML\n"
        "202606,RYJ,,Missing,ML\n",
    )

    vmps = compare.load_provisional_vmps(csv_path).sort("vmp_code")

    assert vmps.get_column("vmp_code").to_list() == ["111", "222"]
    assert vmps.get_column("provisional_unit_dose_uom").to_list() == [
        "TABLET",
        "ML",
    ]


def test_compare_unit_doses_classifies_agreement() -> None:
    provisional = pl.DataFrame(
        {
            "vmp_code": ["1", "2", "3", "4", "5", "6"],
            "provisional_vmp_name": ["A", "B", "C", "D", "E", "F"],
            "provisional_unit_dose_uom": [
                "TABLET",
                "ML",
                "VIAL",
                None,
                "CAPSULE",
                None,
            ],
        }
    )
    vmp = pl.DataFrame(
        {
            "vmp_code": ["1", "2", "3", "4", "6"],
            "vmp_name": ["A", "B", "C", "D", "F"],
            "unit_dose_uom": ["tablet", "ampoule", None, "capsule", None],
            "df_ind": [
                "Discrete",
                "Continuous",
                "Continuous",
                "Discrete",
                "Not applicable",
            ],
        }
    )

    comparison = compare.compare_unit_doses(provisional, vmp).sort("vmp_code")
    statuses = dict(
        zip(
            comparison.get_column("vmp_code").to_list(),
            comparison.get_column("status").to_list(),
            strict=True,
        )
    )

    assert statuses == {
        "1": compare.STATUS_AGREE,
        "2": compare.STATUS_DISAGREE,
        "3": compare.STATUS_VMP_UNIT_DOSE_MISSING,
        "4": compare.STATUS_PROVISIONAL_UNIT_DOSE_MISSING,
        "5": compare.STATUS_MISSING_FROM_VMP_DATA,
        "6": compare.STATUS_AGREE,
    }


def test_main_reads_inputs_and_writes_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provisional_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,TABLET\n",
    )
    vmp_path = tmp_path / "vmp_data.csv"
    pl.DataFrame(
        {
            "vmp_code": ["111"],
            "vmp_name": ["Alpha"],
            "unit_dose_uom": ["tablet"],
            "df_ind": ["Discrete"],
        }
    ).write_csv(vmp_path)
    output_path = tmp_path / "comparison.csv"
    monkeypatch.setattr(compare, "PROVISIONAL_CSV", provisional_path)
    monkeypatch.setattr(compare, "VMP_CSV", vmp_path)
    monkeypatch.setattr(compare, "OUTPUT_CSV", output_path)

    comparison = compare.main()

    assert comparison.get_column("status").to_list() == [compare.STATUS_AGREE]
    assert output_path.exists()
