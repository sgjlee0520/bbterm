# Packaging Phase 1 — Public Open-Source Release

**Date:** 2026-06-19
**Status:** Approved (brainstorming, 2026-06-19)
**Builds on:** Phases 1–4 (shipped). Core product is feature-complete; this is the
first of the "business track" items (see `2026-06-12-terminal-rebuild-design.md`
item 5).

## Goal

Turn bbterm into a clean, properly-licensed, verifiably-buildable **public
open-source package** that anyone can install with:

```bash
pipx install git+https://github.com/sgjlee0520/bbterm.git
```

The metadata is written once so that PyPI and Homebrew become small follow-up
increments, not rework.

### Two-track context

The near-term deliverable is the **public** open-source bbterm on GitHub. A more
advanced **private** fork may follow later for a commercial product; the design
keeps clean module boundaries so that fork stays easy. Because the author holds
the copyright, the public AGPL license does not constrain the private fork.

## Scope

- Complete `pyproject.toml` distribution metadata.
- Add an **AGPL-3.0** `LICENSE`.
- Restructure dependencies: **yfinance core, Databento optional** — with the
  lazy-import refactor that makes a core-only install runnable.
- Single-source the version and expose it (`bbterm --version`).
- **CI** (GitHub Actions): test on push/PR; build artifacts on a version tag.
- Update the README install docs.

### Non-goals (deferred)

- **PyPI publishing.** The name `bbterm` is already taken on PyPI by an unrelated
  "BBS Terminal" project (v0.0.4). Phase 2 will publish under a distinct
  *distribution* name (e.g. `bbterm-tui`) while keeping the *import* package
  `bbterm`. Choosing that name is a deliberate Phase 2 decision.
- **Homebrew formula** — Phase 3.
- **The private advanced fork** — separate future effort.
- Removing yfinance. For an open-source (non-commercial) release, yfinance is
  fine: the library is Apache-2.0, and Yahoo's ToS concern is about *commercial
  use of the data*, which a private commercial fork — not this release — must
  address.

## Distribution strategy (phased)

1. **Phase 1 (this spec):** GitHub + `pipx install git+…`. No external accounts,
   no PyPI namespace, isolated install.
2. **Phase 2 (later):** PyPI under a new distribution name, via Trusted
   Publishing.
3. **Phase 3 (later):** Homebrew formula / tap.

## `pyproject.toml` metadata

Add the fields a real distribution needs; keep the existing build-system and
src-layout discovery. Version stays `0.1.0` (single source of truth here).

```toml
[project]
name = "bbterm"
version = "0.1.0"
description = "A local, keyboard-driven Bloomberg-style market terminal for your shell."
readme = "README.md"
requires-python = ">=3.11"
license = "AGPL-3.0-or-later"          # SPDX expression
authors = [{ name = "sgjlee0520", email = "yagurootajum@gmail.com" }]
keywords = ["terminal", "tui", "finance", "stocks", "bloomberg", "charts", "sec", "edgar"]
classifiers = [
    # No "License ::" classifier — PEP 639 uses the SPDX `license` field above,
    # and recent setuptools errors if both are present.
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Financial and Insurance Industry",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Office/Business :: Financial :: Investment",
]
dependencies = [
    "textual>=0.47.0",
    "plotext>=5.2.8",
    "duckdb>=0.9.0",
    "pandas>=2.0.0",
    "yfinance>=0.2.36",
]

[project.optional-dependencies]
databento = ["databento>=0.34.0"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "build", "twine"]

[project.urls]
Homepage = "https://github.com/sgjlee0520/bbterm"
Repository = "https://github.com/sgjlee0520/bbterm"
Issues = "https://github.com/sgjlee0520/bbterm/issues"
```

Notes:
- `databento` moves from core `dependencies` to an optional extra.
- `build` and `twine` are added to `dev` so local build verification needs no
  ad-hoc installs.
- The bare-string SPDX `license` expression (PEP 639) needs a recent setuptools,
  so bump the build-system: `requires = ["setuptools>=77"]`. The `License ::`
  trove classifier is omitted on purpose (see the classifiers note above).
- Keep `[project.scripts]`, `[tool.setuptools.packages.find]`, and
  `[tool.pytest.ini_options]` as they are.

## Dependency restructure + lazy-import refactor

Making Databento optional requires a code change. Today
`src/bbterm/data/__init__.py:4` does:

```python
from bbterm.data.providers.databento_ import DatabentoProvider
```

at module top level, and `databento_.py:5` does `import databento as db`. On a
core-only install (no `databento` package), importing `bbterm.data` raises
`ImportError` and the whole app fails to start.

**Fix:** remove the top-level `DatabentoProvider` import from `data/__init__.py`
and import it lazily inside `build_service`, only on the branch that actually
needs it, degrading gracefully if the package is absent:

```python
def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    edgar = EdgarProvider()
    if config.databento_api_key:
        try:
            from bbterm.data.providers.databento_ import DatabentoProvider
        except ImportError:
            # Key set but the optional package isn't installed — warn and fall back.
            print(
                "DATABENTO_API_KEY is set but the 'databento' package is not "
                "installed. Run: pip install 'bbterm[databento]'. "
                "Falling back to yfinance.",
                file=sys.stderr,
            )
        else:
            bars = DatabentoProvider(
                api_key=config.databento_api_key,
                dataset=config.databento_dataset,
                cost_cap_usd=config.cost_cap_usd,
            )
            return DataService(store, bars, yf_provider, edgar_provider=edgar)
    return DataService(store, yf_provider, yf_provider, edgar_provider=edgar)
```

`databento_.py` keeps its own top-level `import databento` — it is now only
imported when `build_service` reaches the Databento branch with the package
present. No other call sites import `DatabentoProvider` (verified).

## Version single-sourcing

`pyproject.toml` remains the only place the version is written. Expose it at
runtime in the currently-empty `src/bbterm/__init__.py`:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bbterm")
except PackageNotFoundError:        # running from a source tree, not installed
    __version__ = "0.0.0+source"
```

Add a `--version` flag to the `bbterm` CLI (`tui/app.py:main`) that prints
`bbterm {__version__}` and exits, handled before the Textual app launches. No
duplicated version strings anywhere.

## LICENSE

Add the full **GNU AGPL-3.0** license text as `LICENSE` at the repo root, with
the copyright line `Copyright (C) 2026 sgjlee0520`. Add a short **License**
section to the README pointing to it and naming AGPL-3.0.

## CI — GitHub Actions

Two workflows under `.github/workflows/`:

### `ci.yml` — test on push and PR

- Triggers: `push` and `pull_request`.
- Matrix: Python **3.11** and **3.12**.
- Steps: checkout → setup-python → `pip install -e ".[dev]"` → `pytest`.
- The suite makes no network calls and spends no credits, so CI is hermetic.

### `release.yml` — build artifacts on a version tag

- Trigger: `push` of a tag matching `v*`.
- Steps: checkout → setup-python (3.12) → `pip install build twine` →
  `python -m build` → `twine check dist/*` → attach `dist/*` (wheel + sdist) to
  the GitHub Release.
- **No PyPI publish** in Phase 1.

## README updates

- Install section leads with the end-user path
  (`pipx install git+https://github.com/sgjlee0520/bbterm.git`), keeps the
  contributor path (`pip install -e ".[dev]"`), and documents the optional
  `pip install 'bbterm[databento]'` extra.
- Add a **License** section naming AGPL-3.0 and linking `LICENSE`.
- Optionally add a CI status badge.

## Testing & verification

Run before tagging `v0.1.0`:

1. **Existing suite:** all 88 tests still pass (`python -m pytest`).
2. **New unit test:** `build_service` degrades gracefully when the `databento`
   import fails. Set a fake `databento_api_key` in `Config`, patch the lazy
   import to raise `ImportError`, and assert (a) no exception escapes, (b) a
   `DataService` is returned using the yfinance provider for bars, (c) the
   warning is emitted. This exercises the core-only-install path even in a dev
   environment where `databento` is installed.
3. **Manual build proof:**
   - `python -m build` and `twine check dist/*` succeed.
   - In a clean throwaway venv, `pip install dist/bbterm-0.1.0-*.whl` (core
     only), confirm `bbterm --version` prints, and `bbterm` launches and runs on
     the yfinance/EDGAR path **with `databento` not installed**.
   - `pip install 'dist/bbterm-0.1.0-*.whl[databento]'` and confirm the
     Databento provider loads when a key is set.

## Error handling

- `DATABENTO_API_KEY` set but `databento` package missing → stderr warning,
  fall back to yfinance, no crash (covered by the new unit test).
- All existing degrade-to-cache and cost-cap behavior is unchanged.

## Alternatives considered

- **Full PyPI automation now (Trusted Publishing on tag):** rejected for Phase 1.
  PyPI releases are immutable, the build is unproven until we install a wheel in
  a clean env, and — decisively — the `bbterm` name is already taken on PyPI.
  Deferred to Phase 2 with a new distribution name.
- **Keep everything as core deps (databento always installed):** rejected;
  forces every user to pull the large databento SDK they may never use, and
  muddies the "yfinance is the free default" story.
- **EDGAR-only slim core (both providers optional):** rejected; a bare install
  would show almost no price data — worst first-run experience.
- **MIT/Apache-2.0 license:** rejected in favor of AGPL-3.0 to keep the
  open-core defense (no one can take the public version closed-source or
  closed-SaaS); the author's private fork is unaffected since they hold
  copyright.
</content>
</invoke>
