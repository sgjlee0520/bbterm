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


def test_version_matches_installed_distribution():
    from importlib.metadata import version

    # Guards the spec's stated risk: renaming the distribution without updating
    # the importlib.metadata lookup (which keys on the *distribution* name).
    assert bbterm.__version__ == version("bbterm-tui")
