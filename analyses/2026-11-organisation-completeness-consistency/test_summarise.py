from datetime import date

import fetch_data
import polars as pl
from summarise import (
    chart_groups,
    consecutive_ranges,
    expected_trusts,
    expected_window,
    format_span_list,
    gap_ranges,
    has_successor,
    incomplete_submissions,
    inconsistent_product_counts,
    missing_trusts,
    organisation_change_groups,
    period_bounds,
    product_series,
    submitted_trusts,
    successor_anchors,
)


def organisations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ods_code": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "ods_name": [
                "Alpha NHS Trust",
                "Beta Ambulance Service NHS Trust",
                "Closed Before NHS Trust",
                "Delta NHS Trust",
                "Echo NHS Trust",
            ],
            "successors": [None, None, None, "AAA", None],
            "ultimate_successors": [None, None, None, "AAA", None],
            "predecessors": ["DDD", None, None, None, None],
            "legal_closed_date": [
                None,
                None,
                date(2018, 1, 1),
                None,
                None,
            ],
            "operational_closed_date": [None, None, None, None, None],
            "legal_open_date": [
                date(2010, 4, 1),
                None,
                date(2000, 4, 1),
                date(2010, 4, 1),
                date(2026, 6, 1),
            ],
            "operational_open_date": [None, None, None, None, None],
        }
    )


def monthly_products() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ods_code": ["AAA", "AAA", "AAA", "DDD"],
            "year_month": [
                date(2019, 1, 1),
                date(2019, 2, 1),
                date(2019, 3, 1),
                date(2019, 1, 1),
            ],
            "n_products": [10, 0, 12, 4],
        }
    )


def test_expected_trusts_drops_closures_before_2019() -> None:
    trusts = expected_trusts(organisations())

    assert trusts.get_column("ods_code").to_list() == ["AAA", "BBB", "DDD", "EEE"]


def test_submitted_trusts_keeps_a_closure_that_has_rows() -> None:
    monthly = pl.concat(
        [
            monthly_products(),
            pl.DataFrame(
                {
                    "ods_code": ["CCC"],
                    "year_month": [date(2019, 1, 1)],
                    "n_products": [3],
                }
            ),
        ]
    )

    codes = submitted_trusts(organisations(), monthly).get_column("ods_code").to_list()

    assert "CCC" in codes
    assert "BBB" not in codes


def test_missing_trusts_keeps_trusts_with_no_positive_quantity() -> None:
    missing = missing_trusts(expected_trusts(organisations()), monthly_products())

    assert missing.get_column("ods_code").to_list() == ["BBB", "EEE"]


def test_product_series_fills_missing_months_with_zero() -> None:
    series = product_series(
        monthly_products(),
        "DDD",
        date(2019, 1, 1),
        date(2019, 3, 1),
    )

    assert series.get_column("n_products").to_list() == [4, 0, 0]


def test_consecutive_ranges_and_gaps() -> None:
    months = [date(2019, 1, 1), date(2019, 3, 1)]

    assert consecutive_ranges(months) == [
        (date(2019, 1, 1), date(2019, 1, 1)),
        (date(2019, 3, 1), date(2019, 3, 1)),
    ]
    assert gap_ranges(months, date(2019, 1, 1), date(2019, 4, 1)) == [
        (date(2019, 2, 1), date(2019, 2, 1)),
        (date(2019, 4, 1), date(2019, 4, 1)),
    ]
    assert format_span_list([(date(2019, 1, 1), date(2019, 2, 1))]) == (
        "January 2019 to February 2019"
    )


def test_chart_groups_keeps_a_successor_with_its_predecessors() -> None:
    organisations = pl.DataFrame(
        {
            "ods_code": ["AAA", "DDD", "BBB"],
            "ods_name": ["Alpha NHS Trust", "Delta NHS Trust", "Beta NHS Trust"],
            "successors": [None, "AAA", None],
            "ultimate_successors": [None, "AAA", None],
            "predecessors": ["DDD", None, None],
            "legal_closed_date": [None, None, None],
            "operational_closed_date": [None, None, None],
            "legal_open_date": [None, None, None],
            "operational_open_date": [None, None, None],
        }
    )

    assert chart_groups(["DDD", "BBB"], organisations) == [["AAA", "DDD"], ["BBB"]]


def test_expected_window_starts_at_the_later_open_date() -> None:
    row = {
        "legal_open_date": date(2019, 4, 1),
        "operational_open_date": date(2019, 1, 15),
        "legal_closed_date": None,
        "operational_closed_date": date(2019, 6, 30),
    }

    assert expected_window(row, date(2019, 1, 1), date(2019, 12, 1)) == (
        date(2019, 4, 1),
        date(2019, 6, 1),
    )


def test_incomplete_submissions_respects_open_and_close_dates() -> None:
    trusts = pl.DataFrame(
        {
            "ods_code": ["GAP", "CLOSED", "NEW"],
            "ods_name": ["Gap NHS Trust", "Closed NHS Trust", "New NHS Trust"],
            "successors": [None, None, None],
            "ultimate_successors": [None, None, None],
            "predecessors": [None, None, None],
            "legal_closed_date": [None, date(2019, 3, 31), None],
            "operational_closed_date": [None, None, None],
            "legal_open_date": [date(2010, 4, 1), date(2010, 4, 1), date(2019, 3, 1)],
            "operational_open_date": [None, None, None],
        }
    )
    monthly = pl.DataFrame(
        {
            "ods_code": [
                "GAP",
                "GAP",
                "GAP",
                "CLOSED",
                "CLOSED",
                "CLOSED",
                "NEW",
                "NEW",
            ],
            "year_month": [
                date(2019, 1, 1),
                date(2019, 3, 1),
                date(2019, 4, 1),
                date(2019, 1, 1),
                date(2019, 2, 1),
                date(2019, 3, 1),
                date(2019, 3, 1),
                date(2019, 4, 1),
            ],
            "n_products": [5, 5, 5, 5, 5, 5, 5, 5],
        }
    )
    start = date(2019, 1, 1)
    end = date(2019, 4, 1)

    closed = trusts.filter(pl.col("ods_code") == "CLOSED").row(0, named=True)
    assert expected_window(closed, start, end) == (start, date(2019, 3, 1))

    incomplete = incomplete_submissions(trusts, monthly, start, end)

    assert incomplete.get_column("ods_code").to_list() == ["GAP"]
    assert incomplete.get_column("missing_months").to_list() == ["February 2019"]


def test_period_bounds_uses_final_and_provisional_months() -> None:
    status = pl.DataFrame(
        {
            "file_type": ["final", "provisional"],
            "min_month": [date(2019, 1, 1), date(2026, 4, 1)],
            "max_month": [date(2026, 3, 1), date(2026, 8, 1)],
        }
    )

    assert period_bounds(status) == (
        date(2019, 1, 1),
        date(2026, 8, 1),
        date(2026, 4, 1),
    )


def test_has_successor() -> None:
    orgs = organisations()

    assert has_successor(orgs, "DDD")
    assert not has_successor(orgs, "AAA")


def test_fetch_functions_read_the_sql_files(monkeypatch) -> None:
    calls: list[tuple[str, set[str]]] = []

    def fake_query(path, *, schema):
        calls.append((path.name, set(schema)))
        return pl.DataFrame(schema=schema)

    monkeypatch.setattr(fetch_data, "query_to_polars", fake_query)

    fetch_data.fetch_organisations()
    fetch_data.fetch_monthly_products()
    fetch_data.fetch_data_status()

    assert calls == [
        ("organisations.sql", set(fetch_data.ORGANISATION_SCHEMA)),
        ("monthly_products.sql", set(fetch_data.MONTHLY_PRODUCTS_SCHEMA)),
        ("data_status.sql", set(fetch_data.DATA_STATUS_SCHEMA)),
    ]


def test_write_extracts_writes_three_csv_files(tmp_path) -> None:
    organisations_frame = pl.DataFrame(schema=fetch_data.ORGANISATION_SCHEMA)
    monthly_frame = pl.DataFrame(schema=fetch_data.MONTHLY_PRODUCTS_SCHEMA)
    status_frame = pl.DataFrame(schema=fetch_data.DATA_STATUS_SCHEMA)
    aggregated_frame = pl.DataFrame(schema=fetch_data.AGGREGATED_PRODUCTS_SCHEMA)

    fetch_data.write_extracts(
        organisations_frame,
        monthly_frame,
        status_frame,
        aggregated_frame,
        tmp_path,
    )

    assert (tmp_path / "organisations.csv").exists()
    assert (tmp_path / "monthly_products.csv").exists()
    assert (tmp_path / "data_status.csv").exists()
    assert (tmp_path / "aggregated_products.csv").exists()


def test_successor_anchors_follow_the_first_successor() -> None:
    orgs = pl.DataFrame(
        {
            "ods_code": ["OLD", "MID", "NEW"],
            "successors": ["MID|OTHER", "NEW", None],
        }
    )

    assert successor_anchors(orgs) == {"OLD": "NEW", "MID": "NEW", "NEW": "NEW"}


def test_organisation_change_groups_keep_predecessors_with_rows() -> None:
    groups = organisation_change_groups(organisations(), monthly_products())

    assert groups == [("AAA", ["DDD"])]


def test_inconsistent_product_counts_flags_a_low_submitted_month() -> None:
    orgs = organisations()
    months = [date(2019, month, 1) for month in range(1, 7)]
    steady = pl.DataFrame(
        {
            "ods_code": ["AAA"] * 6,
            "year_month": months,
            "n_products": [100, 100, 10, 100, 100, 100],
        }
    )
    mild = pl.DataFrame(
        {
            "ods_code": ["DDD"] * 6,
            "year_month": months,
            "n_products": [100, 100, 40, 100, 100, 100],
        }
    )
    aggregated = pl.concat([steady, mild])

    flagged = inconsistent_product_counts(
        orgs,
        aggregated,
        date(2019, 1, 1),
        date(2019, 6, 1),
    )

    assert flagged.get_column("ods_code").to_list() == ["AAA"]
    assert flagged.get_column("low_months").to_list() == ["March 2019"]
    assert flagged.get_column("median_products").to_list() == [100]
