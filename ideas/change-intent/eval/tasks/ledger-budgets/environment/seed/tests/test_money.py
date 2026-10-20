import pytest

from ledger.money import MoneyError, format_cents, parse_amount


@pytest.mark.parametrize(
    "text,cents",
    [("12.50", 1250), ("12.5", 1250), ("12", 1200), ("0.07", 7), ("-3.07", -307), ("$4.00", 400)],
)
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize("text", ["abc", "1.234", "1,000", ""])
def test_parse_amount_rejects(text):
    with pytest.raises(MoneyError):
        parse_amount(text)


def test_format_cents():
    assert format_cents(1250) == "12.50"
    assert format_cents(7) == "0.07"
    assert format_cents(-307) == "-3.07"
