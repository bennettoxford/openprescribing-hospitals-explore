import aware_vmp_list as aware
import polars as pl
import pytest


def categories(*rows: tuple[str, str, str, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Antibiotic": [row[0] for row in rows],
            "route": [""] * len(rows),
            "atc_route": [row[1] for row in rows],
            "aware_2019": [row[2] for row in rows],
            "aware_2024": [row[3] for row in rows],
        }
    )


def vtms(*rows: tuple[int, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {"id": [row[0] for row in rows], "nm": [row[1] for row in rows]},
        schema={"id": pl.Int64, "nm": pl.String},
    )


def test_drops_assumed_duplicate_and_keeps_direct_match() -> None:
    matched = aware.match_categories_to_vtms(
        categories(
            ("Ampicillin", "", "Access", "Access"),
            ("Flucloxacillin", "", "Access", "Access"),
            ("Ampicillin + Flucloxacillin", "", "Other", "Other"),
        ),
        vtms(
            (1, "Ampicillin"),
            (2, "Flucloxacillin"),
            (3, "Ampicillin + Flucloxacillin"),
        ),
    )

    combo = matched.filter(pl.col("nm") == "Ampicillin + Flucloxacillin")
    assert combo.height == 1
    assert combo.get_column("Antibiotic").item() == "Ampicillin + Flucloxacillin"
    assert combo.get_column("aware_2024").item() == "Other"


def test_keeps_assumed_match_when_the_vtm_name_matches_once() -> None:
    matched = aware.match_categories_to_vtms(
        categories(("Amikacin", "", "Watch", "Watch")),
        vtms((1, "Amikacin"), (2, "Amikacin liposomal")),
    )

    assert matched.get_column("nm").sort().to_list() == [
        "Amikacin",
        "Amikacin liposomal",
    ]


def test_route_filter_keeps_blank_category_route_and_equal_routes() -> None:
    vtm_matches = pl.DataFrame(
        {
            "Antibiotic": ["Colistin", "Colistin", "Amoxicillin"],
            "nm": ["Colistin", "Colistin", "Amoxicillin"],
            "id": [1, 1, 2],
            "atc_route": ["O", "P", ""],
            "aware_2019": ["Reserve", "Reserve", "Access"],
            "aware_2024": ["Reserve", "Reserve", "Access"],
        },
        schema={
            "Antibiotic": pl.String,
            "nm": pl.String,
            "id": pl.Int64,
            "atc_route": pl.String,
            "aware_2019": pl.String,
            "aware_2024": pl.String,
        },
    )
    vmp_rows = pl.DataFrame(
        {
            "vmp_id": [10, 11, 12],
            "vmp_nm": ["oral product", "iv product", "capsule"],
            "invalid_vmp": [False, False, False],
            "vtm_id": [1, 1, 2],
            "vtm_nm": ["Colistin", "Colistin", "Amoxicillin"],
            "atc_route": ["O", "P", "O"],
            "atc": ["J01", "J01", "J01"],
        }
    )

    result = aware.match_vmps(vtm_matches, vmp_rows)

    assert result.select("vmp_id", "category_route").sort("vmp_id").rows() == [
        (10, "O"),
        (11, "P"),
        (12, ""),
    ]


def test_route_list_becomes_one_row_per_route() -> None:
    vmp_forms = pl.DataFrame(
        {
            "vmp_id": [5, 6, 7],
            "vmp_nm": ["infusion", "tablet", "unmapped"],
            "invalid_vmp": [False, False, False],
            "vtm_id": [1, 1, 1],
            "vtm_nm": ["Flucloxacillin", "Flucloxacillin", "Flucloxacillin"],
            "form": ["infusion.intravenous", "tablet.oral", "powder"],
            "who_route_codes_for_ddd": ["P", "O|P", None],
            "atc": ["J01", "J01", "J01"],
        }
    )
    excluded_forms = pl.DataFrame({"pattern": [".cutaneous"], "match_type": ["suffix"]})

    rows = aware.prepare_vmp_rows(vmp_forms, excluded_forms)

    assert rows.select("vmp_id", "atc_route").sort("vmp_id", "atc_route").rows() == [
        (5, "P"),
        (6, "O"),
        (6, "P"),
        (7, None),
    ]


def test_form_rules_drop_suffix_and_exact_forms() -> None:
    vmp_forms = pl.DataFrame(
        {
            "vmp_id": [1, 2, 3],
            "vmp_nm": ["drops", "vaginal gel", "tablet"],
            "invalid_vmp": [False, False, False],
            "vtm_id": [1, 1, 1],
            "vtm_nm": ["Drug", "Drug", "Drug"],
            "form": ["drops.ophthalmic", "gel.vaginal", "tablet.oral"],
            "who_route_codes_for_ddd": ["O", "O", "O"],
            "atc": ["J01", "J01", "J01"],
        }
    )
    excluded_forms = pl.DataFrame(
        {
            "pattern": [".ophthalmic", "gel.vaginal"],
            "match_type": ["suffix", "exact"],
        }
    )

    rows = aware.prepare_vmp_rows(vmp_forms, excluded_forms)

    assert rows.get_column("vmp_nm").to_list() == ["tablet"]


def test_load_cached_query_reads_csv_and_skips_bigquery(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "vtms.csv"
    pl.DataFrame({"id": [1], "nm": ["Amoxicillin"]}, schema=aware.VTM_SCHEMA).write_csv(
        cache
    )

    def fail(*_args, **_kwargs):
        raise AssertionError("BigQuery was called")

    monkeypatch.setattr(aware, "query_to_polars", fail)
    frame = aware.load_cached_query(tmp_path / "vtms.sql", cache, aware.VTM_SCHEMA)

    assert frame.get_column("nm").item() == "Amoxicillin"


def test_load_cached_query_writes_csv_when_missing(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "nested" / "vmp_forms.csv"
    schema = {
        "vmp_id": pl.Int64,
        "form": pl.String,
        "invalid_vmp": pl.Boolean,
    }
    expected = pl.DataFrame(
        {"vmp_id": [2], "form": [None], "invalid_vmp": [None]},
        schema=schema,
    )

    def fake_query(sql_path, *, schema, **_kwargs):
        assert sql_path.name == "vmp_forms.sql"
        return expected

    monkeypatch.setattr(aware, "query_to_polars", fake_query)
    frame = aware.load_cached_query(tmp_path / "vmp_forms.sql", cache, schema)

    assert frame.equals(expected)
    assert pl.read_csv(cache, schema=schema).equals(expected)


def test_unknown_form_match_type_raises(tmp_path) -> None:
    path = tmp_path / "excluded_forms.csv"
    path.write_text("pattern,match_type\n.oral,contains\n")

    with pytest.raises(ValueError, match="Unknown form match types"):
        aware.load_excluded_forms(path)
