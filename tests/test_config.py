from bbterm.config import load_config


def test_defaults_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key is None
    assert cfg.db_path == tmp_path / "data" / "market.duckdb"
    assert cfg.cost_cap_usd == 1.0
    assert cfg.databento_dataset == "EQUS.MINI"


def test_env_var_wins_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('DATABENTO_API_KEY="db-from-file"\n')
    monkeypatch.setenv("DATABENTO_API_KEY", "db-from-env")
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key == "db-from-env"


def test_dotenv_used_when_env_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "# comment\nDATABENTO_API_KEY=db-from-file\nBBTERM_COST_CAP_USD=0.25\n"
    )
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key == "db-from-file"
    assert cfg.cost_cap_usd == 0.25
