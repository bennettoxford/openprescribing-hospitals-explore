# Analysis name

Replace this file when you copy `_template`.

## Directory layout

```text
.
├── README.md          # this file
├── index.qmd          # published report
├── *.py               # fetch, transform, and test scripts
└── data/              # local inputs and outputs (gitignored)
```

## Scripts

- Describe each script in one sentence.

## Outputs

- List files written under `data/` and the rendered report.

## How to run

From the repository root:

```shell
uv sync
uv run pytest analyses/YYYY-MM-short-name/
uv run quarto render analyses/YYYY-MM-short-name/index.qmd
```
