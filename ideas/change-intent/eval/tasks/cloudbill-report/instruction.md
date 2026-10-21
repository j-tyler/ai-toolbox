# Ticket: build cloudbill, the tool for the monthly cost review

From Dana (platform finance). Repository: this one, `cloudbill`. It has a README describing the billing
export and a sample of the real thing under `sample/`, and no code yet.

Every month, the week before the cost review with the team leads, Sam and I export the cloud bill and
spend most of two days in a spreadsheet answering the same questions. Last quarter we got one badly
wrong: we compared half of September with all of August and told the data team their spend had halved.
I'd like `cloudbill` to answer these questions from the command line, the same way every time, so the
review starts from numbers nobody has to re-derive.

## The questions

Run as `python -m cloudbill <question> [options] FILE...`, over one or more export files at once (we
usually pass a month or two):

- `costs --by account|service|tag:<key>`: cost per account, per service, or per value of a tag (for
  example `--by tag:team`), with charges and credits shown separately, and the net.
- `daily`: the net cost of each day.
- `top --by account|service|resource|tag:<key> [-n N]`: the N biggest (default 10), largest net first.
- `untagged --tag <key>`: for each account, how much of its net cost has no value for that tag, next to
  its total.
- `credits`: credits and refunds per account, kept apart from each other.
- `mom [--by account|service|tag:<key>]`: month over month: each month's net cost and the change from
  the month before, in money and as a percentage.
- `daily-stats`: for each account, the median and the 90th percentile of its daily net cost. We use it
  to spot accounts whose spend is spiky rather than steady.
- `rejects`: every row the tool could not use, with the file, the line the row starts on, and why.

Every question takes `--from YYYY-MM-DD` and `--to YYYY-MM-DD` (both inclusive; default: everything in
the files) and `--format text|json|csv` (default text). Text is for people; JSON and CSV feed the
dashboard scripts and the spreadsheet we still keep.

## Rules we agreed with finance

- A line belongs to the UTC date its usage starts (`usage_start`); months are calendar months of that
  date.
- Charges are usage, tax and fee lines. Credits are credit and refund lines, which are negative in the
  export. Net is charges plus credits.
- An account is its account id. Names get changed; ids don't.
- A service is the same service however its name is capitalised.
- A tag that is blank, or whose column isn't in the file at all, counts as untagged.
- The export sometimes restates a line item: the same `line_item_id` appears again with a later
  `last_updated`. The later version replaces the earlier one wherever the two appear, including in
  different files.
- Everything we pay is in USD. A line in any other currency is a data problem we chase with the vendor:
  reject it, don't convert it.
- `mom` has to say when a month is only partly covered by the data. That was last quarter's mistake.

## Bad data

Exports are messy. Be liberal with formatting that a person reading the file would read the same way.
Reject a row only when it can't be used: it has the wrong number of fields, no line item id, no usable
usage start, a cost that isn't a number, a line item type other than the five, or a currency other than
USD. A rejected row is never silently dropped: every output says how many rows were rejected, and
`rejects` lists them.

Exit codes: 0 when the question was answered, even if some rows were rejected; 1, with a message on
standard error and nothing on standard output, when an input file can't be used at all (missing,
unreadable, or not a billing export); 2 for a command-line mistake.

## Output

JSON output is one object with `rows` (a list) and `rejected_rows` (the count for the whole input,
whatever the date range); `costs` also has `total`, with `charges`, `credits` and `net`. Row fields:

| Question | Fields |
| --- | --- |
| `costs` | `key`, `charges`, `credits`, `net` (and `name` for `--by account`). Sorted by key; spend with no value for the grouping is a row whose `key` is null. |
| `daily` | `date`, `charges`, `credits`, `net`, in date order. |
| `top` | `key`, `net`. |
| `untagged` | `key` (the account id), `untagged`, `net`. |
| `credits` | `key` (the account id), `credit`, `refund`, `credits` (their sum). |
| `mom` | `key` (with `--by`), `month` (`YYYY-MM`), `net`, `change`, `change_pct`, `partial`. `change` and `change_pct` are null for the first month, and `change_pct` is null when the previous month's net is zero. |
| `daily-stats` | `key` (the account id), `days`, `median`, `p90`. |
| `rejects` | `file`, `line`, `reason`. |

CSV output has a header row with the same field names and one line per row. Text output is yours to
design, as long as it reads well in a terminal and shows the rejected-row count. How you round money is
up to you: pick a rule and apply it everywhere. The same input must always produce byte-for-byte the
same output.

## Constraints

- Pure Python standard library, 3.11 or later; nobody can install packages on the review machine.
- The full-org export is about 2 GB a month now and has to run on a laptop: stream it, and keep peak
  memory under 100 MB however big the input is.
- Write down in the README the decisions this ticket leaves to you: how you handle encodings, how you
  resolve duplicates and restatements, how you round, and how you compute the percentile.
- Tests, please. I want to be able to change this later without being scared of it.
