from conftest import add


def test_set_default_budget_prints_and_persists(workdir, run):
    code, out, err = run(["budget", "set", "groceries", "300"])
    assert code == 0, err
    assert out.strip() == "budget groceries 300.00"
    assert (workdir / "budgets.csv").exists()
    assert not (workdir.parent / "budgets.csv").exists(), "budgets.csv must sit next to the ledger file, not in cwd"


def test_files_follow_the_file_flag(tmp_path, workdir, run):
    other = tmp_path / "elsewhere"
    other.mkdir()
    ledger = other / "book.csv"
    code, _, _ = run(["--file", str(ledger), "budget", "set", "fuel", "10"])
    assert code == 0
    code, _, _ = run(["--file", str(ledger), "recur", "add", "--amount", "1", "--category", "x", "--every", "weekly", "--start", "2026-01-01"])
    assert code == 0
    assert (other / "budgets.csv").exists() and (other / "recurring.csv").exists()
    assert not (workdir / "budgets.csv").exists() and not (tmp_path / "budgets.csv").exists()


def test_set_month_budget_prints_month(workdir, run):
    code, out, _ = run(["budget", "set", "groceries", "250.5", "--month", "2026-10"])
    assert code == 0
    assert out.strip() == "budget groceries 250.50 for 2026-10"


def test_status_text_sorted_with_remaining(workdir, run):
    run(["budget", "set", "groceries", "300"])
    run(["budget", "set", "fuel", "100"])
    add(run, "2026-10-03", "120.25", "groceries")
    add(run, "2026-10-04", "30", "groceries")
    add(run, "2026-10-05", "40", "fuel")
    add(run, "2026-09-05", "999", "fuel")  # other month, ignored
    code, out, _ = run(["budget", "status", "--month", "2026-10"])
    assert code == 0
    assert out.strip().splitlines() == [
        "fuel 40.00/100.00 remaining 60.00",
        "groceries 150.25/300.00 remaining 149.75",
    ]


def test_status_marks_over(workdir, run):
    run(["budget", "set", "fun", "50"])
    add(run, "2026-10-10", "70", "fun")
    _, out, _ = run(["budget", "status", "--month", "2026-10"])
    assert out.strip() == "fun 70.00/50.00 remaining -20.00 OVER"


def test_status_json_shape(workdir, run_json, run):
    run(["budget", "set", "fun", "50"])
    add(run, "2026-10-10", "70", "fun")
    data = run_json(["budget", "status", "--month", "2026-10", "--format", "json"])
    assert data == [
        {"category": "fun", "limit_cents": 5000, "spent_cents": 7000, "remaining_cents": -2000, "over": True}
    ]


def test_month_override_beats_default_only_for_that_month(workdir, run_json, run):
    run(["budget", "set", "groceries", "300"])
    run(["budget", "set", "groceries", "500", "--month", "2026-12"])
    nov = run_json(["budget", "status", "--month", "2026-11", "--format", "json"])
    dec = run_json(["budget", "status", "--month", "2026-12", "--format", "json"])
    assert nov[0]["limit_cents"] == 30000
    assert dec[0]["limit_cents"] == 50000


def test_set_again_replaces(workdir, run_json, run):
    run(["budget", "set", "groceries", "300"])
    run(["budget", "set", "groceries", "310"])
    data = run_json(["budget", "status", "--month", "2026-10", "--format", "json"])
    assert len(data) == 1 and data[0]["limit_cents"] == 31000


def test_status_without_budgets_is_empty(workdir, run):
    code, out, _ = run(["budget", "status", "--month", "2026-10"])
    assert code == 0
    assert out.strip() == ""


def test_status_at_limit_is_not_over(workdir, run):
    run(["budget", "set", "fun", "50"])
    add(run, "2026-10-10", "50", "fun")
    _, out, _ = run(["budget", "status", "--month", "2026-10"])
    assert out.strip() == "fun 50.00/50.00 remaining 0.00"
