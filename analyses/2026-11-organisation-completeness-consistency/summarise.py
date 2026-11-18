from datetime import date
from pathlib import Path

import polars as pl

SCMD_START = date(2019, 1, 1)
LOW_PRODUCT_SHARE = 0.25
MIN_SERIES_MONTHS = 6

DATE_COLUMNS = {
    "legal_closed_date": pl.Date,
    "operational_closed_date": pl.Date,
    "legal_open_date": pl.Date,
    "operational_open_date": pl.Date,
}


def load_extracts(
    data_dir: Path,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Read the organisation, monthly product, and data-status extracts."""
    organisations = pl.read_csv(
        data_dir / "organisations.csv",
        schema_overrides=DATE_COLUMNS,
        null_values=[""],
    )
    monthly_products = pl.read_csv(
        data_dir / "monthly_products.csv",
        schema_overrides={"year_month": pl.Date, "n_products": pl.Int64},
        null_values=[""],
    )
    data_status = pl.read_csv(
        data_dir / "data_status.csv",
        schema_overrides={"min_month": pl.Date, "max_month": pl.Date},
        null_values=[""],
    )
    return organisations, monthly_products, data_status


def period_bounds(data_status: pl.DataFrame) -> tuple[date, date, date]:
    """Return the first month, last month, and first provisional month."""
    start = data_status.get_column("min_month").min()
    end = data_status.get_column("max_month").max()
    provisional = data_status.filter(pl.col("file_type") == "provisional")
    provisional_start = provisional.get_column("min_month").min()
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError("data status has no months")
    if not isinstance(provisional_start, date):
        raise ValueError("data status has no provisional months")
    return start, end, provisional_start


def expected_trusts(organisations: pl.DataFrame) -> pl.DataFrame:
    """Return trusts with no closure date before the SCMD starts."""
    legal_closed = pl.col("legal_closed_date")
    closed_before_scmd = (legal_closed.is_not_null() & (legal_closed < SCMD_START)) | (
        pl.col("operational_closed_date").is_not_null()
        & (pl.col("operational_closed_date") < SCMD_START)
    )
    return organisations.filter(~closed_before_scmd).sort("ods_name")


def submitted_trusts(
    organisations: pl.DataFrame,
    monthly_products: pl.DataFrame,
) -> pl.DataFrame:
    """Return organisations with at least one positive-quantity month.

    A trust stays in this set when it has SCMD rows, including a trust whose
    recorded close date is before January 2019.
    """
    submitted = (
        monthly_products.filter(pl.col("n_products") > 0)
        .get_column("ods_code")
        .unique()
        .to_list()
    )
    return organisations.filter(pl.col("ods_code").is_in(submitted)).sort("ods_name")


def month_spine(start: date, end: date) -> list[date]:
    """Return each month from start to end, inclusive."""
    return pl.date_range(start, end, interval="1mo", eager=True).to_list()


def next_month(value: date) -> date:
    """Return the first day of the month after value."""
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _month_index(value: date) -> int:
    return value.year * 12 + value.month


def consecutive_ranges(months: list[date]) -> list[tuple[date, date]]:
    """Collapse sorted months into inclusive consecutive ranges."""
    if not months:
        return []
    ordered = sorted(months)
    ranges: list[tuple[date, date]] = []
    start = previous = ordered[0]
    for month in ordered[1:]:
        if _month_index(month) - _month_index(previous) == 1:
            previous = month
            continue
        ranges.append((start, previous))
        start = previous = month
    ranges.append((start, previous))
    return ranges


def submitted_months(
    monthly_products: pl.DataFrame,
    ods_code: str,
    start: date,
    end: date,
) -> list[date]:
    """Return months in which the trust has at least one product."""
    return (
        monthly_products.filter(
            (pl.col("ods_code") == ods_code)
            & (pl.col("year_month") >= start)
            & (pl.col("year_month") <= end)
            & (pl.col("n_products") > 0)
        )
        .sort("year_month")
        .get_column("year_month")
        .to_list()
    )


def gap_ranges(
    months: list[date],
    start: date,
    end: date,
) -> list[tuple[date, date]]:
    """Return consecutive months in the period with no submission."""
    present = set(months)
    missing = [month for month in month_spine(start, end) if month not in present]
    return consecutive_ranges(missing)


def product_series(
    monthly_products: pl.DataFrame,
    ods_code: str,
    start: date,
    end: date,
) -> pl.DataFrame:
    """Return one row per month. Months with no submission have zero products."""
    spine = pl.DataFrame({"year_month": month_spine(start, end)})
    series = monthly_products.filter(pl.col("ods_code") == ods_code).select(
        "year_month",
        "n_products",
    )
    return spine.join(series, on="year_month", how="left").with_columns(
        pl.col("n_products").fill_null(0)
    )


def positive_median(values: list[int]) -> int:
    """Return the upper middle value of a non-empty list."""
    ordered = sorted(values)
    return int(ordered[len(ordered) // 2])


def successor_anchors(organisations: pl.DataFrame) -> dict[str, str]:
    """Map each trust to the current trust that should hold its submissions.

    The current trust is the end of the successor chain. The chain uses the
    first successor code that is in this table. A trust with no such successor
    maps to itself.
    """
    known = {row["ods_code"]: row for row in organisations.iter_rows(named=True)}

    def anchor(code: str) -> str:
        seen: set[str] = set()
        current = code
        while current not in seen:
            seen.add(current)
            row = known[current]
            nxt = _linked_codes(row["successors"], set(known))
            if not nxt:
                return current
            current = nxt[0]
        return current

    return {code: anchor(code) for code in known}


def organisation_change_groups(
    organisations: pl.DataFrame,
    monthly_products: pl.DataFrame,
) -> list[tuple[str, list[str]]]:
    """Return each current trust and the predecessors that have SCMD rows.

    The successor is an expected trust. A predecessor is included when it has
    at least one product, including a predecessor that closed before 2019.
    """
    known = {row["ods_code"]: row for row in organisations.iter_rows(named=True)}
    submitted = set(
        monthly_products.filter(pl.col("n_products") > 0)
        .get_column("ods_code")
        .unique()
        .to_list()
    )
    groups: list[tuple[str, list[str]]] = []
    for row in expected_trusts(organisations).iter_rows(named=True):
        predecessors = [
            code
            for code in _linked_codes(row["predecessors"], set(known))
            if code in submitted
        ]
        if not predecessors:
            continue
        predecessors.sort(key=lambda code: known[code]["ods_name"])
        groups.append((row["ods_code"], predecessors))
    groups.sort(key=lambda group: known[group[0]]["ods_name"])
    return groups


def inconsistent_product_counts(
    organisations: pl.DataFrame,
    aggregated_products: pl.DataFrame,
    period_start: date,
    period_end: date,
    low_share: float = LOW_PRODUCT_SHARE,
) -> pl.DataFrame:
    """Return trusts with a submitted month far below the usual product count.

    The product count is already combined into the successor. A month is low
    when it has at least one product and the count is below `low_share` of the
    median submitted month. A month with no product is not low. A series with
    fewer than six submitted months is excluded.
    """
    names = {
        row["ods_code"]: row["ods_name"] for row in organisations.iter_rows(named=True)
    }
    rows: list[dict[str, object]] = []
    codes = aggregated_products.get_column("ods_code").unique().to_list()
    for code in codes:
        if code not in names:
            continue
        series = product_series(aggregated_products, code, period_start, period_end)
        submitted = series.filter(pl.col("n_products") > 0)
        if submitted.height < MIN_SERIES_MONTHS:
            continue
        values = [int(value) for value in submitted.get_column("n_products").to_list()]
        median = positive_median(values)
        low = submitted.filter(pl.col("n_products") < low_share * median).sort(
            "year_month"
        )
        if low.height == 0:
            continue
        low_months = low.get_column("year_month").to_list()
        rows.append(
            {
                "ods_code": code,
                "ods_name": names[code],
                "median_products": median,
                "min_products": int(min(low.get_column("n_products").to_list())),
                "n_low": low.height,
                "low_months": format_span_list(consecutive_ranges(low_months)),
            }
        )
    schema = {
        "ods_code": pl.String,
        "ods_name": pl.String,
        "median_products": pl.Int64,
        "min_products": pl.Int64,
        "n_low": pl.Int64,
        "low_months": pl.String,
    }
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(rows).sort(["n_low", "ods_name"], descending=[True, False])


def load_aggregated(data_dir: Path) -> pl.DataFrame:
    """Read the successor-level distinct product counts."""
    return pl.read_csv(
        data_dir / "aggregated_products.csv",
        schema_overrides={"year_month": pl.Date, "n_products": pl.Int64},
        null_values=[""],
    )


def trust_name(organisations: pl.DataFrame, ods_code: str) -> str:
    """Return the ODS name for one code."""
    names = organisations.filter(pl.col("ods_code") == ods_code).get_column("ods_name")
    if names.len() != 1:
        raise ValueError(f"expected one organisation for {ods_code}")
    return names[0]


def has_successor(organisations: pl.DataFrame, ods_code: str) -> bool:
    """Return true when ORD records a successor for the trust."""
    successors = organisations.filter(pl.col("ods_code") == ods_code).get_column(
        "successors"
    )
    if successors.len() != 1:
        raise ValueError(f"expected one organisation for {ods_code}")
    return bool(successors[0])


def _linked_codes(value: str | None, known: set[str]) -> list[str]:
    if not value:
        return []
    return [code for code in value.split("|") if code and code in known]


def chart_groups(codes: list[str], organisations: pl.DataFrame) -> list[list[str]]:
    """Group trusts that share a successor or predecessor.

    The first code in a related group is the successor. Predecessors follow it.
    A related trust is included even when its own history is complete.
    Trusts with no link in this organisation list stay in their own group,
    in the original order, after the related groups.
    """
    known = {row["ods_code"]: row for row in organisations.iter_rows(named=True)}
    families: dict[str, list[str]] = {}
    for code in codes:
        row = known.get(code)
        if row is None:
            continue
        successors = _linked_codes(row["successors"], set(known))
        predecessors = _linked_codes(row["predecessors"], set(known))
        if not successors and not predecessors:
            continue
        anchor = successors[0] if successors else code
        members = families.setdefault(anchor, [anchor])
        if code not in members:
            members.append(code)
        anchor_row = known[anchor]
        for predecessor in _linked_codes(anchor_row["predecessors"], set(known)):
            if predecessor not in members:
                members.append(predecessor)

    related_codes = {code for members in families.values() for code in members}
    related_groups = []
    for anchor, members in families.items():
        ordered = [anchor]
        ordered.extend(
            sorted(
                (code for code in members if code != anchor),
                key=lambda code: known[code]["ods_name"],
            )
        )
        related_groups.append(ordered)
    related_groups.sort(key=lambda group: known[group[0]]["ods_name"])

    alone = [[code] for code in codes if code not in related_codes]
    return related_groups + alone


def month_floor(value: date) -> date:
    """Return the first day of the month that contains value."""
    return date(value.year, value.month, 1)


def _recorded_dates(row: dict[str, object], *columns: str) -> list[date]:
    values: list[date] = []
    for column in columns:
        value = row[column]
        if isinstance(value, date):
            values.append(value)
    return values


def expected_window(
    row: dict[str, object],
    period_start: date,
    period_end: date,
) -> tuple[date, date] | None:
    """Return the months a trust should have a submission.

    The window starts at the SCMD start, or at the later open date when that
    is later. It ends at the latest SCMD month, or at the earlier close date
    when that is earlier. A trust with a close before its open has no window.
    """
    open_dates = _recorded_dates(row, "legal_open_date", "operational_open_date")
    close_dates = _recorded_dates(row, "legal_closed_date", "operational_closed_date")
    start = period_start
    if open_dates:
        start = max(period_start, month_floor(max(open_dates)))
    end = period_end
    if close_dates:
        end = min(period_end, month_floor(min(close_dates)))
    if end < start:
        return None
    return start, end


def incomplete_submissions(
    trusts: pl.DataFrame,
    monthly_products: pl.DataFrame,
    period_start: date,
    period_end: date,
) -> pl.DataFrame:
    """Return trusts that miss a month inside their open window."""
    rows: list[dict[str, object]] = []
    for row in trusts.iter_rows(named=True):
        window = expected_window(row, period_start, period_end)
        if window is None:
            continue
        start, end = window
        submitted = submitted_months(monthly_products, row["ods_code"], start, end)
        gaps = gap_ranges(submitted, start, end)
        if not gaps:
            continue
        expected_months = len(month_spine(start, end))
        rows.append(
            {
                "ods_code": row["ods_code"],
                "ods_name": row["ods_name"],
                "window_start": start,
                "window_end": end,
                "n_submitted": len(submitted),
                "n_expected": expected_months,
                "n_missing": expected_months - len(submitted),
                "missing_months": format_span_list(gaps),
            }
        )
    if not rows:
        return pl.DataFrame(
            schema={
                "ods_code": pl.String,
                "ods_name": pl.String,
                "window_start": pl.Date,
                "window_end": pl.Date,
                "n_submitted": pl.Int64,
                "n_expected": pl.Int64,
                "n_missing": pl.Int64,
                "missing_months": pl.String,
            }
        )
    return pl.DataFrame(rows).sort(["n_missing", "ods_name"], descending=[True, False])


def missing_trusts(
    trusts: pl.DataFrame,
    monthly_products: pl.DataFrame,
) -> pl.DataFrame:
    """Return expected trusts with no positive-quantity month."""
    positive = monthly_products.filter(pl.col("n_products") > 0)
    submitted = positive.get_column("ods_code").unique()
    return trusts.filter(~pl.col("ods_code").is_in(submitted.to_list())).sort(
        "ods_name"
    )


def format_month(value: date) -> str:
    """Return a month label such as January 2019."""
    return value.strftime("%B %Y")


def format_span(start: date, end: date) -> str:
    """Return one month, or a range of months."""
    if start == end:
        return format_month(start)
    return f"{format_month(start)} to {format_month(end)}"


def format_span_list(spans: list[tuple[date, date]]) -> str:
    """Join month ranges with commas and a final 'and'."""
    labels = [format_span(start, end) for start, end in spans]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " and " + labels[-1]
