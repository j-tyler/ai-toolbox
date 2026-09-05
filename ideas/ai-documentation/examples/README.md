# Placement examples in practice

These small Python repositories illustrate the current [Placement Guide](../placement-guide.md):
keep a useful explanation together, extract independently meaningful facts,
omit a redundant redraw, and reconcile existing documentation. Python 3.10+
and its standard library are sufficient. No production infrastructure or
automatic documentation tooling is assumed.

## Inputs and expected placement

| Material | Role |
|---|---|
| [`placement/before/`](placement/before/) | Runnable undocumented baseline. Treat this directory as its own repository root. |
| [`placement/artifacts.md`](placement/artifacts.md) | Supplied intermediate document: raw scope metadata, state/sequence/packet diagrams, edge rows, glossary, and purpose notes. |
| [`placement/expected/`](placement/expected/) | Authored expected placement. Code tokens match the baseline; comments and Markdown demonstrate allowed homes. |

The inputs and expected result are authored fixtures, not captured output of a
generator or placement agent. They expose the evidence needed to reproduce the
placement and compare decisions. Different supported wording or selected root
navigation can be valid; behavior, ownership, qualifications, and direct routes
are the important comparison.

For a placement exercise, copy `placement/before/` to a fresh disposable directory
and give an agent that copy, `placement/artifacts.md`, and the Placement Guide.
Withhold `expected/` and this tour until the agent finishes. Review the result
against current code and the criteria below, then adjudicate differences.
Repeat placement on the result with unchanged inputs; expect no edits.
That second pass must actually run before calling the result idempotent.

## What changes at the reading location

| Decision | Expected result | Why it belongs there |
|---|---|---|
| Keep the lifecycle | [`shop/models.py`](placement/expected/shop/models.py) | Creation, confirmation, cancellation, guards and rejection notes stay together above `OrderStatus`; the writer points there. No terminal marker asserts more than the public guards establish. |
| Keep the synchronous flow | [`shop/README.md#order-confirmation`](placement/expected/shop/README.md#order-confirmation) | Commit, synchronous subscriber invocation, failure and retry consequences cross files. Only the status branch changes which participants are reached; inbox success/error belongs in a note. |
| Extract a connection and hazard | [`shop/service.py`](placement/expected/shop/service.py), [`notifications.py`](placement/expected/shop/notifications.py) | Edge rows support paired event maps. Registration is named. The local `_publish` comment preserves that failure happens after commit and another confirm will not redeliver. |
| Index a writer | [`shop/storage.py`](placement/expected/shop/storage.py) | `writes: orders` comes from supplied table rows. Delegating service code does not acquire that entry. |
| Keep a queued handoff | [`receipts/README.md#queued-receipt`](placement/expected/receipts/README.md#queued-receipt) | Producer acceptance precedes later polling. The sequence keeps the three-attempt bound, retry acceptance and acknowledgment order, and the sequential duplicate guard. |
| Keep a handwritten layout | [`transport/frame.py`](placement/expected/transport/frame.py) | One copy assembles the contract from separate encoder and decoder files; all three files point to it. |
| Omit a redraw | [Selection comparison](selection/README.md) | The short single-file codec and protobuf declaration provide concrete negative cases. The dataclass fields and SQLite schema also get no duplicate inventory. |
| Reconcile a partial update | [Maintenance exercise](maintenance/README.md) | A new guarded transition does not erase supported omitted transitions; a known move repairs pointers and leaves unrelated explanations alone. |

The expected root [`AGENTS.md`](placement/expected/AGENTS.md) adds selected
navigation and the self-contained map legend. [`GLOSSARY.md`](placement/expected/GLOSSARY.md)
clarifies why “confirmation” does not guarantee an inbox entry. File purpose
notes support `owns:`; none of these maps depend on unexplained inferred input.
Raw completeness comments become the guide's exact selected-view form.

## Try the two failure boundaries

Run Python from `placement/expected/` (the same code runs from `before/`):

```python
from shop import storage
from shop.models import OrderStatus
from shop.notifications import ConfirmationInbox, register_inbox
from shop.service import OrderService

connection = storage.open_store()
storage.create_order(connection, 1)
service = OrderService(connection)
inbox = ConfirmationInbox(available=False)
register_inbox(service, inbox)
try:
    service.confirm(1)
except RuntimeError:
    pass
assert storage.get_order(connection, 1).status is OrderStatus.CONFIRMED
inbox.available = True
try:
    service.confirm(1)
except ValueError:
    pass
assert inbox.order_ids == []
connection.close()

from receipts.broker import ReceiptBroker
from receipts.ledger import ReceiptLedger
from receipts.producer import submit
from receipts.worker import process_next

broker, ledger = ReceiptBroker(), ReceiptLedger(available=False)
assert submit(broker, "r1", 25) == "r1"
assert ledger.receipts == {}  # acceptance is not consumer completion
for _ in range(3):
    process_next(broker, ledger)
assert broker.receipts.empty() and broker.failed[0].attempt == 3
ledger.available = True
submit(broker, "r2", 25)
process_next(broker, ledger)
submit(broker, "r2", 99)
process_next(broker, ledger)
assert ledger.receipts == {"r2": 25}  # first amount survives duplicate processing
assert broker.receipts.unfinished_tasks == 0
```

The queue is real deferred work within one process, with one sequential worker.
Its contents and duplicate guard are in memory. The attempt bound applies to a
submitted chain, not repeated fresh submissions; there is no external email,
payment, restart recovery, or durability guarantee in this example.
