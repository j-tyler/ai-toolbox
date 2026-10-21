# Changelog

## 0.2.0 (2026-10-20)

- Answers come from a SQLite database. New `load --db PATH FILE...` (idempotent, restatements across
  loads, file provenance) and `files --db PATH`; every question takes `--db PATH` instead of files and
  answers byte-identically either way. Schema in `cloudbill/schema.sql`.

## 0.1.0 (2026-10-01)

- The `cloudbill` command: `costs`, `daily`, `top`, `untagged`, `credits`, `mom`, `daily-stats` and
  `rejects`, over one or more billing exports, as text, JSON or CSV.
- Restatements resolved across files in bounded memory; rejected rows reported, never dropped.
- README: the decisions on encodings, restatements, rounding and percentiles.

## 0.0.2 (2026-09-18)

- Added `sample/`: the August 2026 export and September 2026 so far, from the billing bucket, account
  names scrubbed.
- README: described the export columns.

## 0.0.1 (2026-09-04)

- Repository created for the cost-review tool, with packaging metadata and a README stating what it is
  for.
