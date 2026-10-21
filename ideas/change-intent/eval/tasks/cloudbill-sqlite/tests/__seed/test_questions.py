from datetime import date
from decimal import Decimal

from cloudbill import questions
from cloudbill.export import LineItem
from cloudbill.questions import percentile

D = Decimal


def item(cost, day="2026-08-01", account="111", service="Compute Engine", kind="usage", resource="vm-1", tags=(), n=[0]):
    n[0] += 1
    return LineItem(line_item_id=f"i{n[0]}", account_id=account, account_name=f"name-{account}", service=service,
                    resource_id=resource, usage_date=date.fromisoformat(day), usage_start=f"{day}T00:00:00+00:00",
                    last_updated="", kind=kind, cost=D(cost), tags=tuple(tags), order=(0, n[0]))


def test_costs_split_charges_and_credits_and_merge_service_spellings():
    items = [item("10"), item("5", service="compute engine"), item("-3", kind="credit"), item("2", kind="tax", service="Tax"),
             item("-1", kind="refund", service="Tax")]
    rows, total = questions.costs(items, "service")
    assert rows == [
        {"key": "Compute Engine", "charges": D(15), "credits": D(-3), "net": D(12)},
        {"key": "Tax", "charges": D(2), "credits": D(-1), "net": D(1)},
    ]
    assert total == {"charges": D(17), "credits": D(-4), "net": D(13)}


def test_spelling_ties_pick_the_alphabetically_first():
    rows, _ = questions.costs([item("1", service="b-svc"), item("1", service="B-svc")], "service")
    assert rows[0]["key"] == "B-svc"


def test_costs_by_tag_puts_untagged_last_and_accounts_carry_names():
    items = [item("1", tags=(("team", "web"),)), item("2"), item("4", tags=(("team", "api"),))]
    rows, _ = questions.costs(items, "tag:team")
    assert [(r["key"], r["net"]) for r in rows] == [("api", D(4)), ("web", D(1)), (None, D(2))]
    rows, _ = questions.costs([item("1", account="222"), item("1", account="011")], "account")
    assert [(r["key"], r["name"]) for r in rows] == [("011", "name-011"), ("222", "name-222")]


def test_top_orders_by_net_then_key():
    items = [item("5", resource="b"), item("5", resource="a"), item("9", resource="c"), item("1", resource="d")]
    assert [r["key"] for r in questions.top(items, "resource", 3)] == ["c", "a", "b"]


def test_daily_untagged_and_credits():
    items = [item("3", day="2026-08-02"), item("2", day="2026-08-01", tags=(("team", "x"),)), item("-1", kind="refund", day="2026-08-02")]
    assert [(r["date"], r["net"]) for r in questions.daily(items)] == [("2026-08-01", D(2)), ("2026-08-02", D(2))]
    assert questions.untagged(items, "team") == [{"key": "111", "untagged": D(2), "net": D(4)}]
    assert questions.credits(items) == [{"key": "111", "credit": D(0), "refund": D(-1), "credits": D(-1)}]


def test_mom_change_percentage_and_partial_months():
    items = [item("100", day="2026-07-01"), item("100", day="2026-07-31"), item("50", day="2026-08-01"),
             item("75", day="2026-08-31"), item("10", day="2026-09-15")]
    rows = questions.mom(items, None)
    assert [(r["month"], r["net"], r["change"], r["change_pct"], r["partial"]) for r in rows] == [
        ("2026-07", D(200), None, None, False),
        ("2026-08", D(125), D(-75), D("-37.50"), False),
        ("2026-09", D(10), D(-115), D("-92.00"), True),
    ]


def test_mom_by_group_fills_missing_months_with_zero():
    rows = questions.mom([item("4", day="2026-07-01", account="a"), item("6", day="2026-08-31", account="b")], "account")
    assert [(r["key"], r["month"], r["net"], r["change_pct"]) for r in rows] == [
        ("a", "2026-07", D(4), None), ("a", "2026-08", D(0), D("-100.00")),
        ("b", "2026-07", D(0), None), ("b", "2026-08", D(6), None)]


def test_percentile_is_linear_between_ranks():
    values = [D(v) for v in (1, 2, 3, 4, 10)]
    assert percentile(values, 50) == D(3)
    assert percentile(values, 90) == D("7.6")
    assert percentile([D(5)], 90) == D(5)
    assert percentile([D(1), D(2)], 50) == D("1.5")


def test_daily_stats_sum_each_day_first():
    items = [item("1", day="2026-08-01"), item("2", day="2026-08-01"), item("10", day="2026-08-02"), item("4", day="2026-08-03")]
    assert questions.daily_stats(items) == [{"key": "111", "days": 3, "median": D(4), "p90": D("8.8")}]


def test_answers_do_not_depend_on_item_order():
    items = [item("1", service="x"), item("2", service="X"), item("3", service="X", day="2026-09-02"), item("-1", kind="credit")]
    for q in (lambda its: questions.costs(its, "service"), questions.daily, questions.daily_stats,
              lambda its: questions.mom(its, "service")):
        assert q(items) == q(list(reversed(items)))
