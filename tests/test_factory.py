import importlib.util
import sys

import pytest

from bbterm.config import Config
from bbterm.data import build_service

databento_installed = importlib.util.find_spec("databento") is not None


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


@pytest.mark.skipif(
    not databento_installed, reason="databento extra not installed"
)
def test_key_present_uses_databento_for_bars(tmp_path):
    svc = build_service(_config(tmp_path, key="db-test-key"))
    assert svc._bars.name == "databento"
    assert svc._quotes.name == "yfinance"  # quotes stay on free fallback


def test_key_present_but_databento_missing_falls_back(tmp_path, monkeypatch, capsys):
    # Simulate the optional 'databento' package not being installed: a None entry
    # in sys.modules makes the lazy `from ... import DatabentoProvider` raise ImportError.
    monkeypatch.setitem(sys.modules, "bbterm.data.providers.databento_", None)
    svc = build_service(_config(tmp_path, key="db-test-key"))
    assert svc._bars.name == "yfinance"
    assert svc._quotes.name == "yfinance"
    err = capsys.readouterr().err
    assert "databento" in err.lower()
