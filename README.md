# openprescribing-hospitals-explore

Small, one-off analyses related to [OpenPrescribing Hospitals](https://hospitals.openprescribing.net/).

Each analysis is a Quarto report with optional Python code. The reports are
rendered into a website and deployed to GitHub Pages by CI.

## Setup

The project uses [uv](https://docs.astral.sh/uv/) for package management and
[Quarto](https://quarto.org/) for rendering.

```shell
uv sync
```

## Add an analysis

Copy `analyses/_template/` to a new folder under `analyses/` named
`YYYY-MM-short-name`, for example `2026-08-explore-data`.
See the "How to" page (`how-to.qmd`) for the full instructions.

## Render

The project sets `freeze: true`, so a full project render never executes code.
To refresh the results of a report, render it directly and commit the updated
`_freeze/` output.

```shell
# Render the full site from committed results
uv run quarto render

# Execute and refresh one report
uv run quarto render analyses/YYYY-MM-short-name/index.qmd
```

## Checks

```shell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

