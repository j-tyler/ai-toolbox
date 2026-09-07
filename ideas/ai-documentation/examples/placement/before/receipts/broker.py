from dataclasses import dataclass
from queue import Queue


@dataclass(frozen=True)
class ReceiptJob:
    receipt_id: str
    amount: int
    attempt: int = 1


class ReceiptBroker:
    def __init__(self) -> None:
        self.receipts: Queue[ReceiptJob] = Queue()
        self.failed: list[ReceiptJob] = []

    def publish(self, job: ReceiptJob) -> str:
        if not 1 <= job.attempt <= 3:
            raise ValueError("Attempt must be between 1 and 3")
        self.receipts.put_nowait(job)
        return job.receipt_id

    def acknowledge(self) -> None:
        self.receipts.task_done()

    def reject(self, job: ReceiptJob) -> None:
        self.failed.append(job)
        self.acknowledge()
