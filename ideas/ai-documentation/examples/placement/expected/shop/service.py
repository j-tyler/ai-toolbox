# map
# owns: order confirmation and synchronous confirmation-event delivery
# entry point of: order confirmation (shop/README.md#order-confirmation)
# event out: OrderConfirmed -> shop.notifications.ConfirmationInbox.on_order_confirmed (shop/notifications.py); in shop.service.OrderService.confirm; when the inbox is registered and the confirmation status update commits
# end map

import sqlite3
from collections.abc import Callable

from shop import storage
from shop.models import Order


class OrderService:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._listeners: dict[str, list[Callable[[Order], None]]] = {}

    def subscribe(self, event: str, listener: Callable[[Order], None]) -> None:
        self._listeners.setdefault(event, []).append(listener)

    def confirm(self, order_id: int) -> Order:
        order = storage.confirm_order(self.connection, order_id)
        # Confirmation has already committed. A listener failure leaves it confirmed;
        # repeating confirm rejects that status before delivering another event.
        self._publish("OrderConfirmed", order)
        return order

    def _publish(self, event: str, order: Order) -> None:
        for listener in self._listeners.get(event, ()):
            listener(order)
