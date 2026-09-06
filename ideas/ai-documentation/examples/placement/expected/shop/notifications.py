# map
# owns: confirmation inbox and its OrderConfirmed subscription
# participates in: order confirmation (shop/README.md#order-confirmation)
# event in: OrderConfirmed <- shop.service.OrderService.confirm (shop/service.py); in shop.notifications.ConfirmationInbox.on_order_confirmed; when the inbox is registered and the confirmation status update commits
# end map

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
    # This subscription connects OrderService.confirm to the inbox without
    # shop/service.py importing the consumer; delivery is synchronous.
    service.subscribe("OrderConfirmed", inbox.on_order_confirmed)
