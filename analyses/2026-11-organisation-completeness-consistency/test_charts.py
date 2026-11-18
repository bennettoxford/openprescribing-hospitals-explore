import matplotlib

matplotlib.use("Agg", force=True)

from datetime import date  # noqa: E402

import charts  # noqa: E402
import polars as pl  # noqa: E402


def organisations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ods_code": ["AAA", "DDD"],
            "ods_name": ["Alpha NHS Trust", "Delta NHS Trust"],
            "successors": [None, "AAA"],
            "ultimate_successors": [None, "AAA"],
            "predecessors": ["DDD", None],
            "legal_closed_date": [None, None],
            "operational_closed_date": [None, None],
            "legal_open_date": [date(2010, 4, 1), date(2010, 4, 1)],
            "operational_open_date": [None, None],
        }
    )


def monthly_products() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ods_code": ["AAA", "DDD"],
            "year_month": [date(2019, 1, 1), date(2019, 1, 1)],
            "n_products": [10, 4],
        }
    )


def test_charts_return_one_figure_each() -> None:
    orgs = organisations()
    monthly = monthly_products()
    start = date(2019, 1, 1)
    end = date(2019, 3, 1)

    timeline = charts.plot_submission_timeline(
        orgs,
        monthly,
        start,
        end,
        codes=["AAA", "DDD"],
    )
    counts = charts.plot_product_counts(orgs, monthly, ["AAA"], start, end)
    mergers = charts.plot_merger_product_counts(
        orgs,
        monthly,
        start,
        end,
        groups=[("AAA", ["DDD"])],
    )

    assert len(timeline.axes) == 1
    assert len(counts.axes) == 1
    assert len(mergers.axes) == 1
    assert timeline.axes[0].get_xlabel() == "Month"
    low = charts.plot_product_counts(
        orgs,
        monthly,
        ["AAA"],
        start,
        end,
        low_share=0.25,
    )

    assert counts.axes[0].get_ylabel() == "Unique products"
    assert len(low.axes[0].get_lines()) == 2
    assert mergers.axes[0].get_ylim()[1] >= 10
    merger_labels = [text.get_text() for text in mergers.axes[0].texts]
    assert "Alpha" in merger_labels
    assert "Delta" in merger_labels
    assert all(patch.get_gid() != "provisional" for patch in timeline.axes[0].patches)


def test_provisional_window_is_shaded_on_every_panel() -> None:
    orgs = organisations()
    monthly = monthly_products()
    start = date(2019, 1, 1)
    end = date(2019, 6, 1)
    provisional = date(2019, 4, 1)

    counts = charts.plot_product_counts(
        orgs,
        monthly,
        ["AAA", "DDD"],
        start,
        end,
        provisional_start=provisional,
    )

    assert len(counts.axes) == 2
    for ax in counts.axes:
        shaded = [patch for patch in ax.patches if patch.get_gid() == "provisional"]
        assert len(shaded) == 1
    assert charts.PROVISIONAL_LABEL in [text.get_text() for text in counts.texts]
