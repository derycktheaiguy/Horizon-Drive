"""Tests for horizon_drive.config — XDG-based persistence with legacy fallback."""

import json

from horizon_drive.config import get_config_path, load_config, save_config

SAMPLE = {"local_folder": "/home/u/HorizonDrive", "sync_mode": "Two-way"}


def test_save_writes_to_xdg_location(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    path = save_config(SAMPLE)

    assert path == str(tmp_path / "horizon-drive" / "config.json")
    assert json.loads((tmp_path / "horizon-drive" / "config.json").read_text()) == SAMPLE


def test_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_config(SAMPLE)

    assert load_config() == SAMPLE


def test_load_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # no legacy file either

    assert load_config() is None


def test_load_falls_back_to_legacy_cwd_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nonexistent"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps(SAMPLE))

    loaded = load_config()

    assert loaded == SAMPLE


def test_new_location_takes_priority_over_legacy(tmp_path, monkeypatch):
    xdg_dir = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_dir))
    save_config(SAMPLE)

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"local_folder": "/legacy"}))

    assert load_config()["local_folder"] == "/home/u/HorizonDrive"


def test_corrupt_canonical_file_falls_back_then_none(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "horizon-drive").mkdir()
    (tmp_path / "horizon-drive" / "config.json").write_text("{broken")
    monkeypatch.chdir(tmp_path)  # no legacy file

    assert load_config() is None


def test_non_dict_json_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "horizon-drive").mkdir()
    (tmp_path / "horizon-drive" / "config.json").write_text('["a", "list"]')
    monkeypatch.chdir(tmp_path)  # isolate from any real legacy config

    assert load_config() is None


def test_default_dir_uses_home_when_no_xdg_var(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert get_config_path() == str(tmp_path / ".config" / "horizon-drive" / "config.json")


def test_main_module_still_exposes_load_config():
    # entry point imports load_config from main; guard against regressions
    from horizon_drive.main import load_config  # noqa: F401
