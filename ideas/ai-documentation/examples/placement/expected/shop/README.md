## Owns

- [models.py](models.py) — order records and status values
- [service.py](service.py) — order confirmation and synchronous confirmation-event delivery

## Flows

### Order confirmation

This scenario uses one inbox connected by `shop.notifications.register_inbox`
in [notifications.py](notifications.py). The service is in [service.py](service.py);
the guarded update and transaction are in [storage.py](storage.py). Storage and
the inbox are in memory; the commit does not make them survive process exit.

```mermaid
sequenceDiagram
  %% scenario: order confirmation
  %% selected view; omits: connection setup, order creation, other subscribers; omissions do not establish absence
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
