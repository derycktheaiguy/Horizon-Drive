"""Tests for the entry-point helpers in horizon_drive.main."""

import json

from horizon_drive.main import load_config


def test_load_config_reads_valid_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({"local_folder": "/home/u/Drive", "sync_mode": "Two-way"}))

    config = load_config()

    assert config == {"local_folder": "/home/u/Drive", "sync_mode": "Two-way"}


def test_load_config_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_config() is None


def test_load_config_corrupt_json_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.json").write_text("{not valid json")

    assert load_config() is None
