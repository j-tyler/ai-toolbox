from receipts.broker import ReceiptBroker, ReceiptJob


def submit(broker: ReceiptBroker, receipt_id: str, amount: int) -> str:
    return broker.publish(ReceiptJob(receipt_id, amount))
