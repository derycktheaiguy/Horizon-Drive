"""Tests for pure GUI helper functions (no display required thanks to conftest stubs)."""

import pytest

from horizon_drive.gui.main_window import MainWindow


@pytest.fixture
def window():
    """A MainWindow instance without running __init__ (no display, no engine)."""
    return object.__new__(MainWindow)


def test_format_bytes_human_zero():
    assert MainWindow._format_bytes_human(0) == "0 B"


def test_format_bytes_human_scales():
    assert MainWindow._format_bytes_human(512) == "512.0 B"
    assert MainWindow._format_bytes_human(1536) == "1.5 KB"
    assert MainWindow._format_bytes_human(5 * 1024**2) == "5.0 MB"
    assert MainWindow._format_bytes_human(int(2.5 * 1024**3)) == "2.5 GB"


def test_format_bytes_human_caps_at_tb():
    huge = 10 * 1024**5  # 10 PB -> stays in TB units
    assert MainWindow._format_bytes_human(huge).endswith("TB")


def test_truncate_string_short(window):
    assert window._truncate_string("hello.txt", 15) == "hello.txt"


def test_truncate_string_long(window):
    out = window._truncate_string("a-very-long-filename-in-drive.txt", 15)
    assert len(out) == 15
    assert out.endswith("...")


def test_format_size_accepts_numeric_strings(window):
    assert window._format_size("1024") == "1.0 KB"


def test_get_mime_icon_mapping(window):
    cases = {
        "application/pdf": "\U0001f4c4",
        "image/png": "\U0001f5bc\ufe0f",
        "video/mp4": "\U0001f3ac",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "\U0001f4ca",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "\U0001f4dd",
        "msword": "\U0001f4dd",
        "application/zip": "\U0001f4c4",
        # Known gap: native Google Docs mimes fall through to generic icon
        "application/vnd.google-apps.document": "\U0001f4c4",
    }
    for mime, icon in cases.items():
        assert window._get_mime_icon(mime) == icon, mime


def test_mime_icon_treats_folder_separately(window):
    # Folders are handled by callers, but the icon fn should not crash on them.
    assert window._get_mime_icon("application/vnd.google-apps.folder")
