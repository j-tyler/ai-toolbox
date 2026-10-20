# ledger

A tiny command-line tool for tracking personal spending in a CSV file.

```
python -m ledger add --date 2026-10-01 --amount 12.50 --category groceries --note "market"
python -m ledger list --month 2026-10
```

The ledger file is `ledger.csv` in the current directory, or the path given by
`--file` or the `LEDGER_FILE` environment variable. Amounts are stored as
integer cents. The tool uses only the Python standard library.

Run the tests with `python -m pytest -q`.
