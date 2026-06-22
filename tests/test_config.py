from bbterm.config import load_config


def _xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    for k in ("DATABENTO_API_KEY", "LAMBDA_API_KEY", "BBTERM_DB_PATH",
              "BBTERM_COST_CAP_USD"):
        monkeypatch.delenv(k, raising=False)


def test_default_db_path_is_xdg_data(tmp_path, monkeypatch):
    _xdg(tmp_path, monkeypatch)
    cfg = load_config(root=tmp_path)
    assert cfg.db_path == tmp_path / "data" / "bbterm" / "market.duckdb"
    assert cfg.databento_api_key is None
    assert cfg.cost_cap_usd == 1.0
    assert cfg.databento_dataset == "EQUS.MINI"


def test_config_dir_dotenv_picked_up(tmp_path, monkeypatch):
    _xdg(tmp_path, monkeypatch)
    cfgdir = tmp_path / "config" / "bbterm"
    cfgdir.mkdir(parents=True)
    (cfgdir / ".env").write_text("LAMBDA_API_KEY=from-config-dir\n")
    cfg = load_config(root=tmp_path)
    assert cfg.lambda_api_key == "from-config-dir"


def test_exported_env_overrides_config_dir(tmp_path, monkeypatch):
    _xdg(tmp_path, monkeypatch)
    cfgdir = tmp_path / "config" / "bbterm"
    cfgdir.mkdir(parents=True)
    (cfgdir / ".env").write_text("LAMBDA_API_KEY=from-config-dir\n")
    monkeypatch.setenv("LAMBDA_API_KEY", "from-export")
    cfg = load_config(root=tmp_path)
    assert cfg.lambda_api_key == "from-export"


def test_cwd_dotenv_used_as_fallback(tmp_path, monkeypatch):
    _xdg(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text(
        "DATABENTO_API_KEY=db-from-cwd\nBBTERM_COST_CAP_USD=0.25\n"
    )
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key == "db-from-cwd"
    assert cfg.cost_cap_usd == 0.25


def test_bbterm_db_path_overrides(tmp_path, monkeypatch):
    _xdg(tmp_path, monkeypatch)
    monkeypatch.setenv("BBTERM_DB_PATH", str(tmp_path / "custom.duckdb"))
    cfg = load_config(root=tmp_path)
    assert cfg.db_path == tmp_path / "custom.duckdb"


def test_exported_env_wins_over_cwd_dotenv(tmp_path, monkeypatch):
    _xdg(tmp_path, monkeypatch)
    (tmp_path / ".env").write_text('DATABENTO_API_KEY="db-from-file"\n')
    monkeypatch.setenv("DATABENTO_API_KEY", "db-from-env")
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key == "db-from-env"
