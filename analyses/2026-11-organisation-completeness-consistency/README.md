# Organising organisations: data completeness and consistency

Where monthly submissions have gaps, and where the number of products changes. This report updates the February 2025 Organising Organisations posts on data completeness and data consistency. Trusts with no SCMD rows are excluded.

## Directory layout

```text
.
├── README.md
├── index.qmd
├── fetch_data.py
├── summarise.py
├── charts.py
├── test_summarise.py
├── test_charts.py
├── sql/
│   ├── organisations.sql
│   ├── monthly_products.sql
│   ├── aggregated_products.sql
│   └── data_status.sql
└── data/
    ├── organisations.csv
    ├── monthly_products.csv
    ├── aggregated_products.csv
    └── data_status.csv
```

## Scripts

- `fetch_data.py` reads organisations, monthly product counts, the combined successor product counts, and the finalised or provisional month range from BigQuery.
- `summarise.py` selects the trusts expected in the SCMD, describes gaps in their submissions, and flags product counts that fall below 25% of the trust's median month after predecessors roll into the successor.
- `charts.py` draws the submission timeline, the combined product-count charts, and one panel for each predecessor group.

## Outputs

| File | Source | Contents |
| --- | --- | --- |
| `data/organisations.csv` | BigQuery `ods` | One row per ORD organisation, with successor codes and open and close dates |
| `data/monthly_products.csv` | BigQuery `scmd_processed` | One row per trust-month with at least one product of positive quantity |
| `data/aggregated_products.csv` | BigQuery `scmd_processed` | Distinct VMP counts after each predecessor rolls into its first successor |
| `data/data_status.csv` | BigQuery `scmd_data_status` | First and last month for finalised and provisional data |
| `_site/analyses/2026-11-organisation-completeness-consistency/index.html` | `quarto render` | The published report |

The CSV files are not in git.

## How to run

From the repository root. `fetch_data.py` needs BigQuery credentials in `bq-service-account.json`.

```shell
uv sync
uv run pytest analyses/2026-11-organisation-completeness-consistency/
uv run analyses/2026-11-organisation-completeness-consistency/fetch_data.py
uv run quarto render analyses/2026-11-organisation-completeness-consistency/index.qmd
```

`index.qmd` reads the CSV files in `data/`. Run `fetch_data.py` again before you render if you want a newer extract. Read the findings again after a refresh. Some sentences describe patterns in the current extract.
