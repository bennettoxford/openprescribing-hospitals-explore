from datetime import date

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import polars as pl
from summarise import (
    chart_groups,
    consecutive_ranges,
    has_successor,
    next_month,
    positive_median,
    product_series,
    submitted_months,
    trust_name,
)

SUCCESSOR_COLOUR = "#1f4e9a"
PREDECESSOR_COLOUR = "#8c8c8c"
PROVISIONAL_COLOUR = "#f4d7a1"
PROVISIONAL_LABEL = "Shaded months are provisional"
LOW_COUNT_COLOUR = "#9b2c2c"


def _format_time_axis(ax: plt.Axes, start: date, end: date) -> None:
    ax.set_xlim(start, next_month(end))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlabel("Month")
    ax.grid(True, color="#e5e5e5", linewidth=0.6)
    ax.set_axisbelow(True)


def plot_submission_timeline(
    organisations: pl.DataFrame,
    monthly_products: pl.DataFrame,
    start: date,
    end: date,
    codes: list[str],
    pool: pl.DataFrame | None = None,
    provisional_start: date | None = None,
) -> plt.Figure:
    """Plot months with a submission.

    Trusts that share a successor or predecessor are drawn together. The
    successor is the first row in the group. A predecessor is grey.
    """
    groups = chart_groups(codes, pool if pool is not None else organisations)
    rows = [code for group in groups for code in group]
    group_ids = [index for index, group in enumerate(groups) for _ in group]
    ys = _group_positions(group_ids)
    fig, ax = plt.subplots(figsize=(11, max(3.2, 0.42 * len(rows) + 1.2)))
    labels: list[str] = []
    for code, y, group_id in zip(rows, ys, group_ids, strict=True):
        predecessor = has_successor(organisations, code)
        colour = PREDECESSOR_COLOUR if predecessor else SUCCESSOR_COLOUR
        name = trust_name(organisations, code)
        labels.append(f"    {name}" if predecessor else name)
        ranges = _presence_ranges(monthly_products, code, start, end)
        for range_start, range_end in ranges:
            left = mdates.date2num(range_start)
            width = mdates.date2num(next_month(range_end)) - left
            ax.barh(
                y,
                width=width,
                left=left,
                height=0.28,
                color=colour,
                align="center",
            )
        if len(groups[group_id]) > 1 and code == groups[group_id][0]:
            members = [
                ys[index] for index, item in enumerate(group_ids) if item == group_id
            ]
            ax.axhspan(
                min(members) - 0.45,
                max(members) + 0.45,
                color="#eef3f8",
                zorder=0,
            )
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    for tick, code in zip(ax.get_yticklabels(), rows, strict=True):
        if has_successor(organisations, code):
            tick.set_color(PREDECESSOR_COLOUR)
    if ys:
        ax.set_ylim(min(ys) - 0.7, max(ys) + 0.7)
    _format_time_axis(ax, start, end)
    ax.grid(False)
    ax.tick_params(axis="y", length=0)
    return _finish_figure(fig, [ax], provisional_start, end)


def _group_positions(group_ids: list[int]) -> list[float]:
    """Return y positions. The first row is at the top, with a gap between groups."""
    if not group_ids:
        return []
    cursor = 0.0
    raw: list[float] = []
    for index, group_id in enumerate(group_ids):
        if index and group_id != group_ids[index - 1]:
            cursor += 0.85
        raw.append(cursor)
        cursor += 1
    top = raw[-1]
    return [top - value for value in raw]


def plot_product_counts(
    organisations: pl.DataFrame,
    monthly_products: pl.DataFrame,
    codes: list[str],
    start: date,
    end: date,
    provisional_start: date | None = None,
    low_share: float | None = None,
) -> plt.Figure:
    """Plot unique products per month, with a separate y-axis for each trust."""
    fig, axes = plt.subplots(
        len(codes),
        1,
        figsize=(11, 3.1 * len(codes)),
        sharex=True,
    )
    if len(codes) == 1:
        axes = [axes]
    for ax, code in zip(axes, codes, strict=True):
        _plot_series(ax, monthly_products, code, start, end, SUCCESSOR_COLOUR)
        ax.set_title(trust_name(organisations, code))
        ax.set_ylabel("Unique products")
        _finish_count_axis(ax)
        if low_share is not None:
            _mark_low_share(ax, monthly_products, code, start, end, low_share)
    _format_time_axis(axes[-1], start, end)
    for ax in axes[:-1]:
        ax.set_xlim(start, next_month(end))
        ax.grid(True, color="#e5e5e5", linewidth=0.6)
        ax.set_axisbelow(True)
    return _finish_figure(fig, list(axes), provisional_start, end)


def plot_merger_product_counts(
    organisations: pl.DataFrame,
    monthly_products: pl.DataFrame,
    start: date,
    end: date,
    groups: list[tuple[str, list[str]]],
    provisional_start: date | None = None,
) -> plt.Figure:
    """Plot successor trusts in blue and the selected predecessors in grey."""
    fig, axes = plt.subplots(
        len(groups),
        1,
        figsize=(11, max(3.4, 2.8 * len(groups))),
        sharex=True,
    )
    if len(groups) == 1:
        axes = [axes]
    for ax, (successor, predecessors) in zip(axes, groups, strict=True):
        for code in predecessors:
            _plot_series(ax, monthly_products, code, start, end, PREDECESSOR_COLOUR)
        _plot_series(ax, monthly_products, successor, start, end, SUCCESSOR_COLOUR)
        ax.set_title(trust_name(organisations, successor), fontsize=9)
        ax.set_ylabel("Unique products")
        _finish_count_axis(ax)
        _, top = ax.get_ylim()
        ax.set_ylim(0, top * 1.28)
        placed: list[tuple[float, float]] = []
        for code in [*predecessors, successor]:
            _label_series(
                ax,
                monthly_products,
                code,
                start,
                end,
                _short_trust_name(trust_name(organisations, code)),
                placed,
            )
    _format_time_axis(axes[-1], start, end)
    for ax in axes[:-1]:
        ax.set_xlim(start, next_month(end))
        ax.grid(True, color="#e5e5e5", linewidth=0.6)
        ax.set_axisbelow(True)
    return _finish_figure(fig, list(axes), provisional_start, end)


def _highlight_provisional(
    axes: list[plt.Axes],
    provisional_start: date | None,
    end: date,
) -> None:
    """Shade the provisional months on every panel."""
    if provisional_start is None or provisional_start > end:
        return
    for ax in axes:
        patch = ax.axvspan(
            provisional_start,
            next_month(end),
            facecolor=PROVISIONAL_COLOUR,
            edgecolor="none",
            zorder=0.5,
        )
        patch.set_gid("provisional")


def _finish_figure(
    fig: plt.Figure,
    axes: list[plt.Axes],
    provisional_start: date | None,
    end: date,
) -> plt.Figure:
    """Shade provisional months, then return one closed figure."""
    _highlight_provisional(axes, provisional_start, end)
    fig.tight_layout()
    if provisional_start is not None and provisional_start <= end:
        fig.suptitle(
            PROVISIONAL_LABEL,
            fontsize=9,
            color="#6b5420",
            ha="right",
            x=0.98,
        )
        fig.subplots_adjust(top=fig.subplotpars.top - 0.03)
    return _single_display(fig)


def _mark_low_share(
    ax: plt.Axes,
    monthly_products: pl.DataFrame,
    ods_code: str,
    start: date,
    end: date,
    low_share: float,
) -> None:
    """Draw the low-count threshold for one combined series."""
    values = [
        int(value)
        for value in product_series(monthly_products, ods_code, start, end)
        .filter(pl.col("n_products") > 0)
        .get_column("n_products")
        .to_list()
    ]
    if not values:
        return
    ax.axhline(
        low_share * positive_median(values),
        color=LOW_COUNT_COLOUR,
        linestyle="--",
        linewidth=0.8,
    )


def _finish_count_axis(ax: plt.Axes) -> None:
    """Include every series, and keep zero on the y-axis."""
    ax.relim()
    ax.autoscale_view()
    _, top = ax.get_ylim()
    ax.set_ylim(0, top)


def _short_trust_name(name: str) -> str:
    """Drop the common NHS trust suffix so a line label fits on the panel."""
    for suffix in (" NHS Foundation Trust", " NHS Trust"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _label_anchor(
    months: list[date],
    values: list[int],
) -> tuple[date, int] | None:
    """Return a point on the main part of a series."""
    positive = [
        (month, value) for month, value in zip(months, values, strict=True) if value > 0
    ]
    if not positive:
        return None
    peak = max(value for _, value in positive)
    strong = [(month, value) for month, value in positive if value >= 0.5 * peak]
    return strong[len(strong) // 2]


def _label_series(
    ax: plt.Axes,
    monthly_products: pl.DataFrame,
    ods_code: str,
    start: date,
    end: date,
    label: str,
    placed: list[tuple[float, float]],
) -> None:
    """Write the trust name above the main part of its line."""
    series = product_series(monthly_products, ods_code, start, end)
    anchor = _label_anchor(
        series.get_column("year_month").to_list(),
        [int(value) for value in series.get_column("n_products").to_list()],
    )
    if anchor is None:
        return
    month, value = anchor
    x_pos = float(mdates.date2num(month))
    x_start = float(mdates.date2num(start))
    x_end = float(mdates.date2num(next_month(end)))
    span = x_end - x_start
    if x_pos < x_start + 0.25 * span:
        align = "left"
    elif x_pos > x_end - 0.15 * span:
        align = "right"
    else:
        align = "center"
    _, top = ax.get_ylim()
    y_pos = float(value) + top * 0.045
    gap = top * 0.12
    direction = 1
    if y_pos > top * 0.9:
        y_pos = float(value) - gap
        direction = -1
    for _ in range(6):
        crowded = any(
            abs(x_pos - used_x) < 220 and abs(y_pos - used_y) < gap
            for used_x, used_y in placed
        )
        if not crowded:
            break
        y_pos += direction * gap
    y_pos = min(max(y_pos, top * 0.03), top * 0.94)
    placed.append((x_pos, y_pos))
    ax.annotate(
        label,
        xy=(month, value),
        xytext=(month, y_pos),
        fontsize=7.5,
        color="#243044",
        ha=align,
        va="bottom" if y_pos >= value else "top",
        annotation_clip=True,
        arrowprops={"arrowstyle": "-", "color": "#243044", "lw": 0.4},
        bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85},
    )


def _plot_series(
    ax: plt.Axes,
    monthly_products: pl.DataFrame,
    ods_code: str,
    start: date,
    end: date,
    colour: str,
) -> None:
    series = product_series(monthly_products, ods_code, start, end)
    ax.plot(
        series.get_column("year_month").to_list(),
        series.get_column("n_products").to_list(),
        color=colour,
        linewidth=1.4,
    )


def _single_display(fig: plt.Figure) -> plt.Figure:
    """Return the figure once. An open figure is also emitted at the end of a cell."""
    plt.close(fig)
    return fig


def _presence_ranges(
    monthly_products: pl.DataFrame,
    ods_code: str,
    start: date,
    end: date,
) -> list[tuple[date, date]]:
    months = submitted_months(monthly_products, ods_code, start, end)
    return consecutive_ranges(months)
