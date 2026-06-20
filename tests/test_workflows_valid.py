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
