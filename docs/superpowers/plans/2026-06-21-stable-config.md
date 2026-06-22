# Stable Config & Data Locations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make bbterm read its database and API keys from fixed XDG locations so it works the same from any directory, and migrate the user's existing data/key over.

**Architecture:** A small change to `config.py`: derive the database path and a config-directory `.env` from `XDG_DATA_HOME`/`XDG_CONFIG_HOME` (with `~/.local/share` and `~/.config` fallbacks), and merge key sources in precedence order. Then a one-time migration copies the user's existing DB and key into the new spots.

**Tech Stack:** Python stdlib (`os`, `pathlib`), pytest.

## Global Constraints

- Database default: `${XDG_DATA_HOME:-~/.local/share}/bbterm/market.duckdb`.
- Config `.env`: `${XDG_CONFIG_HOME:-~/.config}/bbterm/.env`.
- Key precedence (highest wins): exported env vars → config-dir `.env` → cwd `.env`.
- `BBTERM_DB_PATH` still overrides the database path.
- Tests isolate via `XDG_DATA_HOME`/`XDG_CONFIG_HOME` pointed at temp dirs; no network.
- macOS/Linux focus (no Windows `%APPDATA%`).
- Work on the existing **`stable-config`** branch.

---

### Task 1: Fixed XDG paths in `config.py`

**Files:**
- Modify: `src/bbterm/config.py`
- Test: `tests/test_config.py` (rewrite)

**Interfaces:**
- Produces: `load_config(root=None) -> Config` where `db_path` defaults to the XDG
  data path and keys come from the merged sources (exported env > config-dir `.env`
  > cwd `.env`); `BBTERM_DB_PATH` still overrides `db_path`.

- [ ] **Step 1: Write the failing/updated tests**

Replace `tests/test_config.py` with:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL — `test_default_db_path_is_xdg_data` expects the new XDG path (old
code returns `tmp_path/data/market.duckdb`); `test_config_dir_dotenv_picked_up`
fails (config-dir `.env` not read yet).

- [ ] **Step 3: Update `config.py`**

Replace `load_config` (and add the `_xdg_dir` helper) in `src/bbterm/config.py`.
Keep the `Config` dataclass and `_load_dotenv` exactly as they are. The new code:

```python
def _xdg_dir(var: str, default_subdir: str) -> Path:
    base = os.environ.get(var)
    root = Path(base) if base else Path.home() / default_subdir
    return root / "bbterm"


def load_config(root: Path | None = None) -> Config:
    root = root or Path.cwd()
    config_dir = _xdg_dir("XDG_CONFIG_HOME", ".config")
    data_dir = _xdg_dir("XDG_DATA_HOME", ".local/share")
    env = {
        **_load_dotenv(root / ".env"),            # cwd (dev fallback, lowest)
        **_load_dotenv(config_dir / ".env"),      # ~/.config/bbterm/.env
        **os.environ,                             # exported vars (highest)
    }
    return Config(
        databento_api_key=env.get("DATABENTO_API_KEY"),
        db_path=Path(env.get("BBTERM_DB_PATH", str(data_dir / "market.duckdb"))),
        cost_cap_usd=float(env.get("BBTERM_COST_CAP_USD", "1.0")),
        databento_dataset=env.get("BBTERM_DATASET", "EQUS.MINI"),
        lambda_api_key=env.get("LAMBDA_API_KEY"),
    )
```

(`os` and `Path` are already imported at the top of `config.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS — all 6.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — no failures. (`test_config.py` is the only caller of `load_config`;
other tests build `Config`/`DataService` directly.)

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/config.py tests/test_config.py
git commit -m "feat: read DB + keys from fixed XDG locations (cwd-independent)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: One-time migration of the existing DB and key (operational)

No code — copies the user's current data into the new fixed locations so nothing
is lost. Run on the user's machine after Task 1.

- [ ] **Step 1: Create the fixed directories**

Run:
```bash
mkdir -p ~/.local/share/bbterm ~/.config/bbterm
```

- [ ] **Step 2: Copy the existing database (if not already migrated)**

Run:
```bash
[ -f ~/.local/share/bbterm/market.duckdb ] || \
  cp ~/bloomberg/data/market.duckdb ~/.local/share/bbterm/market.duckdb 2>/dev/null
ls -la ~/.local/share/bbterm/market.duckdb
```
Expected: the file exists at the new location (the user's watchlist + cache).

- [ ] **Step 3: Copy the Lambda key into the config-dir `.env`**

Run (only adds it if not already present; never prints the key):
```bash
if ! grep -q LAMBDA_API_KEY ~/.config/bbterm/.env 2>/dev/null; then
  grep '^LAMBDA_API_KEY=' ~/bloomberg/.env >> ~/.config/bbterm/.env
fi
grep -q LAMBDA_API_KEY ~/.config/bbterm/.env && echo "key present in config dir"
```
Expected: `key present in config dir`.

- [ ] **Step 4: Verify it works from an unrelated directory**

Run (from `/tmp`, which has no `.env`, with the dev build):
```bash
cd /tmp && /Users/slee/bloomberg/.venv/bin/python -c "
from bbterm.config import load_config
c = load_config()
print('db_path:', c.db_path)
print('lambda key found:', bool(c.lambda_api_key))
"
```
Expected: `db_path` points at `~/.local/share/bbterm/market.duckdb` and
`lambda key found: True` — proving cwd no longer matters.

---

## Notes for the implementer

- Branch is already `stable-config`.
- Only `config.py` changes; the `Config` dataclass and `_load_dotenv` are untouched.
- Task 2 is a one-time copy on the user's machine; it reads but never prints the key,
  and is safe to re-run (guards against overwriting/duplicating).
