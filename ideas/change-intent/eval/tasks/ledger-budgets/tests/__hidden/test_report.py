from conftest import add


def test_report_text(workdir, run):
    add(run, "2026-10-01", "12.50", "groceries")
    add(run, "2026-10-03", "7.50", "groceries")
    add(run, "2026-10-02", "40", "fuel")
    add(run, "2026-11-02", "99", "fuel")
    run(["budget", "set", "groceries", "100"])
    code, out, _ = run(["report", "--month", "2026-10"])
    assert code == 0
    assert out.strip().splitlines() == [
        "fuel 40.00",
        "groceries 20.00 of 100.00",
        "total 60.00",
    ]


def test_report_json(workdir, run_json, run):
    add(run, "2026-10-01", "12.50", "groceries")
    add(run, "2026-10-02", "40", "fuel")
    run(["budget", "set", "groceries", "100", "--month", "2026-10"])
    data = run_json(["report", "--month", "2026-10", "--format", "json"])
    assert data == {
        "month": "2026-10",
        "total_cents": 5250,
        "categories": [
            {"category": "fuel", "spent_cents": 4000, "limit_cents": None},
            {"category": "groceries", "spent_cents": 1250, "limit_cents": 10000},
        ],
    }


def test_report_empty_month(workdir, run):
    code, out, _ = run(["report", "--month", "2026-10"])
    assert code == 0
    assert out.strip() == "total 0.00"


def test_report_includes_applied_recurring(workdir, run):
    run(["recur", "add", "--amount", "10", "--category", "sub", "--every", "monthly", "--start", "2026-10-01"])
    run(["recur", "apply", "--through", "2026-10-31"])
    _, out, _ = run(["report", "--month", "2026-10"])
    assert out.strip().splitlines() == ["sub 10.00", "total 10.00"]
