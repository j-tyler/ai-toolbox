"""Each question against the oracle, on a two-file scenario that exercises every rule in the brief."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import billing_gen as g
import pytest
from conftest import A, B, C, by_key, close, norm, num

D = Decimal


def check_groups(rows, expected: dict, by: str, fields=("charges", "credits", "net")):
    got = by_key(rows, by)
    extra = {k for k in set(got) - set(expected) if any(num(got[k].get(f)) for f in fields)}
    assert not extra, f"unexpected groups {sorted(map(str, extra))}"
    for k, exp in expected.items():
        assert k in got, f"missing group {k!r}; got {sorted(map(str, got))}"
        for f in fields:
            assert close(got[k].get(f), exp[f]), f"{k!r} {f}: got {got[k].get(f)!r}, expected {exp[f]}"


@pytest.mark.parametrize("by", ["account", "service", "tag:team", "tag:cost-center"])
def test_costs(scenario, cli_json, by):
    exports, paths = scenario
    doc = cli_json("costs", "--by", by, *paths)
    groups, total = g.totals(exports, by)
    check_groups(doc["rows"], groups, by.split(":")[0])
    for f in ("charges", "credits", "net"):
        assert close(doc["total"][f], total[f]), f"total {f}"
    assert doc["rejected_rows"] == g.rejected_count(exports)


def test_costs_rows_sorted_by_key(scenario, cli_json):
    keys = [r["key"] for r in cli_json("costs", "--by", "account", *scenario[1])["rows"]]
    assert keys == sorted(keys) == [A, B, C]


def test_costs_over_a_date_range(scenario, cli_json):
    exports, paths = scenario
    doc = cli_json("costs", "--by", "service", "--from", "2026-08-30", "--to", "2026-09-02", *paths)
    groups, total = g.totals(exports, "service", date(2026, 8, 30), date(2026, 9, 2))
    check_groups(doc["rows"], groups, "service")
    assert close(doc["total"]["net"], total["net"])


def test_daily(scenario, cli_json):
    exports, paths = scenario
    rows = cli_json("daily", *paths)["rows"]
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates)
    expected = g.daily(exports)
    got = by_key(rows, field="date")
    for day in set(expected) | set(got):
        assert close(got.get(day, {}).get("net", 0), expected.get(day, 0)), day


@pytest.mark.parametrize("by,n", [("service", 3), ("resource", 2), ("account", 10)])
def test_top(scenario, cli_json, by, n):
    exports, paths = scenario
    rows = cli_json("top", "--by", by, "-n", n, *paths)["rows"]
    groups, _ = g.totals(exports, by)
    ranked = sorted(groups.items(), key=lambda kv: -kv[1]["net"])[:n]
    assert [norm(r.get("key"), by) for r in rows] == [k for k, _ in ranked]
    for r, (_, exp) in zip(rows, ranked):
        assert close(r["net"], exp["net"])


def test_top_defaults_to_ten(tmp_path, cli_json):
    items = [g.Item(g.new_id(), "111111111111", "Compute Engine", g.ts("2026-08-01T00:00:00Z"), str(i), resource_id=f"r{i:02d}")
             for i in range(1, 15)]
    path = g.Export(items).write(tmp_path / "e.csv")
    rows = cli_json("top", "--by", "resource", path)["rows"]
    assert [r["key"] for r in rows] == [f"r{i:02d}" for i in range(14, 4, -1)]


def test_untagged(scenario, cli_json):
    exports, paths = scenario
    got = by_key(cli_json("untagged", "--tag", "team", *paths)["rows"])
    expected = g.untagged(exports, "team")
    assert set(got) == set(expected)
    for k, (untagged, net) in expected.items():
        assert close(got[k]["untagged"], untagged) and close(got[k]["net"], net), k


def test_credits(scenario, cli_json):
    exports, paths = scenario
    got = by_key(cli_json("credits", *paths)["rows"])
    expected = g.credit_split(exports)
    for k, (credit, refund) in expected.items():
        assert close(got[k]["credit"], credit) and close(got[k]["refund"], refund) and close(got[k]["credits"], credit + refund), k
    for k in set(got) - set(expected):
        assert close(got[k]["credits"], 0), k


def _mom_expected(exports, by):
    nets = g.monthly(exports, by)
    keys = sorted({k for k, _ in nets}, key=lambda k: (k is None, k or ""))
    out = {}
    for k in keys:  # only groups with lines in both months: the brief does not say how a missing month shows
        if (k, "2026-08") in nets and (k, "2026-09") in nets:
            aug, sep = nets[(k, "2026-08")], nets[(k, "2026-09")]
            out[(k, "2026-08")] = (aug, None, None)
            out[(k, "2026-09")] = (sep, sep - aug, None if aug == 0 else (sep - aug) * 100 / abs(aug))
    assert out
    return out


@pytest.mark.parametrize("by", [None, "service", "account"])
def test_mom(scenario, cli_json, by):
    exports, paths = scenario
    args = ["mom"] + (["--by", by] if by else [])
    rows = cli_json(*args, *paths)["rows"]
    expected = _mom_expected(exports, by)
    got = {}
    for r in rows:
        k = (norm(r.get("key"), by) if by else None, r["month"])
        got[k] = r
    for k, (net, change, pct) in expected.items():
        assert k in got, f"missing {k}"
        r = got[k]
        assert close(r["net"], net), k
        if change is None:
            assert r.get("change") is None and r.get("change_pct") is None, k
        else:
            assert close(r["change"], change), k
            if pct is None:
                assert r.get("change_pct") is None, f"{k}: previous month is zero, change_pct should be null"
            else:
                assert close(r["change_pct"], pct, D("0.05")), f"{k} change_pct {r['change_pct']} vs {pct:.4f}"


def test_mom_flags_the_partial_month(scenario, cli_json):
    rows = {r["month"]: r for r in cli_json("mom", *scenario[1])["rows"]}
    assert rows["2026-08"]["partial"] in (False, "false") and rows["2026-09"]["partial"] in (True, "true")


def test_mom_percentage_is_null_after_a_zero_month(tmp_path, cli_json):
    items = [g.Item(g.new_id(), "1", "Compute Engine", g.ts("2026-07-01T00:00:00Z"), "0"),
             g.Item(g.new_id(), "1", "Compute Engine", g.ts("2026-07-31T00:00:00Z"), "0"),
             g.Item(g.new_id(), "1", "Compute Engine", g.ts("2026-08-01T00:00:00Z"), "5"),
             g.Item(g.new_id(), "1", "Compute Engine", g.ts("2026-08-31T00:00:00Z"), "5")]
    rows = {r["month"]: r for r in cli_json("mom", g.Export(items).write(tmp_path / "e.csv"))["rows"]}
    assert close(rows["2026-08"]["change"], "10") and rows["2026-08"]["change_pct"] is None


def test_daily_stats(scenario, cli_json):
    exports, paths = scenario
    rows = by_key(cli_json("daily-stats", "--from", "2026-08-01", "--to", "2026-08-31", *paths)["rows"])
    per_account = g.account_days(exports, date(2026, 8, 1), date(2026, 8, 31))
    assert set(rows) == set(per_account)
    for k, days in per_account.items():
        values = sorted(days.values())
        assert len(values) == 31
        assert int(num(rows[k]["days"])) == 31, k
        assert close(rows[k]["median"], values[15]), f"{k} median {rows[k]['median']} vs {values[15]}"
        p90 = num(rows[k]["p90"])
        assert values[15] - D("0.01") <= p90 <= values[-1] + D("0.01"), f"{k} p90 {p90}"
        assert values[26] - D("0.01") <= p90 <= values[28] + D("0.01"), f"{k} p90 {p90} not near the 90th percentile"


def test_rejects(scenario, cli_json):
    exports, paths = scenario
    doc = cli_json("rejects", *paths)
    expected = sorted((paths[i].name, line) for i, line in g.rejected_lines(exports))
    got = sorted((Path(str(r["file"])).name, int(r["line"])) for r in doc["rows"])
    assert got == expected
    assert doc["rejected_rows"] == len(expected) and all(str(r["reason"]).strip() for r in doc["rows"])
