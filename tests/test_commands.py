import pytest
from bbterm.commands import (
    parse_command, LoadSymbol, AddSymbol, RemoveSymbol,
    ShowChart, ShowStats, Help, Unknown,
)


@pytest.mark.parametrize("text,expected", [
    ("AAPL", LoadSymbol("AAPL")),
    ("  aapl  ", LoadSymbol("AAPL")),
    ("BRK.B", LoadSymbol("BRK.B")),
    ("BTC-USD", LoadSymbol("BTC-USD")),
    ("ADD TSLA", AddSymbol("TSLA")),
    ("add tsla", AddSymbol("TSLA")),
    ("DEL SPY", RemoveSymbol("SPY")),
    ("REMOVE SPY", RemoveSymbol("SPY")),
    ("GP", ShowChart()),
    ("DES", ShowStats()),
    ("?", Help()),
    ("HELP", Help()),
])
def test_parse_known_forms(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize("text", [
    "", "   ",
    "ADD",            # verb missing required arg
    "DEL",
    "this is not a command",
    "@#$",
    "TOOLONGSYM",     # >6 chars, not a verb
])
def test_parse_unknown_or_empty(text):
    result = parse_command(text)
    assert isinstance(result, Unknown)


from bbterm.commands import ShowFilings, ShowFundamentals


def test_fa_parses_to_show_fundamentals():
    assert isinstance(parse_command("FA"), ShowFundamentals)
    assert isinstance(parse_command("fa"), ShowFundamentals)


def test_fil_parses_to_show_filings():
    assert isinstance(parse_command("FIL"), ShowFilings)


def test_n_parses_to_show_news():
    from bbterm.commands import ShowNews
    assert isinstance(parse_command("N"), ShowNews)
