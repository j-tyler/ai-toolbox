"""The brief: a 2 GB export must run on a laptop, streamed, under 100 MB of peak memory. Checked on a
1,500,000-row export (about 380 MB): loading it costs gigabytes, and even a bare set of the line item
ids about 180 MB, so only a design whose memory does not grow with the export passes (conftest.py has
the measurements)."""
import json
import sys

import pytest
from conftest import CAP_MB, LARGE_ROWS, by_key, close, measured


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="ru_maxrss units are Linux's")
def test_large_export_streams_under_the_memory_cap(tmp_path, large):
    path, expected = large
    code, peak_mb, out, err = measured(tmp_path, "costs", "--by", "service", "--format", "json", path)
    assert code == 0, err[-800:]
    doc = json.loads(out)
    assert doc["rejected_rows"] == expected["rejected"]
    rows = by_key(doc["rows"], "service")
    for service, exp in expected["by_service"].items():
        assert close(rows[service]["net"], exp["net"]), service
    assert close(doc["total"]["net"], expected["total"]["net"])
    assert peak_mb < CAP_MB, f"peak memory {peak_mb:.0f} MB on a {LARGE_ROWS}-row export; the brief allows {CAP_MB} MB"
