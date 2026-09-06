# map
# owns: receipt insertion with a duplicate receipt_id guard
# participates in: queued receipt (receipts/README.md#queued-receipt)
# end map

class ReceiptLedger:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.receipts: dict[str, int] = {}

    def record(self, receipt_id: str, amount: int) -> bool:
        if not self.available:
            raise RuntimeError("Ledger is unavailable")
        # Duplicate protection lasts only while this ledger retains its receipt history.
        if receipt_id in self.receipts:
            return False
        self.receipts[receipt_id] = amount
        return True
