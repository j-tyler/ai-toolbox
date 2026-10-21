"""Properties the brief states for every question: determinism, rejected rows counted in every output,
CSV mirroring the JSON rows, and totals that agree across views."""
import json
from decimal import Decimal

import billing_gen as g
import pytest
from conftest import by_key, close, csv_rows, mentions_rejected, num

QUESTIONS = [
    ["costs", "--by", "account"], ["costs", "--by", "service"], ["costs", "--by", "tag:team"], ["daily"],
    ["top", "--by", "service"], ["top", "--by", "resource", "-n", "3"], ["untagged", "--tag", "team"], ["credits"],
    ["mom"], ["mom", "--by", "service"], ["daily-stats"], ["rejects"],
]


def tolerance(n_rows: int) -> Decimal:
    return Decimal("0.005") * (n_rows + 1) + Decimal("0.0001")


def test_same_input_same_bytes(scenario, cli):
    """One test for every question and format, so determinism does not outweigh the answers."""
    for question in QUESTIONS:
        for fmt in ("text", "json", "csv"):
            first = cli(*question, "--format", fmt, *scenario[1])
            assert first[0] == 0, f"{question} {fmt}: {first[2][-500:]}"
            assert cli(*question, "--format", fmt, *scenario[1]) == first, f"{question} {fmt} differs between runs"


@pytest.mark.parametrize("fmt", ["json", "text", "csv"])
def test_rejected_rows_counted_in_every_output(scenario, cli, fmt):
    exports, paths = scenario
    n = g.rejected_count(exports)
    for question in QUESTIONS:
        code, out, err = cli(*question, "--format", fmt, *paths)
        assert code == 0, err[-500:]
        if fmt == "json":
            assert json.loads(out)["rejected_rows"] == n, question
        else:
            assert mentions_rejected(out, n), f"{question} {fmt} output does not report {n} rejected rows"


def test_csv_has_the_json_fields_and_rows(scenario, cli, cli_json):
    for question in QUESTIONS[:-1]:
        rows = cli_json(*question, *scenario[1])["rows"]
        code, out, _ = cli(*question, "--format", "csv", *scenario[1])
        assert code == 0 and rows, question
        table = csv_rows(out)
        assert table and set(rows[0]) <= set(table[0]), f"{question}: CSV header lacks {set(rows[0]) - set(table[0] if table else {})}"
        data = [r for r in table if any(str(v).strip() for v in r.values())]
        assert len(data) >= len(rows), question
        money = [f for f in rows[0] if f in ("charges", "credits", "net", "untagged", "credit", "refund", "median", "p90")]
        for j, row in zip(data, rows):
            for f in money:
                assert close(j[f], row[f]), f"{question} {f}: csv {j[f]!r} json {row[f]!r}"


def test_file_order_does_not_change_the_answer(scenario, cli_json):
    """The answer does not depend on the order the files are given in. Accounts, months and statistics
    are compared exactly; services by key the way the brief defines them (case-insensitively) and by
    money, since which spelling of a service name is shown is the implementer's choice."""
    paths = scenario[1]
    for q in (["mom", "--by", "account"], ["daily-stats"]):
        assert cli_json(*q, *paths)["rows"] == cli_json(*q, *reversed(paths))["rows"], q
    q = ["costs", "--by", "service"]
    first, second = (by_key(cli_json(*q, *files)["rows"], "service") for files in (paths, list(reversed(paths))))
    assert set(first) == set(second), q
    for k, row in first.items():
        for f in ("charges", "credits", "net"):
            assert close(second[k][f], num(row[f])), (k, f)


@pytest.mark.parametrize("by", ["account", "service", "tag:team", "tag:cost-center"])
def test_groups_add_up_to_the_total_and_charges_plus_credits_is_net(scenario, cli_json, by):
    doc = cli_json("costs", "--by", by, *scenario[1])
    rows, total = doc["rows"], doc["total"]
    for f in ("charges", "credits", "net"):
        assert abs(sum(num(r[f]) for r in rows) - num(total[f])) <= tolerance(len(rows)), f
    for r in rows + [total]:
        assert abs(num(r["charges"]) + num(r["credits"]) - num(r["net"])) <= Decimal("0.0101")


def test_views_agree(scenario, cli_json):
    paths = scenario[1]
    costs = cli_json("costs", "--by", "account", *paths)
    net = num(costs["total"]["net"])
    daily = cli_json("daily", *paths)["rows"]
    assert abs(sum(num(r["net"]) for r in daily) - net) <= tolerance(len(daily))
    months = cli_json("mom", *paths)["rows"]
    assert abs(sum(num(r["net"]) for r in months) - net) <= tolerance(len(months))
    accounts = by_key(costs["rows"])
    for k, r in by_key(cli_json("untagged", "--tag", "team", *paths)["rows"]).items():
        assert close(r["net"], num(accounts[k]["net"])), k
    for k, r in by_key(cli_json("credits", *paths)["rows"]).items():
        assert close(r["credits"], num(accounts[k]["credits"])), k
    top = cli_json("top", "--by", "account", "-n", "50", *paths)["rows"]
    assert sorted(r["key"] for r in top) == sorted(accounts)


def test_rejected_count_matches_the_rejects_listing(scenario, cli_json):
    doc = cli_json("rejects", *scenario[1])
    assert doc["rejected_rows"] == len(doc["rows"]) == g.rejected_count(scenario[0])
