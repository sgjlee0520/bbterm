from bbterm.config import Config
from bbterm.data import build_service


def _config(tmp_path, key=None):
    return Config(
        databento_api_key=key,
        db_path=tmp_path / "m.duckdb",
        cost_cap_usd=1.0,
        databento_dataset="EQUS.MINI",
    )


def test_no_key_uses_yfinance_for_bars(tmp_path):
    svc = build_service(_config(tmp_path))
    assert svc._bars.name == "yfinance"
    assert svc._quotes.name == "yfinance"
