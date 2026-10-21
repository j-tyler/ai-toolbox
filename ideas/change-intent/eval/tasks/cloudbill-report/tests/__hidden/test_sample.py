"""The questions the review actually asks, on the same sample the repository ships (regenerated here)."""
from datetime import date

import billing_gen as g
from conftest import by_key, close


def test_sample_costs_by_service(sample, cli_json):
    exports, paths = sample
    doc = cli_json("costs", "--by", "service", *paths)
    groups, total = g.totals(exports, "service")
    got = by_key(doc["rows"], "service")
    for k, exp in groups.items():
        assert close(got[k]["net"], exp["net"]) and close(got[k]["credits"], exp["credits"]), k
    assert close(doc["total"]["net"], total["net"]) and doc["rejected_rows"] == g.rejected_count(exports)


def test_sample_month_over_month(sample, cli_json):
    exports, paths = sample
    rows = {r["month"]: r for r in cli_json("mom", *paths)["rows"]}
    nets = g.monthly(exports)
    assert close(rows["2026-08"]["net"], nets[(None, "2026-08")]) and close(rows["2026-09"]["net"], nets[(None, "2026-09")])
    assert rows["2026-09"]["partial"] in (True, "true") and rows["2026-08"]["partial"] in (False, "false")


def test_sample_untagged_team_spend_in_august(sample, cli_json):
    exports, paths = sample
    got = by_key(cli_json("untagged", "--tag", "team", "--from", "2026-08-01", "--to", "2026-08-31", *paths)["rows"])
    for k, (untagged, net) in g.untagged(exports, "team", date(2026, 8, 1), date(2026, 8, 31)).items():
        assert close(got[k]["untagged"], untagged) and close(got[k]["net"], net), k
