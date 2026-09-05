## Flows

### Queued receipt

[`submit`](producer.py) and [`process_next`](worker.py) must receive the same
[`ReceiptBroker`](broker.py). `process_next` polls its `receipts` queue later;
`publish` never calls a worker. [`ReceiptLedger.record`](ledger.py) records an
in-memory receipt, with one sequential worker assumed. The duplicate guard and
queue contents do not survive restart, and this example promises no external
payment or message delivery.

```mermaid
sequenceDiagram
  %% scenario: queued receipt
  %% selected view; omits: queue construction, empty polling, other jobs, caller resubmission; omissions do not establish absence
  %% queue.receipts is receipts.broker.ReceiptBroker.receipts (receipts/broker.py).
  %% receipts.worker.process_next polls that same queue; no callback registration is involved.
  %% This scenario uses one sequential worker and one in-memory broker and ledger, with no process boundary or restart durability.
  participant receipts.producer
  participant queue.receipts
  participant receipts.worker
  participant receipts.ledger
  receipts.producer->>queue.receipts: submit calls ReceiptBroker.publish(job with attempt 1)
  Note over receipts.producer,queue.receipts: publish returns after put_nowait accepts the job, before process_next runs or any receipt is recorded
  queue.receipts-->>receipts.producer: receipt_id is acceptance only
  queue.receipts-)receipts.worker: job retrieved later by process_next
  receipts.worker->>receipts.ledger: ReceiptLedger.record(receipt_id, amount)
  Note over receipts.worker,receipts.ledger: record guards receipt_id before insertion, so sequential duplicates keep the first amount. RuntimeError occurs before insertion when unavailable
  receipts.ledger-->>receipts.worker: inserted, duplicate, or RuntimeError
  receipts.worker->>queue.receipts: on retryable RuntimeError, publish replacement job
  Note over receipts.worker,queue.receipts: process_next requeues only while attempt < 3, incrementing it. ReceiptBroker.publish validates 1 through 3. The bound is per submitted job chain
  queue.receipts-->>receipts.worker: replacement accepted when retried
  Note over receipts.worker,queue.receipts: process_next acknowledges after record or accepted retry. At attempt 3 failure it calls reject to retain the failed job then acknowledge
  receipts.worker->>queue.receipts: acknowledge, or reject on exhausted failure
```
