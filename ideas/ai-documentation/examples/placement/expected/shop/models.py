# map
# owns: order records and status values
# transitions: shop.models.Order.status, diagram above shop.models.OrderStatus
# end map

from dataclasses import dataclass
from enum import Enum


# stateDiagram-v2
# %% entity: shop.models.Order, field: status
# %% selected view; omissions do not establish absence
# %% triggers: shop/storage.py
# [*] --> pending: shop.storage.create_order
# pending --> confirmed: shop.storage.confirm_order [current status is pending]
# pending --> cancelled: shop.storage.cancel_order [current status is pending]
# %% shop.storage.cancel_order rejects confirmed orders without changing them.
# %% shop.storage.confirm_order rejects cancelled orders without changing them.
# %% Public operations guard transitions, but direct SQL on the supplied connection can change valid status values. No finality is asserted.
class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Order:
    id: int
    status: OrderStatus
