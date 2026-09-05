# Reconcile a partial update and a known move

This authored maintenance fixture reuses the placed repository from
[`placement/expected/`](../placement/expected/). It tests maintenance after a
code change; `code.patch` is fixture setup, not a documentation-placement edit.
Use a disposable directory and run these commands from this examples folder:

```sh
cp -R placement/expected /tmp/order-maintenance
mv /tmp/order-maintenance/shop/models.py /tmp/order-maintenance/shop/records.py
git -C /tmp/order-maintenance apply "$PWD/maintenance/code.patch"
```

Choose a fresh destination if that directory exists. The patch adds `shipped`
and the guarded `ship_order`, updates the SQLite value constraint and imports,
and leaves documentation stale for the exercise. All stores are newly opened
in memory; no persistent-schema migration is demonstrated.

Give an agent that resulting repository, [`artifacts.md`](artifacts.md), the
known move above, and the [Placement Guide](../../placement-guide.md). Withhold
[`expected-documentation.patch`](expected-documentation.patch) until review.
That patch is an authored expected delta, not evidence that an agent made it.
Apply it only to a separate copy when inspecting the expected result.

| Check after placement | What must survive or change |
|---|---|
| Whole lifecycle | Keep creation, guarded pending-to-cancelled, and both rejection notes, although the incoming diagram omits them. Add guarded confirmed-to-shipped. |
| False absence avoidance | Do not mark confirmed or shipped terminal: current public guards do not prevent direct SQL with another valid status. |
| Known move | Repair the owner identifier, storage pointer, and README source link from models to records. Keep one full lifecycle above `shop.records.OrderStatus`. |
| Existing wording | Keep the synchronous flow, event pair, `writes: orders`, and supported lifecycle wording. The new table row does not require a second writes line. |
| Second pass | Apply the same partial input to the reconciled result. Expect no documentation edits; compare the entire result, not only duplicate map keys. |

The expected patch is small because preservation is a real part of the result.
Idempotence is an exercise expectation until a second placement pass is run;
applying a static patch twice is not a substitute for that check.
