# Brief: turn ledger into a budgeting tool

`ledger` is a small command-line tool, in this repository, that tracks personal spending in a CSV file. Today it can only record a transaction and list transactions. We want to turn it into something a person can actually budget with. They should be able to set a monthly spending limit per category and see at any time how each category is tracking against its limit. They should be able to record an expense that repeats, such as rent or a subscription, once, and have the tool create the individual transactions on demand without ever creating the same occurrence twice. They should be able to import the CSV export from their bank, telling the tool which columns hold the date and amount, without ending up with duplicate transactions when they import an overlapping export next month. And they should be able to get a report for a month that shows what was spent per category and how that compares with the budget.

All of this must remain a pure standard-library Python tool. Everything it stores lives in plain text files next to the ledger file so a user can inspect and version them. Money stays integer cents end to end. Output is deterministic so it can be scripted. Every existing command, flag, and output format keeps working exactly as it does today, and the existing tests keep passing. Please add tests for everything you build.

## Interface contract

The tool's acceptance tests drive these commands through `ledger.cli.main(argv)` and check exit codes, standard output, and the files written. Anything not stated here is yours to decide, as long as the paragraphs above still hold.

Files, all in the same directory as the ledger file (not the current directory): `budgets.csv`, `recurring.csv`. The ledger file itself keeps its current format. Wherever a command offers `--format json`, lists in the JSON output use the same order as the text output.

### Budgets

- `ledger budget set <category> <amount> [--month YYYY-MM]` sets the limit for a category. Without `--month` it sets the default limit that applies to every month; with `--month` it sets a limit for that month only, which overrides the default for that month. Setting again replaces the previous value. Prints `budget <category> <amount> [for YYYY-MM]`, with the amount formatted as the tool already formats amounts, and exits 0.
- `ledger budget status --month YYYY-MM [--format text|json]` shows each budgeted category for that month. Text output is one line per category, sorted by category name: `<category> <spent>/<limit> remaining <remaining>`, with ` OVER` appended when spent exceeds limit. Spent is the sum of the month's transactions in that category; `remaining` is limit minus spent, negative when over. With no budgets set the output is empty. JSON output is a list of objects with keys `category`, `limit_cents`, `spent_cents`, `remaining_cents`, `over` (boolean). Exit code is 0.

### Recurring transactions

- `ledger recur add --amount <amount> --category <category> --every monthly|weekly --start YYYY-MM-DD [--until YYYY-MM-DD] [--note <text>]` records a recurring rule and prints `recurring #<n> ...` where `<n>` is the rule's id, exit 0. Rule ids start at 1 and increase by one.
- `ledger recur list` prints one line per rule, in id order, starting with `#<n>`.
- `ledger recur apply --through YYYY-MM-DD` creates one ledger transaction for every occurrence of every rule that falls on or after the rule's start, on or before `--through`, and on or before the rule's `--until` if set, and that has not already been created by an earlier `apply`. Running `apply` again with the same or an earlier date creates nothing. A monthly rule that starts on the 31st falls on the last day of shorter months. The created transactions carry the rule's amount, category, and note. Prints `applied <count>` and exits 0.

### Import

- `ledger import <path> --date-col <name> --amount-col <name> [--note-col <name>] [--category <category>] [--date-format <strptime format>] [--negate] [--format text|json]` reads a CSV with a header row. `--date-format` defaults to ISO `YYYY-MM-DD`. `--negate` flips the sign of every amount, for banks that export spending as negative numbers. `--category` defaults to `imported`. A row is a duplicate, and is skipped, when a transaction with the same date, amount, and note already exists in the ledger or appeared earlier in the same file. Text output is `imported <n> skipped <m>`; JSON output is `{"imported": n, "skipped": m}`. Exit 0 on success; exit 2 with a message on standard error if a named column is missing, and in that case the ledger is left unchanged.

### Report

- `ledger report --month YYYY-MM [--format text|json]`. Text output: one line per category with spending in that month, sorted by category name, `<category> <spent>`, then a final line `total <amount>`. Categories that have a budget for the month also show ` of <limit>` after the spent amount. JSON output is an object with `month`, `total_cents`, and `categories`, a list of objects with `category`, `spent_cents`, and `limit_cents` (null when there is no budget). Exit 0.
