# cloudbill

Command-line answers for the monthly cloud cost review, computed from the provider's billing export.

Nothing is built yet. This repository holds the description of the export the tool will read and a
sample of it.

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

## Sample

`sample/` has the August 2026 export and the September 2026 export as it stood on the 18th, taken from
the billing bucket with account names scrubbed. Use it to try things out; it is real enough to be
messy.

## Development

Python 3.11 or later, standard library only. Run the tests with `python -m pytest -q`.
