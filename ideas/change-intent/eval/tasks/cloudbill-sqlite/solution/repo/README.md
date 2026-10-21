# cloudbill

Command-line answers for the monthly cloud cost review, computed from the provider's billing export.

```
python -m cloudbill load --db bill.db sample/*.csv
python -m cloudbill costs --by service --db bill.db
python -m cloudbill mom --by account --format json --db bill.db
python -m cloudbill files --db bill.db
python -m cloudbill rejects sample/*.csv            # straight from files works as before
```

Questions: `costs --by account|service|tag:<key>`, `daily`, `top --by account|service|resource|tag:<key>
[-n N]`, `untagged --tag <key>`, `credits`, `mom [--by ...]`, `daily-stats`, `rejects`. Each takes
`--from`/`--to` (inclusive UTC usage days) and `--format text|json|csv`, and either one or more export
files or `--db PATH`. `load --db PATH FILE...` loads exports into a SQLite database and `files --db PATH`
lists what it holds. Exit codes: 0 answered (rejected rows are reported, not fatal), 1 an input file or
the database cannot be used at all, 2 a command-line mistake.

## The billing export

The provider drops one CSV per billing period into the billing bucket, and a fresh copy of the current
period every night. One row per line item:

| Column | Meaning |
| --- | --- |
| `line_item_id` | The provider's id for the line item. |
| `billing_period` | `YYYY-MM` of the invoice the line belongs to. |
| `account_id` | 12-digit account id. |
| `account_name` | The account's display name at export time. |
| `service` | The service that was billed. |
| `region` | Region code, blank for account-level lines. |
| `usage_type` | The provider's usage type code. |
| `resource_id` | The resource that was billed, blank for account-level lines. |
| `usage_start`, `usage_end` | Usage window in UTC, ISO 8601. |
| `usage_start_local` | `usage_start` in the payer account's local time zone. |
| `usage_amount`, `usage_unit` | How much was used, and of what. |
| `unblended_cost` | Cost of the line, four decimal places. |
| `currency` | Currency code of the cost. |
| `line_item_type` | `Usage`, `Credit`, `Refund`, `Tax` or `Fee`. |
| `last_updated` | When the provider last wrote this line item, UTC. |
| `tag:<key>` | One column per activated cost-allocation tag, e.g. `tag:team`. |
| `description` | Free text from the provider. |

`sample/` has the August 2026 export and the September 2026 export as it stood on the 18th.

## Decisions

**Reading.** Columns are found by name (case and surrounding spaces ignored), so their order and the
set of tag columns may differ between files; a file without `line_item_id`, `account_id`, `service`,
`usage_start`, `unblended_cost`, `currency` or `line_item_type` is not a billing export (exit 1). Only
`usage_start` decides the day; `usage_start_local` is ignored. Timestamps without a zone are UTC.

**Encodings.** Files are read as UTF-8, with or without a byte-order mark. Bytes that are not valid
UTF-8 become U+FFFD instead of stopping the run; that can only make a row unusable (and so rejected) or
change free text. Line endings may be `\n` or `\r\n`, and quoted fields may contain commas and line
breaks. Line numbers in `rejects` are physical lines where the row starts, the header being line 1.

**What is accepted.** Surrounding whitespace is ignored everywhere. A cost may carry thousands
separators (`1,234.5600`), a leading `$`, or accounting parentheses for a negative (`(3.20)`). Line item
types and currencies are case-insensitive. Services are grouped case-insensitively and shown in their
most common spelling (ties: alphabetically first). An account is shown with the name on its most recent
usage. A blank tag and an absent tag column are both untagged. Blank lines are skipped, not rejected.

**What is rejected,** with the reason in `rejects`: a different number of fields from the header; no
line item id; a missing or unparseable usage start; a cost that is not a finite number (`#VALUE!`,
`12,34`); a line item type other than usage, credit, refund, tax or fee; any currency other than USD
(including blank). The rejected count in every output covers the whole input, whatever the date range.

**Duplicates and restatements.** Line items are identified by `line_item_id`. When an id appears more
than once among the usable rows, across every file given, the row with the latest `last_updated` wins
(a missing `last_updated` is older than any); on a tie the row later in the input wins (later file
on the command line, then later line). Exact duplicate rows therefore count once. Rejected rows never
take part, so a broken restatement leaves the earlier version standing. The result does not depend on
the order of files on the command line except through that tie rule.

**Memory.** The input is read twice and never held. The first pass validates files, collects rejected
rows and writes a 64-bit hash of every id into small sorted runs on disk, which are merged to find the
ids that repeat; the second pass streams every row whose id is unique and holds only the repeated ones
until it knows which version wins. Peak memory is about 40 MB on a 600,000-row export and grows with the
number of restated line items (and rejected rows, which `rejects` must list), not with the size of the
export. All question state is per group or per day.

**Rounding.** Sums are exact (decimal arithmetic on the export's four places). JSON numbers and CSV
values keep four decimal places; text rounds money half-up to cents, with thousands separators.
`change_pct` is `change / |previous net| * 100`, rounded half-even to two places, so a fall is always
negative. Rows and keys are always in a fixed order, so output is byte-for-byte reproducible.

**Months.** `mom` lists every calendar month from the first to the last usage day in the selected data,
for every group, with a zero net where a group had nothing that month. A month is `partial` when the
data starts after its first day or ends before its last day.

**Percentiles.** `daily-stats` sums each account's lines per UTC day, over the days on which the account
has any line, then takes the median and the 90th percentile by linear interpolation between closest
ranks (the spreadsheet `PERCENTILE.INC` rule; the median is the usual median). `days` is the number of
such days.

**Output.** JSON: `question`, the options used, `rows`, `total` (for `costs`), `rejected_rows`. CSV: a
header row of the JSON row fields, then the rows, then a final comment line `# rejected_rows: N`. A
group with no value (untagged, no resource) has a null key in JSON, an empty one in CSV, and shows as
`(untagged)` or `(none)` in text.

## The database

Answers come from SQLite (standard library `sqlite3`). The schema is `cloudbill/schema.sql`; `load`
applies it to a new database, and applying it again is harmless.

- `load` reads each file row by row, exactly as before (same acceptance and rejection rules), and
  upserts every usable row: the stored version of a line item is replaced only by a newer one (latest
  `last_updated`, then later file, then later line), so restatements resolve the same way whatever
  order files are loaded in, across any number of loads. Rejected rows are stored with their file and
  line.
- A file is identified by the SHA-256 of its bytes. Loading a file that is already in the database (by
  any name) reports `already loaded` and changes nothing. A newer nightly copy of the current month is a
  different file: it loads, and its restatements win. Rejected rows belong to the file they were read
  from, so a broken row present in two nightly copies is listed (and counted) once per copy.
- One `load` command is one transaction: if any file in it cannot be used, nothing from that command is
  loaded.
- Provenance: `files` lists every loaded file with its path as given, hash, load time and row counts;
  every stored line item records the file and line its current version came from.
- A question asked of the database covers everything loaded, across files and billing periods, unless
  `--from`/`--to` narrow it. Answering from files loads them into a temporary on-disk database first and
  then runs the same queries, so the two give byte-identical output.
- Costs are stored as exact decimal text and summed in Python, not as SQLite floating point, so nothing
  is lost to rounding. Memory stays bounded: rows stream in and out, and SQLite pages to disk.

## Development

Python 3.11 or later, standard library only. Run the tests with `python -m pytest -q`.

Layout: `export.py` reads and validates rows, `db.py` and `schema.sql` hold the database, `questions.py`
computes each answer, `render.py` formats it, `cli.py` wires them together. `resolve.py`, the two-pass
in-memory restatement resolver the tool used before the database, is no longer on the command path; it
is kept, with its tests, as the specification the database's upsert rule was checked against.
