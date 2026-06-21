from bbterm.data.congress import (
    CONGRESS_ROSTER, PoliticianSummary, filter_to_roster, parse_congress_trades,
    summarize,
)

PAYLOAD = {
    "trades": [
        {"symbol": "NVDA", "representative": "Gilbert Cisneros",
         "transactionDate": "2025-11-18", "type": "Purchase",
         "amount": "$15,001 - $50,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Gilbert Cisneros",
         "transactionDate": "2025-10-17", "type": "Purchase",
         "amount": "$1,001 - $15,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Nancy Pelosi",
         "transactionDate": "2025-09-01", "type": "Sale (Full)",
         "amount": "$250,001 - $500,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Dwight Evans",  # not on roster
         "transactionDate": "2025-11-21", "type": "Purchase",
         "amount": "$1,001 - $15,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Some One",
         "transactionDate": "2025-08-01", "type": "Exchange",  # skipped type
         "amount": "$1,001 - $15,000", "chamber": "house"},
    ],
    "count": 5, "days": 730,
}


def test_parse_maps_type_amount_and_skips_non_buy_sell():
    trades = parse_congress_trades(PAYLOAD)
    # 4 Purchase/Sale rows; the Exchange row is skipped
    assert len(trades) == 4
    cisneros = [t for t in trades if t.politician == "Gilbert Cisneros"][0]
    assert cisneros.side == "BUY"
    assert (cisneros.amount_low, cisneros.amount_high) == (15001.0, 50000.0)
    pelosi = [t for t in trades if t.politician == "Nancy Pelosi"][0]
    assert pelosi.side == "SELL"


def test_filter_keeps_roster_with_first_name_variant_drops_others():
    trades = filter_to_roster(parse_congress_trades(PAYLOAD))
    names = {t.politician for t in trades}
    assert "Gilbert Cisneros" in names   # roster has "Gil Cisneros"
    assert "Nancy Pelosi" in names
    assert "Dwight Evans" not in names   # not on roster
    # newest first
    assert trades[0].date >= trades[-1].date


def test_summarize_counts_and_net_estimate():
    trades = filter_to_roster(parse_congress_trades(PAYLOAD))
    s = {x.politician: x for x in summarize(trades)}
    cis = s["Gilbert Cisneros"]
    assert cis.n_buys == 2 and cis.n_sells == 0
    # net = mid(15001,50000) + mid(1001,15000) = 32500.5 + 8000.5 = 40501.0
    assert cis.net_estimate == 40501.0
    pel = s["Nancy Pelosi"]
    assert pel.n_sells == 1 and pel.net_estimate == -375000.5


def test_roster_is_nonempty():
    assert "Nancy Pelosi" in CONGRESS_ROSTER and len(CONGRESS_ROSTER) >= 10
