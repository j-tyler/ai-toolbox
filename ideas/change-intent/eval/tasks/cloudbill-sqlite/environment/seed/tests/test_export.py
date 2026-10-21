from decimal import Decimal

import pytest
from conftest import COLUMNS

from cloudbill.export import ExportError, LineItem, Reject, parse_money, parse_timestamp, read_export


@pytest.mark.parametrize("text,value", [
    ("12.3400", "12.34"), (" 7 ", "7"), ("1,234.5600", "1234.56"), ("-1,500.0000", "-1500"), ("$5.10", "5.10"),
    ("(3.20)", "-3.20"), ("0.0000", "0"),
])
def test_money_a_person_would_read_the_same_way(text, value):
    assert parse_money(text) == Decimal(value)


@pytest.mark.parametrize("text", ["#VALUE!", "", "12,34", "1,23,456", "NaN", "Infinity", "12.3.4"])
def test_money_that_is_not_a_number(text):
    assert parse_money(text) is None


def test_timestamps_are_utc():
    assert parse_timestamp("2026-08-01T23:30:00-07:00").isoformat() == "2026-08-02T06:30:00+00:00"
    assert parse_timestamp("2026-08-01T00:00:00Z").date().isoformat() == "2026-08-01"
    assert parse_timestamp("2026-08-01 05:00:00").isoformat() == "2026-08-01T05:00:00+00:00"
    assert parse_timestamp("yesterday") is None and parse_timestamp(" ") is None


def test_rows_become_items_or_rejects(write_export):
    path = write_export([
        {"unblended_cost": "2.5000", "service": " compute engine ", "tag:team": " web "},
        {"unblended_cost": "#VALUE!"},
        {"currency": "EUR"},
        {"line_item_id": ""},
        {"usage_start": ""},
        {"line_item_type": "Adjustment"},
        {"line_item_type": "CREDIT", "unblended_cost": "-1"},
    ])
    rows = list(read_export(path))
    items = [r for r in rows if isinstance(r, LineItem)]
    rejects = [r for r in rows if isinstance(r, Reject)]
    assert [(i.service, i.cost, i.tag("team"), i.kind) for i in items] == [
        ("compute engine", Decimal("2.5"), "web", "usage"), ("Compute Engine", Decimal("-1"), None, "credit")]
    assert [r.line for r in rejects] == [3, 4, 5, 6, 7]
    assert "EUR" in rejects[1].reason and "#VALUE!" in rejects[0].reason


def test_start_lines_count_embedded_newlines(write_export):
    path = write_export([
        {"description": "line one\nline two\nline three"},
        ["short", "row"],
        {"description": "fine"},
        ["also", "short", "with\nnewline"],
    ])
    rejects = [r for r in read_export(path) if isinstance(r, Reject)]
    assert [r.line for r in rejects] == [5, 7]


def test_byte_order_mark_and_column_case(write_export, tmp_path):
    path = write_export([{"unblended_cost": "3"}], bom=True)
    assert [r.cost for r in read_export(path)] == [Decimal(3)]
    upper = tmp_path / "upper.csv"
    upper.write_text(path.read_text(encoding="utf-8-sig").replace("line_item_id", "Line_Item_ID", 1), encoding="utf-8")
    assert len(list(read_export(upper))) == 1


def test_not_an_export(tmp_path):
    other = tmp_path / "other.csv"
    other.write_text("name,amount\nx,1\n")
    with pytest.raises(ExportError, match="missing columns"):
        list(read_export(other))
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(ExportError, match="empty"):
        list(read_export(empty))
    with pytest.raises(ExportError, match="cannot open"):
        list(read_export(tmp_path / "missing.csv"))


def test_tag_column_absent_or_blank(write_export):
    columns = [c for c in COLUMNS if c != "tag:team"]
    path = write_export([{"tag:env": "prod"}, {"tag:env": " "}], columns=columns)
    items = list(read_export(path))
    assert [(i.tag("team"), i.tag("env")) for i in items] == [(None, "prod"), (None, None)]
