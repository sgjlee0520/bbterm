from pathlib import Path


def test_license_is_agpl_v3():
    text = (Path(__file__).resolve().parents[1] / "LICENSE").read_text()
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in text
    assert "Version 3" in text
