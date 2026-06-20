from datetime import date

from bbterm.data.models import Filing
from bbterm.tui.widgets.filings import FilingsView


def _filing(form="10-K", url="https://sec.gov/x"):
    return Filing(form=form, filed_date=date(2026, 1, 5), period="2025", accession="a", url=url)


def test_open_index_calls_opener_with_url():
    opened = []
    fv = FilingsView(opener=opened.append)
    fv.show([_filing(url="https://sec.gov/aapl"), _filing(url="https://sec.gov/b")])
    fv._open_index(1)
    assert opened == ["https://sec.gov/b"]


def test_open_index_out_of_range_is_noop():
    opened = []
    fv = FilingsView(opener=opened.append)
    fv.show([])
    fv._open_index(0)
    assert opened == []
