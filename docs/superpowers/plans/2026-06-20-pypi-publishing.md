# Packaging Phase 2 (PyPI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish bbterm to PyPI as the distribution `bbterm-tui` via GitHub Actions Trusted Publishing (OIDC), rehearsed on TestPyPI first.

**Architecture:** Rename only the *distribution* (`bbterm`→`bbterm-tui`); the import package and `bbterm` command are unchanged. A manual `testpypi.yml` rehearses the OIDC upload pipeline; `release.yml` gains a `pypi` publish job that runs on `v*` tags. No secrets are stored — PyPI/TestPyPI trust the repo+workflow+environment via pending publishers the maintainer configured.

**Tech Stack:** setuptools build, `pypa/gh-action-pypi-publish`, GitHub Actions OIDC, pytest, PyYAML.

## Global Constraints

- Distribution name: **`bbterm-tui`**. Import package and CLI command stay **`bbterm`**.
- Version: bump to **`0.1.1`** (first PyPI release; the GitHub-only `v0.1.0` stays as-is).
- Auth: **Trusted Publishing / OIDC** — no API tokens or secrets in GitHub.
- **TestPyPI rehearsal before the real PyPI publish.**
- GitHub Environments **`testpypi`** and **`pypi`** already exist; pending publishers already configured (TestPyPI→`testpypi.yml`/`testpypi`, PyPI→`release.yml`/`pypi`).
- `importlib.metadata.version()` keys on the **distribution** name — the version lookup must use `"bbterm-tui"`.
- No change to app behavior.
- Work on the existing **`packaging-phase2`** branch.
- `workflow_dispatch` workflows are only triggerable from the **default branch**, so the branch must be merged to `main` before the TestPyPI rehearsal can run.

---

### Task 1: Rename distribution to `bbterm-tui`, bump to 0.1.1, fix version lookup

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/bbterm/__init__.py`
- Test: `tests/test_version.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: installed distribution named `bbterm-tui` at version `0.1.1`; `bbterm.__version__ == importlib.metadata.version("bbterm-tui")`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_version.py`:

```python
def test_version_matches_installed_distribution():
    from importlib.metadata import version

    import bbterm

    # Guards the spec's stated risk: renaming the distribution without updating
    # the importlib.metadata lookup (which keys on the *distribution* name).
    assert bbterm.__version__ == version("bbterm-tui")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_version.py::test_version_matches_installed_distribution -v`
Expected: FAIL — `importlib.metadata.PackageNotFoundError: bbterm-tui` (the installed distribution is still named `bbterm`).

- [ ] **Step 3: Rename the distribution and bump the version**

In `pyproject.toml`, change the two lines:

```toml
name = "bbterm-tui"
version = "0.1.1"
```

(Leave every other field unchanged.)

- [ ] **Step 4: Point the version lookup at the new distribution name**

Replace the contents of `src/bbterm/__init__.py`:

```python
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("bbterm-tui")
except PackageNotFoundError:  # running from a source tree, not installed
    __version__ = "0.0.0+source"
```

- [ ] **Step 5: Reinstall cleanly under the new name**

Run:
```bash
.venv/bin/pip uninstall -y bbterm bbterm-tui
.venv/bin/pip install -e ".[dev,databento]"
```
Expected: uninstalls the old `bbterm` distribution and installs `bbterm-tui 0.1.1` (editable). The uninstall of both names guarantees no stale `bbterm` distribution metadata lingers to mask the rename.

- [ ] **Step 6: Run the test and confirm version**

Run: `.venv/bin/python -m pytest tests/test_version.py -v && .venv/bin/bbterm --version`
Expected: all version tests PASS; `bbterm --version` prints `bbterm 0.1.1`.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 95 tests (94 + the new guard).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/bbterm/__init__.py tests/test_version.py
git commit -m "build: rename distribution to bbterm-tui, bump to 0.1.1

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: TestPyPI rehearsal workflow

**Files:**
- Create: `.github/workflows/testpypi.yml`
- Test: `tests/test_workflows_valid.py`

**Interfaces:**
- Consumes: GitHub Environment `testpypi` and its TestPyPI pending publisher (maintainer-configured).
- Produces: a manually-triggerable workflow that publishes to TestPyPI.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflows_valid.py`:

```python
def test_testpypi_workflow_is_manual():
    wf = _load("testpypi.yml")
    triggers = wf.get(True, wf.get("on"))
    assert "workflow_dispatch" in triggers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_workflows_valid.py::test_testpypi_workflow_is_manual -v`
Expected: FAIL — `testpypi.yml` does not exist (`FileNotFoundError`).

- [ ] **Step 3: Create the workflow**

Create `.github/workflows/testpypi.yml`:

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
          skip-existing: true  # rehearsals are re-runnable; don't error if the version exists
```

- [ ] **Step 4: Run the test**

Run: `.venv/bin/python -m pytest tests/test_workflows_valid.py::test_testpypi_workflow_is_manual -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/testpypi.yml tests/test_workflows_valid.py
git commit -m "ci: manual TestPyPI rehearsal workflow (OIDC)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Add the real-PyPI publish job to `release.yml`

**Files:**
- Modify: `.github/workflows/release.yml`
- Test: `tests/test_workflows_valid.py`

**Interfaces:**
- Consumes: GitHub Environment `pypi` and its PyPI pending publisher (maintainer-configured).
- Produces: on a `v*` tag, builds + attaches to the GitHub Release **and** publishes to PyPI.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflows_valid.py`:

```python
def test_release_workflow_has_pypi_publish_job():
    wf = _load("release.yml")
    assert "pypi" in wf["jobs"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_workflows_valid.py::test_release_workflow_has_pypi_publish_job -v`
Expected: FAIL — `release.yml` currently has only a `build` job (`KeyError`/assert).

- [ ] **Step 3: Replace `release.yml`**

Overwrite `.github/workflows/release.yml`:

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

- [ ] **Step 4: Run the new test and the existing release-trigger test**

Run: `.venv/bin/python -m pytest tests/test_workflows_valid.py -v`
Expected: PASS — all four workflow tests (CI push/PR, release tag trigger, TestPyPI manual, release has `pypi` job).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — 97 tests (95 + the two workflow guards from Tasks 2–3).

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/release.yml tests/test_workflows_valid.py
git commit -m "ci: publish to PyPI on version tags via OIDC

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: README — PyPI install path

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: documentation only.

- [ ] **Step 1: Read the current Install section**

Run: `grep -n "## Install" README.md` and read the block that follows (it currently starts with "End users (isolated install via [pipx]...").

- [ ] **Step 2: Insert a PyPI install block at the top of the end-user instructions**

Immediately under `## Install`, before the existing "End users (isolated install via pipx)" line, add:

```markdown
From PyPI (recommended):

```bash
pipx install bbterm-tui     # or: pip install bbterm-tui
```

The installed command and import name are `bbterm` (only the PyPI package is
named `bbterm-tui`). To install the latest unreleased `main` instead:
```

The existing `pipx install git+https://github.com/sgjlee0520/bbterm.git` block
remains directly below as the "unreleased main" option.

- [ ] **Step 3: Verify the edit**

Run: `grep -c "pipx install bbterm-tui" README.md`
Expected: `≥ 1`.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document pip/pipx install of bbterm-tui from PyPI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Push branch, open PR, confirm CI green

**Files:** none (release operations).

- [ ] **Step 1: Push the branch**

Run: `git push -u origin packaging-phase2`
Expected: branch pushed; CI (`ci.yml`) starts on the push and PR.

- [ ] **Step 2: Open the PR**

Run:
```bash
gh pr create --base main --head packaging-phase2 \
  --title "Packaging Phase 2: publish to PyPI as bbterm-tui (OIDC, TestPyPI rehearsal)" \
  --body "Implements docs/superpowers/specs/2026-06-20-pypi-publishing-design.md. Renames the distribution to bbterm-tui (import/command stay bbterm), bumps to 0.1.1, adds a manual TestPyPI rehearsal workflow and a real-PyPI publish job via Trusted Publishing. 97 tests passing."
```
Expected: prints the PR URL.

- [ ] **Step 3: Watch CI to green**

Run: `gh run watch "$(gh run list --branch packaging-phase2 --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status`
Expected: `test (3.11)` and `test (3.12)` both succeed (97 tests; the databento-optional tests skip on the core CI install).

---

### Task 6: Merge to `main` (enables the rehearsal; publishes nothing)

**Files:** none.

Merging is required before Task 7 because `workflow_dispatch` is only triggerable from the default branch. Merging does **not** publish: `release.yml` fires only on `v*` tags, and `testpypi.yml` only on manual dispatch.

- [ ] **Step 1: Merge the PR**

Run: `gh pr merge packaging-phase2 --merge --delete-branch`
Expected: PR merged to `main`; branch deleted.

- [ ] **Step 2: Sync local main**

Run: `git checkout main && git pull --ff-only && git log --oneline -1`
Expected: local `main` includes the merge commit; `testpypi.yml` and the updated `release.yml` are now on the default branch.

---

### Task 7: TestPyPI rehearsal (validate the OIDC pipeline)

**Files:** none (release operations).

- [ ] **Step 1: Trigger the rehearsal workflow**

Run: `gh workflow run testpypi.yml --ref main`
Expected: `✓ Created workflow_dispatch event for testpypi.yml at main`.

- [ ] **Step 2: Watch it succeed**

Run:
```bash
sleep 6
gh run watch "$(gh run list --workflow testpypi.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```
Expected: conclusion `success`. The `pypa/gh-action-pypi-publish` step uploads `bbterm-tui 0.1.1` to TestPyPI. (If it fails with a trust error, a pending-publisher field is wrong — fix `testpypi.yml`/`testpypi` env values on TestPyPI and re-run; `skip-existing` makes re-runs safe.)

- [ ] **Step 3: Install from TestPyPI in a clean venv**

Run:
```bash
rm -rf /tmp/bbterm-testpypi
/Users/slee/bloomberg/.venv/bin/python -m venv /tmp/bbterm-testpypi
/tmp/bbterm-testpypi/bin/pip install -i https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ bbterm-tui
/tmp/bbterm-testpypi/bin/bbterm --version
```
Expected: installs `bbterm-tui` (deps resolved from real PyPI via `--extra-index-url`); prints `bbterm 0.1.1`. (If install 404s, wait ~30s for TestPyPI to index the new release and retry.)

- [ ] **Step 4: Clean up**

Run: `rm -rf /tmp/bbterm-testpypi`

---

### Task 8: Real PyPI release (irreversible)

**Files:** none (release operations).

Only proceed once Task 7 succeeded. Publishing to PyPI is permanent.

- [ ] **Step 1: Tag and push `v0.1.1`**

Run:
```bash
git checkout main && git pull --ff-only
git tag -a v0.1.1 -m "bbterm 0.1.1 — first PyPI release (bbterm-tui)"
git push origin v0.1.1
```
Expected: tag pushed; `release.yml` starts.

- [ ] **Step 2: Watch the release workflow (build + pypi jobs)**

Run:
```bash
sleep 6
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```
Expected: conclusion `success`; both `build` and `pypi` jobs green. `bbterm-tui 0.1.1` is now on PyPI and attached to the GitHub Release.

- [ ] **Step 3: Verify the published release and assets**

Run: `gh release view v0.1.1 --json tagName,isDraft,assets --jq '{tag: .tagName, draft: .isDraft, assets: [.assets[].name]}'`
Expected: `draft: false`, assets include `bbterm_tui-0.1.1-py3-none-any.whl` and `bbterm_tui-0.1.1.tar.gz`.

- [ ] **Step 4: Install from real PyPI via pipx**

The Phase 1 pipx install is the `bbterm` package (from git); uninstall it first to avoid an entry-point name clash, then install the PyPI distribution.

Run:
```bash
pipx uninstall bbterm 2>/dev/null || true
pipx install bbterm-tui
~/.local/bin/bbterm --version
```
Expected: `pipx` installs `bbterm-tui`, exposes the `bbterm`/`bbterm-sync` apps, and `bbterm --version` prints `bbterm 0.1.1`. (If PyPI hasn't indexed yet, wait ~30s and retry.)

---

## Notes for the implementer

- The branch is already `packaging-phase2`; do not create another.
- The maintainer has already created the `testpypi`/`pypi` GitHub Environments and both pending publishers. If an OIDC publish fails with a trust error, the fix is in those PyPI/TestPyPI settings (workflow filename + environment name must match the YAML), not in this repo.
- `dist/` and `build/` are gitignored (Phase 1); never commit build output.
- Task 8 is irreversible — do not run it until the Task 7 rehearsal has passed.
- The branch is merged to `main` in Task 6 (a prerequisite for the rehearsal),
  so there is **no separate finishing-a-development-branch step** at the end —
  branch integration is already complete by Task 6.
</content>
