# Packaging Phase 2 — Publish to PyPI

**Date:** 2026-06-20
**Status:** Approved (brainstorming, 2026-06-20)
**Builds on:** Packaging Phase 1 (`2026-06-19-packaging-design.md`) — shipped as the
GitHub-only `v0.1.0` release.

## Goal

Publish bbterm to the Python Package Index so users can
`pipx install bbterm-tui` / `pip install bbterm-tui`, using GitHub Actions
**Trusted Publishing** (OIDC, no stored secrets), **rehearsed on TestPyPI first**.

## Decisions (locked during brainstorming)

- **Distribution name: `bbterm-tui`.** The name `bbterm` is taken on PyPI by an
  unrelated "BBS Terminal" project. The *import package* and *CLI command* stay
  `bbterm` (the `scikit-learn`→`sklearn` pattern). "bloomberg" is deliberately
  avoided in the published name (trademark risk).
- **Auth: Trusted Publishing / OIDC.** No API tokens stored in GitHub.
- **TestPyPI rehearsal before the real publish.** PyPI versions are immutable, so
  the upload pipeline is validated on a throwaway index first.
- **Orchestration A:** a separate manual `testpypi.yml` for rehearsal; the
  existing `release.yml` (on `v*` tags) gains a real-PyPI publish job.

## Scope

- Rename the distribution to `bbterm-tui`; bump version to `0.1.1`.
- Fix the version lookup to key on the new distribution name.
- Add `testpypi.yml` (manual rehearsal) and extend `release.yml` (real publish).
- Document the Trusted Publishing setup the maintainer performs out-of-band.
- Update the README install docs.

### Non-goals

- Homebrew formula (Phase 3).
- Any change to the import package name, the `bbterm` command, or app behavior.
- Removing or changing the GitHub `v0.1.0` release (it stays as the
  GitHub-only milestone).

## Package identity change

### `pyproject.toml`

- `name = "bbterm"` → `name = "bbterm-tui"`.
- `version = "0.1.0"` → `version = "0.1.1"`. A new tag is required to trigger
  publishing regardless, so the first PyPI release is `0.1.1`; the existing
  `v0.1.0` GitHub Release is left untouched.
- Everything else (deps, extras, classifiers, urls, build-system) unchanged.

### `src/bbterm/__init__.py`

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bbterm-tui")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+source"
```

**Mandatory:** `importlib.metadata.version()` keys on the *distribution* name.
Leaving it as `version("bbterm")` would silently degrade `bbterm --version` to
`0.0.0+source` for installed users. After the rename, reinstall the dev env
(`pip install -e ".[dev]"`) so the local distribution registers as `bbterm-tui`.

The import package stays `src/bbterm/`; `[project.scripts]` still maps
`bbterm = "bbterm.tui.app:main"`. Users `pip install bbterm-tui`, then run
`bbterm` and `import bbterm`.

## Workflows

### New `.github/workflows/testpypi.yml` (manual rehearsal)

```yaml
name: TestPyPI

on:
  workflow_dispatch:

jobs:
  testpypi:
    runs-on: ubuntu-latest
    environment: testpypi
    permissions:
      id-token: write  # OIDC for Trusted Publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: python -m twine check dist/*
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
```

Triggered by the "Run workflow" button. No tag, no GitHub Release — pure
pipeline rehearsal. Re-runnable with throwaway versions while iterating.

### Modified `.github/workflows/release.yml` (real publish on `v*` tags)

Split the current single job into `build` (artifacts + GitHub Release) and a new
`pypi` publish job:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: write  # create the GitHub Release
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: python -m twine check dist/*
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/*

  pypi:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # OIDC for Trusted Publishing
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
```

The `pypi` job publishes the exact artifacts the `build` job validated; the
default action URL targets real PyPI.

## Trusted Publishing setup (maintainer, out-of-band)

Performed once in the browser before the first publish; not automatable here.

1. **GitHub → repo Settings → Environments:** create two environments named
   exactly `testpypi` and `pypi`. (Protection rules optional; a required
   reviewer on `pypi` adds a manual approval gate if desired.)
2. **TestPyPI** (`https://test.pypi.org`): register an account (separate from
   PyPI). Account settings → Publishing → add a **pending publisher**:
   - PyPI Project Name: `bbterm-tui`
   - Owner: `sgjlee0520`
   - Repository name: `bbterm`
   - Workflow name: `testpypi.yml`
   - Environment name: `testpypi`
3. **PyPI** (`https://pypi.org`, account already created): add a **pending
   publisher**:
   - PyPI Project Name: `bbterm-tui`
   - Owner: `sgjlee0520`
   - Repository name: `bbterm`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

The pending publishers create the projects on first successful upload.

## README updates

In the Install section, add a published-package path above the `git+…` path:

```bash
pipx install bbterm-tui     # or: pip install bbterm-tui
```

Note that the installed command and import name remain `bbterm`. Keep the
`git+https://…` pipx path for installing unreleased `main`.

## Testing & verification

1. **Unit suite:** after the rename + editable reinstall, all **94** tests pass.
2. **Workflow validity test** (`tests/test_workflows_valid.py`): extend to assert
   (a) `testpypi.yml` triggers on `workflow_dispatch`, and (b) `release.yml`
   defines a `pypi` job. Keep the existing CI/release-tag assertions.
3. **TestPyPI rehearsal (manual):** run `testpypi.yml`; then in a clean venv:
   ```bash
   pip install -i https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ bbterm-tui
   bbterm --version   # -> bbterm 0.1.1
   ```
   The `--extra-index-url` is required because TestPyPI does not host the real
   dependencies (textual, duckdb, …).
4. **Real release:** push tag `v0.1.1`; `release.yml` builds, creates the GitHub
   Release, and publishes to PyPI. Verify in a clean environment:
   `pipx install bbterm-tui` then `bbterm --version`.

## Error handling / risks

- **Wrong pending-publisher values** → OIDC publish step fails with a trust
  error. Fix the publisher config (workflow filename and environment name must
  match the YAML exactly) and re-run; nothing is uploaded on failure.
- **Version already used** → PyPI rejects a duplicate version. Bump and re-tag.
  TestPyPI rehearsals should use throwaway versions if a number gets consumed.
- **TestPyPI dependency resolution** → always pass `--extra-index-url` when
  installing from TestPyPI (see above).

## Alternatives considered

- **Single environment-gated `release.yml` (build → TestPyPI → approval → PyPI):**
  rejected; couples the rehearsal to the same real version/tag, preventing
  throwaway-version rehearsals, and adds environment-protection complexity.
- **Pre-release `vX.Y.Zrc*` tags for TestPyPI:** rejected; pollutes tag history
  and is the most ceremony for a solo project.
- **API-token auth:** rejected in favor of OIDC Trusted Publishing — no
  long-lived secret to store, guard, or rotate.
- **Renaming the import package to `bbterm_tui`:** rejected; breaks the existing
  `bbterm` command/import with no user benefit.
</content>
