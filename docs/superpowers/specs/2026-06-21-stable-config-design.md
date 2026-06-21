# Stable Config & Data Locations

**Date:** 2026-06-21
**Status:** Approved (brainstorming, 2026-06-21)

## Goal

Make bbterm read its **database** and **API keys** from fixed, standard locations
instead of the current working directory, so it behaves identically no matter which
folder you launch it from. This retires a recurring class of bugs (missing
`LAMBDA_API_KEY`, duplicate/empty databases, DuckDB lock conflicts) caused by the
cwd-relative defaults.

## Problem (today)

`config.py` builds both paths from `Path.cwd()`:
- `.env` is read from `./.env` (the launch directory).
- `db_path` defaults to `./data/market.duckdb`.

So launching from `~` vs `~/bloomberg` yields different databases and may not find
the key — confusing and lock-prone.

## Locations (XDG standard)

- **Database:** `${XDG_DATA_HOME:-~/.local/share}/bbterm/market.duckdb`
- **Config `.env`:** `${XDG_CONFIG_HOME:-~/.config}/bbterm/.env`

Respecting `XDG_DATA_HOME`/`XDG_CONFIG_HOME` (with the `~/.local/share` and
`~/.config` fallbacks) keeps it standard on macOS/Linux and makes it testable by
pointing those env vars at temp dirs.

## Key/value precedence (highest wins)

1. Real environment variables (`os.environ`) — e.g. an exported `LAMBDA_API_KEY`.
2. `~/.config/bbterm/.env` (the fixed config file).
3. `./.env` in the current directory (kept as a dev convenience / fallback).

`BBTERM_DB_PATH` continues to override the database path entirely.

## Code change (`config.py`)

- `_load_dotenv` is unchanged; `load_config` now merges three sources in the
  precedence order above:
  ```python
  env = {
      **_load_dotenv(cwd / ".env"),
      **_load_dotenv(config_dir / ".env"),
      **os.environ,
  }
  ```
- The default `db_path` becomes the XDG data path above (still overridable by
  `BBTERM_DB_PATH`).
- `config_dir` / `data_dir` are derived from `XDG_CONFIG_HOME`/`XDG_DATA_HOME` with
  the home-dir fallbacks. `load_config` keeps its optional `root` parameter for the
  cwd `.env` (defaults to `Path.cwd()`), so existing tests still pass.
- The DB's parent directory is created if missing (the `Store` already does
  `path.parent.mkdir(parents=True, exist_ok=True)`).

## One-time migration (run on the user's machine during rollout — not code)

- If `~/.local/share/bbterm/market.duckdb` does not exist, copy
  `~/bloomberg/data/market.duckdb` to it (preserving watchlist + cached data).
- Copy the `LAMBDA_API_KEY` line from `~/bloomberg/.env` into
  `~/.config/bbterm/.env` (so `POL` works from any directory immediately).
- Done once, by hand, as part of finishing this work.

## Testing (no network)

All config tests set `XDG_DATA_HOME` and `XDG_CONFIG_HOME` to temp dirs
(monkeypatch) so they're isolated from the real `~/.config`/`~/.local/share`.

- `test_config.py`:
  - **Update** `test_defaults_when_nothing_set`: its old assertion
    `db_path == tmp_path/"data"/"market.duckdb"` changes to the new XDG default,
    `db_path == <XDG_DATA_HOME>/"bbterm"/"market.duckdb"` (set `XDG_DATA_HOME` to a
    temp dir). The dataset/cost-cap assertions are unchanged.
  - A `LAMBDA_API_KEY` written to `${XDG_CONFIG_HOME}/bbterm/.env` is picked up.
  - An **exported** `LAMBDA_API_KEY` (os.environ) overrides the config-dir `.env`.
  - `BBTERM_DB_PATH` still overrides `db_path`.
  - The two existing key-precedence tests (`test_env_var_wins_over_dotenv`,
    `test_dotenv_used_when_env_absent`) keep working (cwd `.env` via `root`), with
    `XDG_CONFIG_HOME` pointed at a temp dir for isolation.

## Out of scope

Auto-detecting/migrating arbitrary old database locations (the cwd-relative old
default isn't reliably discoverable); a Windows `%APPDATA%` path (macOS/Linux
focus); any change to what's stored.
