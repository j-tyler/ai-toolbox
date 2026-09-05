from shop.models import Order
from shop.service import OrderService


class ConfirmationInbox:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.order_ids: list[int] = []

    def on_order_confirmed(self, order: Order) -> None:
        if not self.available:
            raise RuntimeError("Confirmation inbox is unavailable")
        self.order_ids.append(order.id)


def register_inbox(service: OrderService, inbox: ConfirmationInbox) -> None:
    service.subscribe("OrderConfirmed", inbox.on_order_confirmed)
