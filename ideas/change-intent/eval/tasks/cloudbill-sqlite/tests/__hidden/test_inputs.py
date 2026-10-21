"""Reading exports: what is accepted, what is rejected, and the exit codes. One rule per test."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import billing_gen as g
from conftest import by_key, close, mentions_rejected

T = datetime(2026, 8, 3, tzinfo=timezone.utc)


def item(cost="1.0000", **kw) -> g.Item:
    kw.setdefault("account_id", "111111111111")
    kw.setdefault("service", "Compute Engine")
    kw.setdefault("start", T)
    return g.Item(kw.pop("line_item_id", None) or g.new_id(), kw.pop("account_id"), kw.pop("service"), kw.pop("start"), cost, **kw)


def write(tmp_path: Path, items, name="export.csv", **kw) -> tuple[g.Export, Path]:
    ex = g.Export(items, **kw)
    return ex, ex.write(tmp_path / name)


def test_byte_order_mark_and_crlf_are_an_export(tmp_path, cli_json):
    _, path = write(tmp_path, [item("2.5000"), item("1.5000")], bom=True, newline="\r\n")
    doc = cli_json("costs", "--by", "service", path)
    assert close(doc["total"]["net"], "4") and doc["rejected_rows"] == 0


def test_not_a_billing_export_exits_1(tmp_path, cli):
    _, good = write(tmp_path, [item()])
    assert cli("costs", "--by", "service", good)[0] == 0  # the tool runs at all
    other = tmp_path / "budget.csv"
    other.write_text("team,limit\nweb,100\n", encoding="utf-8")
    code, out, err = cli("costs", "--by", "service", other)
    assert code == 1 and out == "" and err.strip()


def test_missing_file_exits_1(tmp_path, cli):
    _, good = write(tmp_path, [item()])
    assert cli("daily", good)[0] == 0  # the tool runs at all
    code, out, err = cli("daily", good, tmp_path / "no-such-export.csv")
    assert code == 1 and out == "" and err.strip()


def test_command_line_mistakes_exit_2(tmp_path, cli):
    _, path = write(tmp_path, [item()])
    for args in (["forecast", path], ["daily", "--from", "2026-13-01", path], ["costs", "--by", "colour", path],
                 ["daily", "--format", "xml", path]):
        code, out, _ = cli(*args)
        assert code == 2, f"{args[:3]} exited {code}"


def test_wrong_field_count_is_rejected_and_reported_by_start_line(tmp_path, cli_json):
    items = [item(description="first line\nsecond line\nthird line"), item(bad="long"), item(),
             item(bad="short", usage_type="Box\nUsage"), item("2")]
    ex, path = write(tmp_path, items)
    doc = cli_json("rejects", path)
    assert doc["rejected_rows"] == 2
    assert sorted(int(r["line"]) for r in doc["rows"]) == [ex.lines[1], ex.lines[3]]
    assert all(Path(str(r["file"])).name == "export.csv" and str(r["reason"]).strip() for r in doc["rows"])
    assert close(cli_json("costs", "--by", "service", path)["total"]["net"], "4")


def test_cost_that_is_not_a_number_is_rejected(tmp_path, cli_json):
    _, path = write(tmp_path, [item("3"), item(bad="cost")])
    doc = cli_json("costs", "--by", "account", path)
    assert doc["rejected_rows"] == 1 and close(doc["total"]["net"], "3")


def test_missing_id_or_usage_start_is_rejected(tmp_path, cli_json):
    _, path = write(tmp_path, [item("3"), item(bad="id"), item(bad="start")])
    doc = cli_json("costs", "--by", "account", path)
    assert doc["rejected_rows"] == 2 and close(doc["total"]["net"], "3")


def test_other_currency_is_rejected_not_converted(tmp_path, cli_json):
    _, path = write(tmp_path, [item("3"), item("49", currency="EUR")])
    doc = cli_json("costs", "--by", "service", path)
    assert doc["rejected_rows"] == 1 and close(doc["total"]["net"], "3")


def test_unknown_line_item_type_is_rejected(tmp_path, cli_json):
    _, path = write(tmp_path, [item("3"), item("5", bad="kind")])
    doc = cli_json("costs", "--by", "service", path)
    assert doc["rejected_rows"] == 1 and close(doc["total"]["net"], "3")


def test_thousands_separators_and_whitespace_are_read_as_numbers(tmp_path, cli_json):
    _, path = write(tmp_path, [item("1234.5600", cost_text="1,234.5600"), item("2", cost_text=" 2.0000 "),
                               item("-1500", cost_text="-1,500.0000", line_item_type="Credit")])
    doc = cli_json("costs", "--by", "service", path)
    assert doc["rejected_rows"] == 0
    assert close(doc["total"]["charges"], "1236.56") and close(doc["total"]["credits"], "-1500")


def test_line_item_type_is_case_insensitive(tmp_path, cli_json):
    _, path = write(tmp_path, [item("5", line_item_type="TAX"), item("-2", line_item_type="refund")])
    doc = cli_json("costs", "--by", "service", path)
    assert doc["rejected_rows"] == 0 and close(doc["total"]["charges"], "5") and close(doc["total"]["credits"], "-2")


def test_header_only_file_is_an_empty_answer_or_unusable(tmp_path, cli):
    """The brief does not say whether an export with a header and no rows is usable, so both readings
    pass: an empty answer (exit 0, no rows, nothing rejected, net 0), or exit 1 with a message on
    standard error and nothing on standard output. What may not happen is an answer that is wrong."""
    _, good = write(tmp_path, [item()], name="good.csv")
    assert cli("costs", "--by", "service", good)[0] == 0  # the tool runs at all
    _, path = write(tmp_path, [])
    code, out, err = cli("costs", "--by", "service", "--format", "json", path)
    if code == 1:
        assert out == "" and err.strip()
        return
    assert code == 0, f"exit {code}: {err[-500:]}"
    doc = json.loads(out)
    assert doc["rows"] == [] and doc["rejected_rows"] == 0 and close(doc["total"]["net"], "0")


def test_day_is_the_utc_day_of_usage_start(tmp_path, cli_json):
    late = datetime(2026, 8, 4, 2, 0, tzinfo=timezone.utc)  # 2026-08-03 19:00 in the local column
    _, path = write(tmp_path, [item("7", start=late, end=late + timedelta(hours=1)), item("1")])
    rows = by_key(cli_json("daily", path)["rows"], field="date")
    assert close(rows["2026-08-04"]["net"], "7") and close(rows["2026-08-03"]["net"], "1")


def test_restatement_wins_before_or_after_the_original(tmp_path, cli_json):
    a, b = item("5"), item("8")
    later = T + timedelta(days=20)
    items = [g.Item(b.line_item_id, b.account_id, b.service, b.start, "2", last_updated=later), a, b,
             g.Item(a.line_item_id, a.account_id, a.service, a.start, "6", last_updated=later)]
    _, path = write(tmp_path, items)
    doc = cli_json("costs", "--by", "service", path)
    assert close(doc["total"]["net"], "8") and doc["rejected_rows"] == 0


def test_restatement_across_files_in_either_order(tmp_path, cli_json):
    a = item("5")
    _, aug = write(tmp_path, [a, item("1")], name="aug.csv")
    _, sep = write(tmp_path, [g.Item(a.line_item_id, a.account_id, a.service, a.start, "9", billing_period="2026-08",
                                     last_updated=T + timedelta(days=33))], name="sep.csv")
    for files in ((aug, sep), (sep, aug)):
        assert close(cli_json("costs", "--by", "service", *files)["total"]["net"], "10")


def test_services_differing_only_in_case_are_one_service(tmp_path, cli_json):
    _, path = write(tmp_path, [item("1", service="Object Storage"), item("2", service="object storage"),
                               item("4", service="OBJECT STORAGE "), item("8", service="Kubernetes")])
    rows = by_key(cli_json("costs", "--by", "service", path)["rows"], by="service")
    assert set(rows) == {"object storage", "kubernetes"} and close(rows["object storage"]["net"], "7")


def test_accounts_are_ids_not_names(tmp_path, cli_json):
    _, path = write(tmp_path, [item("1", account_id="012345678901", account_name="old-name"),
                               item("2", account_id="012345678901", account_name="new-name", start=T + timedelta(days=1)),
                               item("4", account_id="999999999999", account_name="new-name")])
    rows = by_key(cli_json("costs", "--by", "account", path)["rows"])
    assert set(rows) == {"012345678901", "999999999999"} and close(rows["012345678901"]["net"], "3")


def test_blank_tag_and_missing_tag_column_are_untagged(tmp_path, cli_json):
    _, f1 = write(tmp_path, [item("1", tags={"team": "web"}), item("2", tags={"team": " "})], name="a.csv")
    cols = [c for c in g.COLUMNS if c != "tag:team"]
    _, f2 = write(tmp_path, [item("4", tags={"team": "web"})], name="b.csv", columns=cols)
    rows = by_key(cli_json("costs", "--by", "tag:team", f1, f2)["rows"])
    assert set(rows) == {"web", None} and close(rows["web"]["net"], "1") and close(rows[None]["net"], "6")


def test_rejected_count_is_for_the_whole_input_whatever_the_range(tmp_path, cli, cli_json):
    _, path = write(tmp_path, [item("1"), item(bad="cost"), item("2", start=T + timedelta(days=10))])
    doc = cli_json("costs", "--by", "service", "--from", "2026-08-10", path)
    assert doc["rejected_rows"] == 1 and close(doc["total"]["net"], "2")
    code, out, _ = cli("costs", "--by", "service", "--from", "2026-08-10", path)
    assert code == 0 and mentions_rejected(out, 1)
