# Packaging Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make bbterm a clean, AGPL-licensed, verifiably-buildable public package installable via `pipx install git+https://github.com/sgjlee0520/bbterm.git`, with CI.

**Architecture:** Move Databento to an optional dependency behind a lazy import so a core-only install runs on the free yfinance/EDGAR path; complete the distribution metadata and license; add GitHub Actions for tests and tagged builds. No behavior change to the running app beyond a new `--version` flag and a graceful warning when a Databento key is set without the package installed.

**Tech Stack:** Python ≥3.11, setuptools (PEP 639 SPDX license), pytest, GitHub Actions, `build` + `twine`.

## Global Constraints

- License: **AGPL-3.0-or-later** (SPDX expression in `pyproject.toml`; full text in `LICENSE`).
- Build backend pin: **`setuptools>=77`** (required for the bare-string SPDX `license` field).
- Dependency split: **yfinance core, `databento` optional** under the `databento` extra.
- Version is single-sourced in `pyproject.toml` at **`0.1.0`**; first public tag is **`v0.1.0`**.
- Tests make **no network calls** and spend **no credits**.
- **No PyPI publish** in this phase (the `bbterm` name is taken; deferred to Phase 2).
- Work happens on the existing **`packaging-phase1`** branch.
- CI test matrix: **Python 3.11 and 3.12**.

---

### Task 1: Lazy-import refactor + graceful Databento degradation

Make `build_service` import `DatabentoProvider` lazily so a core-only install (no `databento` package) runs, and degrade to yfinance with a warning when a key is set but the package is missing.

**Files:**
- Modify: `src/bbterm/data/__init__.py`
- Test: `tests/test_factory.py`

**Interfaces:**
- Consumes: `Config` (fields `databento_api_key`, `db_path`, `cost_cap_usd`, `databento_dataset`), `build_service(config) -> DataService`.
- Produces: unchanged public signature `build_service(config: Config) -> DataService`. On `databento` ImportError with a key set, returns a `DataService` whose `_bars.name == "yfinance"` and writes a warning to `stderr`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_factory.py`:

```python
import sys

import pytest


def test_key_present_but_databento_missing_falls_back(tmp_path, monkeypatch, capsys):
    # Simulate the optional 'databento' package not being installed: a None entry
    # in sys.modules makes the lazy `from ... import DatabentoProvider` raise ImportError.
    monkeypatch.setitem(sys.modules, "bbterm.data.providers.databento_", None)
    svc = build_service(_config(tmp_path, key="db-test-key"))
    assert svc._bars.name == "yfinance"
    assert svc._quotes.name == "yfinance"
    err = capsys.readouterr().err
    assert "databento" in err.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_factory.py::test_key_present_but_databento_missing_falls_back -v`
Expected: FAIL — current code imports `DatabentoProvider` at module top, so the patch has no effect and `svc._bars.name` is `"databento"` (assertion error).

- [ ] **Step 3: Refactor `build_service` for a lazy, guarded import**

Replace the entire contents of `src/bbterm/data/__init__.py` with:

```python
from __future__ import annotations

import sys

from bbterm.config import Config
from bbterm.data.providers.edgar import EdgarProvider
from bbterm.data.providers.yfinance_ import YFinanceProvider
from bbterm.data.service import DataService
from bbterm.data.store import Store


def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    edgar = EdgarProvider()
    if config.databento_api_key:
        try:
            from bbterm.data.providers.databento_ import DatabentoProvider
        except ImportError:
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

- [ ] **Step 4: Run the new test and the existing factory tests**

Run: `python -m pytest tests/test_factory.py -v`
Expected: PASS — all three tests (`test_no_key_uses_yfinance_for_bars`, `test_key_present_uses_databento_for_bars`, `test_key_present_but_databento_missing_falls_back`).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python -m pytest`
Expected: PASS — previously 88, now 89 tests.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/__init__.py tests/test_factory.py
git commit -m "refactor: lazy Databento import so core-only install runs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `pyproject.toml` distribution metadata + optional Databento

Complete the packaging metadata, adopt the AGPL SPDX license, and move `databento` into an optional extra.

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: nothing new.
- Produces: an installable project with extras `databento` and `dev`; core deps no longer include `databento`.

- [ ] **Step 1: Replace `pyproject.toml`**

Write `pyproject.toml` with:

```toml
[project]
name = "bbterm"
version = "0.1.0"
description = "A local, keyboard-driven Bloomberg-style market terminal for your shell."
readme = "README.md"
requires-python = ">=3.11"
license = "AGPL-3.0-or-later"
authors = [{ name = "sgjlee0520", email = "yagurootajum@gmail.com" }]
keywords = ["terminal", "tui", "finance", "stocks", "bloomberg", "charts", "sec", "edgar"]
classifiers = [
    # No "License ::" classifier — PEP 639 uses the SPDX `license` field above,
    # and setuptools>=77 errors if both are present.
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

[project.scripts]
bbterm = "bbterm.tui.app:main"
bbterm-sync = "bbterm.sync:main"

[project.urls]
Homepage = "https://github.com/sgjlee0520/bbterm"
Repository = "https://github.com/sgjlee0520/bbterm"
Issues = "https://github.com/sgjlee0520/bbterm/issues"

[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Reinstall the project to pick up the new metadata/extras**

Run: `.venv/bin/pip install -e ".[dev,databento]"`
Expected: completes without error (installs `build`, `twine`; `databento` still present via the extra).

- [ ] **Step 3: Confirm no regressions**

Run: `python -m pytest`
Expected: PASS — 89 tests.

- [ ] **Step 4: Build and validate the distribution**

Run: `python -m build && python -m twine check dist/*`
Expected: builds `dist/bbterm-0.1.0.tar.gz` and `dist/bbterm-0.1.0-py3-none-any.whl`; `twine check` reports `PASSED` for both. No license/metadata warnings.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: distribution metadata, AGPL SPDX license, optional databento extra

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

(`dist/` is build output — do not commit it; confirm it is gitignored or leave it unstaged.)

---

### Task 3: Single-source the version + `bbterm --version`

Expose the installed version on the package and add a `--version` CLI flag.

**Files:**
- Modify: `src/bbterm/__init__.py`
- Modify: `src/bbterm/tui/app.py` (the `main()` function, currently at `:256`)
- Test: `tests/test_version.py` (create)

**Interfaces:**
- Consumes: the installed distribution metadata for `bbterm`.
- Produces: `bbterm.__version__: str`; `bbterm.tui.app.main(argv: list[str] | None = None)` that handles `--version` (prints `bbterm {__version__}` and exits 0) before launching the app.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_version.py`:

```python
import pytest

import bbterm
from bbterm.tui.app import main


def test_version_is_nonempty_string():
    assert isinstance(bbterm.__version__, str)
    assert bbterm.__version__


def test_version_flag_prints_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "bbterm" in out
    assert bbterm.__version__ in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_version.py -v`
Expected: FAIL — `bbterm` has no `__version__` attribute, and `main()` takes no arguments.

- [ ] **Step 3: Add `__version__` to the package**

Replace the contents of `src/bbterm/__init__.py` (currently empty) with:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bbterm")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+source"
```

- [ ] **Step 4: Add the `--version` flag to `main()`**

In `src/bbterm/tui/app.py`, add `import argparse` near the top imports (after `from __future__ import annotations`), and add `from bbterm import __version__` with the other `bbterm` imports. Replace the existing `main()` (at `:256`):

```python
def main() -> None:
    BloombergApp().run()
```

with:

```python
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bbterm",
        description="A local, keyboard-driven Bloomberg-style market terminal.",
    )
    parser.add_argument(
        "--version", action="version", version=f"bbterm {__version__}"
    )
    parser.parse_args(argv)
    BloombergApp().run()
```

- [ ] **Step 5: Run the version tests**

Run: `python -m pytest tests/test_version.py -v`
Expected: PASS — both tests.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest`
Expected: PASS — 91 tests.

- [ ] **Step 7: Commit**

```bash
git add src/bbterm/__init__.py src/bbterm/tui/app.py tests/test_version.py
git commit -m "feat: single-sourced __version__ and bbterm --version flag

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Add the AGPL-3.0 `LICENSE`

Add the canonical license text the SPDX field and classifiers refer to.

**Files:**
- Create: `LICENSE`
- Test: `tests/test_license.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: a repo-root `LICENSE` containing the verbatim AGPL-3.0 text.

- [ ] **Step 1: Write the failing test**

Create `tests/test_license.py`:

```python
from pathlib import Path


def test_license_is_agpl_v3():
    text = (Path(__file__).resolve().parents[1] / "LICENSE").read_text()
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in text
    assert "Version 3" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_license.py -v`
Expected: FAIL — `LICENSE` does not exist (`FileNotFoundError`).

- [ ] **Step 3: Download the canonical AGPL-3.0 text**

Run: `curl -fsSL https://www.gnu.org/licenses/agpl-3.0.txt -o LICENSE`
Expected: creates `LICENSE` (~34 KB). Verify the header: `head -3 LICENSE` shows `GNU AFFERO GENERAL PUBLIC LICENSE` and `Version 3, 19 November 2007`.

- [ ] **Step 4: Run the license test**

Run: `python -m pytest tests/test_license.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add LICENSE tests/test_license.py
git commit -m "docs: add AGPL-3.0 LICENSE

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: README install docs, extras, and License section

Update the README so users install via pipx, contributors keep the editable path, the Databento extra is documented, and the license is named.

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: documentation only.

- [ ] **Step 1: Update the Install section**

In `README.md`, replace the current Install section body with an end-user path first, then the contributor path:

````markdown
## Install

End users (isolated install via [pipx](https://pipx.pypa.io/)):

```bash
pipx install git+https://github.com/sgjlee0520/bbterm.git
```

The core install runs on the free yfinance + SEC EDGAR path. To enable the
Databento provider (requires a `DATABENTO_API_KEY`):

```bash
pipx install "git+https://github.com/sgjlee0520/bbterm.git#egg=bbterm[databento]"
```

Contributors (editable, from a clone):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # add ,databento to work on the Databento provider
```
````

- [ ] **Step 2: Add a License section**

Append to the end of `README.md`:

```markdown
## License

bbterm is licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later). See [`LICENSE`](LICENSE). Copyright © 2026 sgjlee0520.
```

- [ ] **Step 3: Verify the edits landed**

Run: `grep -c "pipx install" README.md` → expect `≥ 2`; `grep -c "AGPL-3.0" README.md` → expect `≥ 1`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: pipx install, databento extra, and License section in README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: GitHub Actions CI and release workflows

Add a test workflow on push/PR and an artifact-build workflow on version tags.

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`
- Test: `tests/test_workflows_valid.py` (create)

**Interfaces:**
- Consumes: the `dev` extra and `pytest`.
- Produces: CI config only.

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflows_valid.py` (validates the YAML parses and has the expected triggers):

```python
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load(name):
    return yaml.safe_load((WF / name).read_text())


def test_ci_workflow_runs_pytest_on_push_and_pr():
    wf = _load("ci.yml")
    # PyYAML parses the bare `on:` key as boolean True.
    triggers = wf.get(True, wf.get("on"))
    assert "push" in triggers and "pull_request" in triggers


def test_release_workflow_triggers_on_version_tags():
    wf = _load("release.yml")
    triggers = wf.get(True, wf.get("on"))
    assert "v*" in triggers["push"]["tags"]
```

Note: `pyyaml` is available transitively, but to be safe ensure it is importable — if `import yaml` fails, run `.venv/bin/pip install pyyaml` (test-only; do not add to project deps).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflows_valid.py -v`
Expected: FAIL — workflow files do not exist.

- [ ] **Step 3: Create `ci.yml`**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: pytest
```

- [ ] **Step 4: Create `release.yml`**

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: python -m twine check dist/*
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/*
```

- [ ] **Step 5: Run the workflow validation test**

Run: `python -m pytest tests/test_workflows_valid.py -v`
Expected: PASS — both tests.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml tests/test_workflows_valid.py
git commit -m "ci: pytest on push/PR and build artifacts on version tags

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Clean-venv build proof (acceptance gate)

End-to-end verification that the built artifact installs and runs both core-only and with the Databento extra. No code change; this is the release gate.

**Files:**
- None (verification only).

**Interfaces:**
- Consumes: the built wheel from Task 2 (rebuild to be current).

- [ ] **Step 1: Rebuild current artifacts**

Run: `rm -rf dist && python -m build && python -m twine check dist/*`
Expected: fresh `dist/bbterm-0.1.0-py3-none-any.whl` and sdist; `twine check` PASSED.

- [ ] **Step 2: Core-only install in a throwaway venv**

```bash
python -m venv /tmp/bbterm-core && \
/tmp/bbterm-core/bin/pip install dist/bbterm-0.1.0-py3-none-any.whl && \
/tmp/bbterm-core/bin/python -c "import importlib.util as u; print('databento present:', u.find_spec('databento') is not None)"
```
Expected: install succeeds; prints `databento present: False`.

- [ ] **Step 3: Confirm `--version` and that the service builds without Databento**

```bash
/tmp/bbterm-core/bin/bbterm --version && \
/tmp/bbterm-core/bin/python -c "from bbterm.config import Config; from bbterm.data import build_service; from pathlib import Path; svc=build_service(Config(databento_api_key='x', db_path=Path('/tmp/m.duckdb'), cost_cap_usd=1.0, databento_dataset='EQUS.MINI')); print('bars provider:', svc._bars.name)"
```
Expected: prints `bbterm 0.1.0`; then a stderr warning about the missing `databento` package; then `bars provider: yfinance`.

- [ ] **Step 4: Install the Databento extra and confirm it loads**

```bash
python -m venv /tmp/bbterm-db && \
/tmp/bbterm-db/bin/pip install "dist/bbterm-0.1.0-py3-none-any.whl[databento]" && \
/tmp/bbterm-db/bin/python -c "from bbterm.config import Config; from bbterm.data import build_service; from pathlib import Path; svc=build_service(Config(databento_api_key='x', db_path=Path('/tmp/m2.duckdb'), cost_cap_usd=1.0, databento_dataset='EQUS.MINI')); print('bars provider:', svc._bars.name)"
```
Expected: prints `bars provider: databento` (no warning).

- [ ] **Step 5: Clean up throwaway venvs and build output**

```bash
rm -rf /tmp/bbterm-core /tmp/bbterm-db /tmp/m.duckdb /tmp/m2.duckdb dist
```

- [ ] **Step 6: Final full-suite run**

Run: `python -m pytest`
Expected: PASS — **94 tests** (88 original + 1 factory degradation + 2 version + 1 license + 2 workflow).

---

## Notes for the implementer

- The branch is already `packaging-phase1`; do not create another. Do not merge to `main` — finishing/merge is handled after review.
- Do not publish to PyPI or push tags in this phase. `release.yml` only runs when a `v*` tag is eventually pushed; creating it is fine, triggering it is out of scope here.
- `dist/` is build output; never commit it.
</content>
