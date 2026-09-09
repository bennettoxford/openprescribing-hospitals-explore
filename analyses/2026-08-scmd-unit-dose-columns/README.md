# Comparing the unit dose reported in the SCMD to the unit dose calculated using the dm+d

A comparison of the unit dose quantity newly reported in the provisional Secondary Care Medicines Data (SCMD) extract with the unit dose calculated from the dm+d in the OpenPrescribing Hospitals data.


## Directory layout

```text
.
├── README.md
├── index.qmd                 # Quarto report
├── fetch_data.py             # download the June 2026 provisional SCMD CSV
├── fetch_oph_data.py         # query OpenPrescribing Hospitals vmp_data
├── fetch_vmp_rows.sql        # BigQuery used by fetch_oph_data.py
├── compare_unit_doses.py     # join the two sources and classify matches
├── test_fetch_data.py
├── test_fetch_oph_data.py
├── test_compare_unit_doses.py
└── data/
    ├── scmd_provisional_202606.csv
    ├── vmp_data.csv
    └── unit_dose_comparison.csv
```

## Scripts

- `fetch_data.py` downloads the June 2026 provisional SCMD extract from the NHSBSA Open Data Portal if the local CSV is missing. Use `--force` to download again.
- `fetch_oph_data.py` reads unique VMP codes from that extract and queries `ebmdatalab.scmd_pipeline.vmp_data` for `vmp_code`, `udfs`, `udfs_uom`, `unit_dose_uom`, and `df_ind`.
- `fetch_vmp_rows.sql` is the BigQuery for that fetch.
- `compare_unit_doses.py` keeps one row per VMP from the extract, checks that implied `udfs` is the same on every organisation row, takes one row's value when it is, and compares the UDFS unit of measure, UDFS value, and unit dose unit of measure with OpenPrescribing Hospitals. It also checks if the provisional UDFS and unit dose units are the same.

## Outputs

All CSVs are under `data/` and are not in git.

| File | Source | Contents |
| --- | --- | --- |
| `data/scmd_provisional_202606.csv` | NHSBSA download | Organisation-month-VMP rows, including the new unit dose columns |
| `data/vmp_data.csv` | BigQuery `vmp_data` | One row per VMP in the extract that exists in OpenPrescribing Hospitals |
| `data/unit_dose_comparison.csv` | `compare_unit_doses.py` | One row per VMP: unit of measure status, `udfs` status, and the values used in the report |
| `_site/analyses/2026-08-scmd-unit-dose-columns/index.html` | `quarto render` | The published report |

## How to run

From the repository root. You need network access for the first SCMD download, and BigQuery credentials for `fetch_oph_data.py`.

```shell
uv sync
uv run pytest analyses/2026-08-scmd-unit-dose-columns/
uv run analyses/2026-08-scmd-unit-dose-columns/fetch_data.py
uv run analyses/2026-08-scmd-unit-dose-columns/fetch_oph_data.py
uv run analyses/2026-08-scmd-unit-dose-columns/compare_unit_doses.py
uv run quarto render analyses/2026-08-scmd-unit-dose-columns/index.qmd
```

`index.qmd` reads `data/unit_dose_comparison.csv`. Rebuild that file before you render if you change the comparison.
