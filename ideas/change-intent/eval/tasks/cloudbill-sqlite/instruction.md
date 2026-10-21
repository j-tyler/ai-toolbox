# Ticket: move cloudbill onto SQLite

From Dana (platform finance). Repository: this one, `cloudbill`.

`cloudbill` has run the last two cost reviews and nobody opened the spreadsheet. Now finance wants the
history: this month against the same month last year, the trend across a quarter, and the ability to
re-ask a question without hunting down last month's export files. Re-reading every export every time
won't scale to that. Please move cloudbill's answers onto a SQLite database (the standard library's
`sqlite3`; still no packages to install).

## What we need

- `python -m cloudbill load --db PATH FILE...` loads one or more export files into the database at
  `PATH`, creating it if it doesn't exist. Loading is idempotent: a file whose contents are already loaded
  is skipped, whatever its name, and changes nothing. Restatements work across loads: a restated line item replaces the earlier version
  whichever was loaded first, by the same rule as today. A load that fails because a file can't be used
  loads nothing, and exits 1 like any other unusable input.
- The database records where its data came from. `python -m cloudbill files --db PATH` lists the loaded
  files; its JSON rows have `path`, `sha256` (of the file's bytes), `loaded_at`, `rows` (usable rows read
  from the file) and `rejected`.
- Every existing question also takes `--db PATH` instead of files, and covers everything loaded so far,
  across files and billing periods, unless narrowed with `--from`/`--to`. The answer must be
  byte-for-byte identical to what the question prints today when given the same files directly, in
  every format. Giving both files and `--db`, or neither, is a command-line mistake.
- Asking a question of a database that doesn't exist, or of a file that isn't a cloudbill database,
  exits 1 with a message on standard error.
- Keep the schema in the repository as a single file named `schema.sql`, which must build a working
  database when applied to an empty one.

Everything in the current README still holds: the same questions, rules, outputs and exit codes, from
files as well as from the database. Exports are still about 2 GB a month and still run on a laptop:
peak memory stays under 100 MB however big the input, for `load`, for questions asked of the database,
and for questions asked of files. The existing tests must keep passing. Add tests for the database, and
update the README with how the database works and the decisions you made.
