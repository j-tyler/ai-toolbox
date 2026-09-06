# Supplied artifacts

Authored input fixture, checked against `before/`; not a captured generator run.
Treat `before/` as repository root. Read scope: `shop/`, `transport/`, `receipts/`.
Each scope comment below is raw input metadata, not persisted documentation.

## State diagrams

```mermaid
stateDiagram-v2
  %% entity: shop.models.Order, field: status
  %% complete within: shop/, transport/, receipts/
  %% triggers: shop/storage.py
  [*] --> pending: shop.storage.create_order
  pending --> confirmed: shop.storage.confirm_order [current status is pending]
  pending --> cancelled: shop.storage.cancel_order [current status is pending]
  %% shop.storage.cancel_order rejects confirmed orders without changing them.
  %% shop.storage.confirm_order rejects cancelled orders without changing them.
  %% Public operations guard transitions, but direct SQL on the supplied connection can change valid status values. No finality is asserted.
```

## Sequence diagrams

```mermaid
sequenceDiagram
  %% scenario: order confirmation
  %% partial within: shop/, transport/, receipts/; left out: connection setup, order creation, other subscribers
  %% source: shop/service.py, shop/storage.py, shop/notifications.py
  participant shop.service.OrderService
  participant shop.storage
  participant shop.notifications.ConfirmationInbox
  shop.service.OrderService->>shop.storage: confirm_order(connection, order_id)
  alt no existing pending order
    shop.storage-->>shop.service.OrderService: raise ValueError without a status change
    Note over shop.service.OrderService: no OrderConfirmed event is delivered
  else pending order
    Note over shop.storage: confirm_order commits confirmed status before returning
    shop.storage-->>shop.service.OrderService: Order(status=confirmed)
    Note over shop.service.OrderService,shop.notifications.ConfirmationInbox: shop.notifications.register_inbox connects OrderConfirmed to on_order_confirmed in shop/notifications.py
    shop.service.OrderService->>shop.notifications.ConfirmationInbox: on_order_confirmed(order), through _publish
    Note over shop.service.OrderService,shop.notifications.ConfirmationInbox: on_order_confirmed appends when available or raises RuntimeError before appending when unavailable
    shop.notifications.ConfirmationInbox-->>shop.service.OrderService: return or propagate RuntimeError with order still confirmed
    Note over shop.service.OrderService: after a listener error another confirm fails the pending-status guard before delivery
  end
```

```mermaid
sequenceDiagram
  %% scenario: queued receipt
  %% partial within: shop/, transport/, receipts/; left out: queue construction, empty polling, other jobs, caller resubmission
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

## Edge table

edge table, complete within: shop/, transport/, receipts/

| Source | Target | Kind | Name | Defined in |
|---|---|---|---|---|
| shop.service.OrderService.confirm | shop.notifications.ConfirmationInbox.on_order_confirmed | event | OrderConfirmed | shop/service.py, shop/notifications.py, registered in shop/notifications.py (shop.notifications.register_inbox) |
| shop.storage.create_order | orders | table | write | shop/storage.py |
| shop.storage.get_order | orders | table | read | shop/storage.py |
| shop.storage.confirm_order | orders | table | write | shop/storage.py |
| shop.storage.cancel_order | orders | table | write | shop/storage.py |
| receipts.producer.submit | receipts.worker.process_next | other | channel receipts | receipts/producer.py, receipts/worker.py, handed off through receipts/broker.py (receipts.broker.ReceiptBroker.receipts) |

## Packet diagrams

```mermaid
packet-beta
  %% format: message frame header
  %% partial within: shop/, transport/, receipts/; left out: the variable-length payload beginning at byte 8
  %% Bit offsets count from the frame start. length and request_id use big-endian byte order.
  %% length is the payload size in bytes, excluding these 8 header bytes.
  %% definition: transport.frame.Frame (transport/frame.py)
  %% codecs: transport.encoder.encode (transport/encoder.py), transport.decoder.decode (transport/decoder.py)
  0-7: "version"
  8-15: "flags"
  16-31: "length"
  32-63: "request_id"
```

## Glossary table

| Term | Canonical identifier | Meaning | Defined in | Known aliases | Notes |
|---|---|---|---|---|---|
| confirmation | `shop.service.OrderService.confirm` | A committed order status change followed by synchronous listener delivery. | shop/service.py | none | A listener failure can leave the order confirmed without an inbox entry. |

## File notes

shop/models.py: Owns order records and status values. The lifecycle combines guarded storage functions; the SQLite CHECK constrains values, not transition order.

shop/storage.py: Owns SQLite order storage and guarded status changes. confirm_order commits before returning to the service; the store lasts only for the connection's lifetime.

shop/service.py: Owns order confirmation and synchronous confirmation-event delivery. With an inbox registered, a successful status-update commit precedes its OrderConfirmed delivery. A listener error at _publish leaves the order confirmed; another confirm fails the pending-status guard before delivery.

shop/notifications.py: Owns confirmation inbox and its OrderConfirmed subscription. register_inbox connects OrderService.confirm to ConfirmationInbox.on_order_confirmed without the service importing the consumer; delivery is synchronous.

transport/frame.py: Owns message frame representation. Its fields do not declare offsets, byte order, or the synthesized wire length field. The header is assembled by transport.encoder.encode and checked by transport.decoder.decode.

transport/encoder.py: Owns message frame encoding. The header uses a length excluding its own eight bytes, consumed by transport.decoder.decode.

transport/decoder.py: Owns message frame decoding. The decoder rejects a short header and total sizes inconsistent with its payload length.

receipts/broker.py: Owns receipt queue acceptance and completion tracking. publish accepts via Queue.put_nowait before returning receipt_id; it never calls process_next. The queue participant denotes the receipts Queue held here, not a service outside this repository.

receipts/producer.py: Owns submission of receipt jobs. Its caller and the worker must share the same ReceiptBroker for this handoff. The publish return reports acceptance, not a recorded receipt.

receipts/worker.py: Owns receipt processing and bounded requeue. process_next polls the broker's receipts queue. Its attempt < 3 guard permits two requeues after the first attempt; a fresh submit starts a separate chain. It acknowledges only after record, accepted requeue, or retention in failed via reject. A crash after dequeue is not recovered by this in-memory example.

receipts/ledger.py: Owns receipt insertion with a duplicate receipt_id guard. record preserves the first amount for repeated receipt_id values under sequential processing; this in-memory protection is not restart durability or a concurrency guarantee.
