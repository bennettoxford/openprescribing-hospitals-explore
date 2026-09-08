from pathlib import Path

import compare_unit_doses as compare
import polars as pl
import pytest


def write_provisional_csv(path: Path, rows: str) -> Path:
    path.write_text(
        "YEAR_MONTH,ODS_CODE,VMP_SNOMED_CODE,VMP_PRODUCT_NAME,"
        "VMP_UDFS_UNIT_OF_MEASURE_NAME,"
        "VMP_UNIT_DOSE_UNIT_OF_MEASURE_NAME,"
        "TOTAL_QUANTITY_IN_VMP_UDFS_UNIT_OF_MEASURE,"
        "TOTAL_QUANTITY_IN_VMP_UNIT_DOSE_UNIT_OF_MEASURE\n" + rows
    )
    return path


def test_load_provisional_vmps(tmp_path: Path) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,TABLET,TABLET,10,2\n"
        "202606,RDE,111,Alpha,TABLET,TABLET,20,4\n"
        "202606,RYJ,222,Beta,ML,ML,100,100\n"
        "202606,RYJ,,Missing,ML,ML,1,1\n",
    )

    vmps = compare.load_provisional_vmps(csv_path).sort("vmp_code")

    assert vmps.get_column("vmp_code").to_list() == ["111", "222"]
    assert vmps.get_column("vmp_product_name").to_list() == ["Alpha", "Beta"]
    assert vmps.get_column("provisional_udfs_uom").to_list() == [
        "TABLET",
        "ML",
    ]
    assert vmps.get_column("provisional_unit_dose_uom").to_list() == [
        "TABLET",
        "ML",
    ]
    assert vmps.get_column("provisional_udfs").to_list() == [5.0, 1.0]
    assert vmps.get_column("provisional_udfs_consistent").to_list() == [True, True]


def test_load_provisional_vmps_treats_float_noise_as_consistent(
    tmp_path: Path,
) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,ML,VIAL,130.000008,1\n"
        "202606,RYJ,111,Alpha,ML,VIAL,130,1\n",
    )

    vmps = compare.load_provisional_vmps(csv_path)

    assert vmps.height == 1
    assert vmps.get_column("provisional_udfs_consistent").to_list() == [True]


def test_load_provisional_vmps_rejects_inconsistent_udfs_uom(
    tmp_path: Path,
) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,ML,VIAL,10,2\n202606,RYJ,111,Alpha,MG,VIAL,10,2\n",
    )

    with pytest.raises(ValueError, match=r"provisional_udfs_uom.*111"):
        compare.load_provisional_vmps(csv_path)


def test_load_provisional_vmps_rejects_inconsistent_unit_dose_uom(
    tmp_path: Path,
) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,ML,VIAL,10,2\n202606,RYJ,111,Alpha,ML,AMPOULE,10,2\n",
    )

    with pytest.raises(ValueError, match=r"provisional_unit_dose_uom.*111"):
        compare.load_provisional_vmps(csv_path)


def test_load_provisional_vmps_ignores_null_uom_rows(tmp_path: Path) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,,,10,2\n202606,RYJ,111,Alpha,ML,VIAL,10,2\n",
    )

    vmps = compare.load_provisional_vmps(csv_path)

    assert vmps.height == 1
    assert vmps.get_column("provisional_udfs_uom").to_list() == ["ML"]
    assert vmps.get_column("provisional_unit_dose_uom").to_list() == ["VIAL"]


def test_load_provisional_vmps_flags_inconsistent_udfs(tmp_path: Path) -> None:
    csv_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,ML,VIAL,10,2\n"
        "202606,RYJ,111,Alpha,ML,VIAL,20,5\n",
    )

    vmps = compare.load_provisional_vmps(csv_path)

    assert vmps.height == 1
    assert vmps.get_column("provisional_udfs_consistent").to_list() == [False]
    assert vmps.get_column("provisional_udfs").to_list()[0] in {4.0, 5.0}


def test_compare_unit_doses_classifies_agreement() -> None:
    provisional = pl.DataFrame(
        {
            "vmp_code": ["1", "2", "3", "4", "5", "6"],
            "provisional_udfs_uom": [
                "ML",
                "MG",
                "ML",
                None,
                "TABLET",
                None,
            ],
            "provisional_unit_dose_uom": [
                "ML",
                "VIAL",
                "ML",
                None,
                "CAPSULE",
                None,
            ],
            "provisional_udfs": [1.0, 1.0, 5.0, None, 1.0, None],
        }
    )
    vmp = pl.DataFrame(
        {
            "vmp_code": ["1", "2", "3", "4", "6"],
            "udfs_uom": ["ml", "microgram", None, "tablet", None],
            "udfs": [1.0, 2.0, None, 1.0, None],
            "unit_dose_uom": ["ml", "vial", None, "tablet", None],
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
        "3": compare.STATUS_VMP_UDFS_UOM_MISSING,
        "4": compare.STATUS_PROVISIONAL_UDFS_UOM_MISSING,
        "5": compare.STATUS_MISSING_FROM_VMP_DATA,
        "6": compare.STATUS_AGREE,
    }
    assert comparison.get_column("provisional_units_match").to_list() == [
        True,
        False,
        True,
        False,
        False,
        False,
    ]

    udfs_statuses = dict(
        zip(
            comparison.get_column("vmp_code").to_list(),
            comparison.get_column("udfs_status").to_list(),
            strict=True,
        )
    )
    assert udfs_statuses == {
        "1": compare.STATUS_AGREE,
        "2": compare.STATUS_DISAGREE,
        "3": compare.STATUS_VMP_UDFS_MISSING,
        "4": compare.STATUS_PROVISIONAL_UDFS_MISSING,
        "5": compare.STATUS_MISSING_FROM_VMP_DATA,
        "6": compare.STATUS_AGREE,
    }

    unit_dose_uom_statuses = dict(
        zip(
            comparison.get_column("vmp_code").to_list(),
            comparison.get_column("unit_dose_uom_status").to_list(),
            strict=True,
        )
    )
    assert unit_dose_uom_statuses == {
        "1": compare.STATUS_AGREE,
        "2": compare.STATUS_AGREE,
        "3": compare.STATUS_VMP_UNIT_DOSE_UOM_MISSING,
        "4": compare.STATUS_PROVISIONAL_UNIT_DOSE_UOM_MISSING,
        "5": compare.STATUS_MISSING_FROM_VMP_DATA,
        "6": compare.STATUS_AGREE,
    }


def test_main_reads_inputs_and_writes_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provisional_path = write_provisional_csv(
        tmp_path / "scmd.csv",
        "202606,RDE,111,Alpha,TABLET,TABLET,10,10\n",
    )
    vmp_path = tmp_path / "vmp_data.csv"
    pl.DataFrame(
        {
            "vmp_code": ["111"],
            "udfs_uom": ["tablet"],
            "udfs": [1.0],
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
    assert comparison.get_column("udfs_status").to_list() == [compare.STATUS_AGREE]
    assert comparison.get_column("unit_dose_uom_status").to_list() == [
        compare.STATUS_AGREE
    ]
    assert output_path.exists()


def test_compare_udfs_treats_float_noise_as_agree() -> None:
    provisional = pl.DataFrame(
        {
            "vmp_code": ["1"],
            "provisional_udfs_uom": ["ML"],
            "provisional_unit_dose_uom": ["VIAL"],
            "provisional_udfs": [130.000008],
        }
    )
    vmp = pl.DataFrame(
        {
            "vmp_code": ["1"],
            "udfs_uom": ["ml"],
            "udfs": [130.0],
            "unit_dose_uom": ["vial"],
            "df_ind": ["Discrete"],
        }
    )

    comparison = compare.compare_unit_doses(provisional, vmp)

    assert comparison.get_column("udfs_status").to_list() == [compare.STATUS_AGREE]


def test_compare_unit_dose_uom_classifies_disagreement() -> None:
    provisional = pl.DataFrame(
        {
            "vmp_code": ["1"],
            "provisional_udfs_uom": ["ML"],
            "provisional_unit_dose_uom": ["VIAL"],
            "provisional_udfs": [5.0],
        }
    )
    vmp = pl.DataFrame(
        {
            "vmp_code": ["1"],
            "udfs_uom": ["ml"],
            "udfs": [5.0],
            "unit_dose_uom": ["ampoule"],
            "df_ind": ["Discrete"],
        }
    )

    comparison = compare.compare_unit_doses(provisional, vmp)

    assert comparison.get_column("unit_dose_uom_status").to_list() == [
        compare.STATUS_DISAGREE
    ]
