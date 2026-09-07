# map
# owns: receipt processing and bounded requeue
# participates in: queued receipt (receipts/README.md#queued-receipt)
# other in: channel receipts <- receipts.producer.submit (receipts/producer.py); in receipts.worker.process_next; when producer and worker share the same ReceiptBroker
# end map

from dataclasses import replace

from receipts.broker import ReceiptBroker
from receipts.ledger import ReceiptLedger


def process_next(broker: ReceiptBroker, ledger: ReceiptLedger) -> None:
    job = broker.receipts.get_nowait()
    try:
        ledger.record(job.receipt_id, job.amount)
    except RuntimeError:
        # This bounds one submitted job chain to three attempts; a fresh submission starts again.
        if job.attempt < 3:
            broker.publish(replace(job, attempt=job.attempt + 1))
            broker.acknowledge()
        else:
            broker.reject(job)
    else:
        broker.acknowledge()
