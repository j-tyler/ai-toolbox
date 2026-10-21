from decimal import Decimal

from cloudbill import resolve
from cloudbill.resolve import Input


def _costs(paths):
    return sorted((i.line_item_id, i.cost) for i in Input(paths).items())


def test_later_restatement_wins_wherever_it_is(write_export):
    path = write_export([
        {"line_item_id": "a", "unblended_cost": "9", "last_updated": "2026-09-05T00:00:00Z"},  # restatement first
        {"line_item_id": "b", "unblended_cost": "1"},
        {"line_item_id": "a", "unblended_cost": "5"},
        {"line_item_id": "c", "unblended_cost": "2"},
        {"line_item_id": "c", "unblended_cost": "3", "last_updated": "2026-09-01T00:00:00Z"},
    ])
    assert _costs([path]) == [("a", Decimal(9)), ("b", Decimal(1)), ("c", Decimal(3))]


def test_tie_goes_to_the_later_row(write_export):
    path = write_export([{"line_item_id": "a", "unblended_cost": "1"}, {"line_item_id": "a", "unblended_cost": "2"}])
    assert _costs([path]) == [("a", Decimal(2))]


def test_restatement_across_files_in_either_order(write_export):
    aug = write_export([{"line_item_id": "x", "unblended_cost": "10"}, {"line_item_id": "y"}], name="aug.csv")
    sep = write_export([{"line_item_id": "x", "unblended_cost": "12", "last_updated": "2026-09-03T00:00:00Z"}], name="sep.csv")
    assert _costs([aug, sep]) == _costs([sep, aug]) == [("x", Decimal(12)), ("y", Decimal(1))]


def test_rejected_rows_never_restate(write_export):
    path = write_export([{"line_item_id": "a", "unblended_cost": "4"},
                         {"line_item_id": "a", "unblended_cost": "oops", "last_updated": "2026-09-09T00:00:00Z"}])
    source = Input([path])
    assert [i.cost for i in source.items()] == [Decimal(4)]
    assert len(source.rejects) == 1


def test_spilled_runs_give_the_same_answer(write_export, monkeypatch):
    rows = [{"line_item_id": f"id{i % 37}", "unblended_cost": str(i), "last_updated": f"2026-09-01T00:00:{i % 60:02d}Z"}
            for i in range(200)]
    path = write_export(rows)
    expected = _costs([path])
    monkeypatch.setattr(resolve, "RUN", 16)
    assert _costs([path]) == expected
    assert len(expected) == 37
