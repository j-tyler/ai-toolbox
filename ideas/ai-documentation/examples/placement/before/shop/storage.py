import sqlite3

from shop.models import Order, OrderStatus


def open_store() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT NOT NULL "
        "CHECK (status IN ('pending', 'confirmed', 'cancelled')))"
    )
    return connection


def create_order(connection: sqlite3.Connection, order_id: int) -> Order:
    with connection:
        connection.execute(
            "INSERT INTO orders (id, status) VALUES (?, ?)",
            (order_id, OrderStatus.PENDING.value),
        )
    return get_order(connection, order_id)


def get_order(connection: sqlite3.Connection, order_id: int) -> Order:
    row = connection.execute(
        "SELECT id, status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    if row is None:
        raise KeyError(order_id)
    return Order(row[0], OrderStatus(row[1]))


def confirm_order(connection: sqlite3.Connection, order_id: int) -> Order:
    with connection:
        result = connection.execute(
            "UPDATE orders SET status = ? WHERE id = ? AND status = ?",
            (OrderStatus.CONFIRMED.value, order_id, OrderStatus.PENDING.value),
        )
        if result.rowcount != 1:
            raise ValueError("Confirmation requires an existing pending order")
    return get_order(connection, order_id)


def cancel_order(connection: sqlite3.Connection, order_id: int) -> Order:
    with connection:
        result = connection.execute(
            "UPDATE orders SET status = ? WHERE id = ? AND status = ?",
            (OrderStatus.CANCELLED.value, order_id, OrderStatus.PENDING.value),
        )
        if result.rowcount != 1:
            raise ValueError("Cancellation requires an existing pending order")
    return get_order(connection, order_id)
