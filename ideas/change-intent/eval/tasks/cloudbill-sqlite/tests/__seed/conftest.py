import csv
import json
from pathlib import Path

import pytest

from cloudbill.cli import main

COLUMNS = [
    "line_item_id", "billing_period", "account_id", "account_name", "service", "region", "usage_type",
    "resource_id", "usage_start", "usage_end", "usage_start_local", "usage_amount", "usage_unit",
    "unblended_cost", "currency", "line_item_type", "last_updated", "tag:team", "tag:env", "tag:cost-center",
    "description",
]
DEFAULTS = {
    "billing_period": "2026-08", "account_id": "111111111111", "account_name": "acct-one", "service": "Compute Engine",
    "region": "us-west-2", "usage_type": "BoxUsage:m6.large", "resource_id": "vm-1", "usage_start": "2026-08-01T00:00:00Z",
    "usage_end": "2026-08-02T00:00:00Z", "usage_start_local": "2026-07-31 17:00:00 -0700", "usage_amount": "24",
    "usage_unit": "Hrs", "unblended_cost": "1.0000", "currency": "USD", "line_item_type": "Usage",
    "last_updated": "2026-08-02T04:00:00Z", "description": "",
}


@pytest.fixture
def write_export(tmp_path: Path):
    """write_export(rows, name=..., columns=..., bom=...): rows are dicts over DEFAULTS (ids are filled in)
    or raw lists written as they are."""
    counter = {"n": 0}

    def write(rows, name="export.csv", columns=COLUMNS, bom=False) -> Path:
        path = tmp_path / name
        with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(columns)
            for row in rows:
                if isinstance(row, list):
                    w.writerow(row)
                    continue
                counter["n"] += 1
                values = {**DEFAULTS, "line_item_id": f"li-{name}-{counter['n']:04d}", **row}
                w.writerow([values.get(c, "") for c in columns])
        return path

    return write


@pytest.fixture
def run(capsys):
    def _run(*argv):
        code = main([str(a) for a in argv])
        out = capsys.readouterr()
        return code, out.out, out.err

    return _run


@pytest.fixture
def run_json(run):
    def _run(*argv):
        code, out, err = run(*argv, "--format", "json")
        assert code == 0, err
        return json.loads(out)

    return _run
