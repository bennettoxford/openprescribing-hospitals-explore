# AWaRe Data Integration and Mapping

A process to link the UK AWaRe antibiotic classification to dm+d, compare that list with the UKHSA translation table, and reconcile the differences.

## Directory layout

```text
.
├── README.md
├── index.qmd                  # comparison report
├── aware_vmp_list.py          # writes the final VMP list
├── test_aware_vmp_list.py
├── sql/                       # BigQuery read by aware_vmp_list.py
├── AWaRe_UK_2024_translation_table.csv  # UKHSA translation table read in section 2
├── aware_categories.csv       # antibiotic names and AWaRe categories
├── vtm_links.csv              # extra dm+d VTM names; the pipeline does not read this file
├── excluded_forms.csv         # form rules read by aware_vmp_list.py
└── data/                      # query caches and aware_vmp_list.csv (gitignored)
```

## Source files

These CSVs stay in this folder. They are not BigQuery tables.

| File | Rows | Contents |
| --- | --- | --- |
| `AWaRe_UK_2024_translation_table.csv` | 931 | UKHSA translation table. Section 2 reads this file. |
| `aware_categories.csv` | 101 | Antibiotic name, route, ATC route, 2019 category, 2024 category, and source. 90 rows come from the UKHSA website list. 11 rows were added after comparison with the UKHSA translation table. `aware_vmp_list.py` reads this file. The report builds the same list in memory and does not write this file. |
| `vtm_links.csv` | 37 | Extra VTM name and VTM id when the VTM name is not an exact match to the antibiotic. The report does not read this file. |
| `excluded_forms.csv` | 9 | dm+d form patterns to leave out. `aware_vmp_list.py` reads this file. `suffix` means the form description ends with the pattern. `exact` means the form description is equal to the pattern. |

## Scripts

`aware_vmp_list.py` writes the final VMP list. It reads `aware_categories.csv` and `excluded_forms.csv`. It reads `data/vtms.csv` and `data/vmp_forms.csv` when those files exist. It runs `sql/vtms.sql` and `sql/vmp_forms.sql` in BigQuery and writes those CSV files when they are missing.

`index.qmd` is the comparison report. It reads the UKHSA website and the translation table. It uses the same VTM and VMP CSV files. It writes `excluded_forms.csv`. It does not write `aware_categories.csv` or `data/aware_vmp_list.csv`.

## Outputs

| File | Contents |
| --- | --- |
| `data/vtms.csv` | VTM id and name from `sql/vtms.sql`. The report and the script read this file. They write it after a BigQuery query when the file is missing. It is not in git. |
| `data/vmp_forms.csv` | VMP rows, forms, and WHO routes from `sql/vmp_forms.sql`. The route column is `who_route_codes_for_ddd` from `scmd_pipeline.vmp_data`. The report and the script read this file. They write it after a BigQuery query when the file is missing. It is not in git. |
| `data/aware_vmp_list.csv` | Final VMP list. `aware_vmp_list.py` writes this file. It is not in git. |
| `_site/analyses/2026-09-aware-main-mapping/index.html` | The published report |

## How to run

From the repository root. You need BigQuery access through `bq-service-account.json`.

```shell
uv sync
uv run python analyses/2026-09-aware-main-mapping/aware_vmp_list.py
uv run pytest analyses/2026-09-aware-main-mapping/test_aware_vmp_list.py
```

The report also needs network access for the UKHSA page.

```shell
uv run quarto render analyses/2026-09-aware-main-mapping/index.qmd
```
