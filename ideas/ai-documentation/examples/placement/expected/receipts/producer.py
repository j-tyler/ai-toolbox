# map
# owns: submission of receipt jobs
# entry point of: queued receipt (receipts/README.md#queued-receipt)
# other out: channel receipts -> receipts.worker.process_next (receipts/worker.py); in receipts.producer.submit; when producer and worker share the same ReceiptBroker
# end map

from receipts.broker import ReceiptBroker, ReceiptJob


def submit(broker: ReceiptBroker, receipt_id: str, amount: int) -> str:
    # Acceptance does not mean a receipt has been recorded; process_next runs later.
    return broker.publish(ReceiptJob(receipt_id, amount))
