"""Real CustomTkinter integration checks, enabled under Xvfb in Linux CI."""

import os
import time
from unittest import mock

import pytest

from horizon_drive.gui.main_window import MainWindow
from horizon_drive.gui.setup_wizard import SetupWizard
from horizon_drive.gui.welcome_wizard import WelcomeWizard

pytestmark = pytest.mark.skipif(os.environ.get("HORIZON_GUI_TESTS") != "1", reason="Requires a real Tk display")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    auth = mock.MagicMock()
    auth.get_quota.return_value = {"limit": "100", "usage": "25", "usageInDrive": "20"}
    auth.get_service.return_value.files.return_value.list.return_value.execute.return_value = {"files": []}
    with mock.patch("horizon_drive.gui.main_window.SyncEngine.start"):
        window = MainWindow(auth, str(tmp_path / "sync"), sync_mode="Backup")
    window.withdraw()
    yield window
    window.force_quit()


def pump(app):
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        app.update()
        app._drain_ui()
        time.sleep(0.01)


def test_real_window_quota_navigation_and_status(app):
    assert app.engine.sync_mode == "Backup"
    for name in ("Home", "My Drive", "Shared", "Starred", "Trash", "Storage", "Activity"):
        app._switch_view(name)
        pump(app)
        assert app.current_view == name
    app.update_sync_status("Sync Error", "Connection unavailable")
    pump(app)
    assert app.sync_title.cget("text") == "Sync Error"
    assert "25.0 B" in app.sidebar_quota_label.cget("text")


def test_search_and_view_modes_render_real_widgets(app):
    app._cached_title = "My Drive"
    app._cached_files = [{"id": "one", "name": "Report.txt", "mimeType": "text/plain", "size": "10"}]
    app.search_entry.insert(0, "report")
    app._apply_search()
    app._set_view_mode("Grid")
    app.search_entry.delete(0, "end")
    app.search_entry.insert(0, "missing")
    app._apply_search()
    assert any(
        getattr(child, "cget", lambda _: "")("text") == "No files found."
        for child in app.content_frame.winfo_children()
    )


def test_old_fetch_cannot_replace_new_view(app):
    import threading

    gate = threading.Event()
    finished = threading.Event()

    def slow():
        gate.wait(2)
        finished.set()
        return [{"name": "old", "mimeType": "text/plain"}]

    app.engine.list_files = slow
    app._switch_view("My Drive")
    app._switch_view("Activity")
    gate.set()
    assert finished.wait(2)
    pump(app)
    assert app.current_view == "Activity" and not app._cached_title


def test_transfer_panel_has_one_refresh_timer(app):
    app._toggle_transfer_queue()
    timer = app._transfer_after
    app._toggle_transfer_queue()
    assert app._transfer_after is None
    assert timer not in app.tk.call("after", "info")
    app._toggle_transfer_queue()
    assert app._transfer_after != timer


def test_pause_resume_and_start_failure_are_visible(app):
    with mock.patch.object(app.engine, "start"), mock.patch.object(app.engine, "stop"):
        app.toggle_sync()
        assert app.sync_paused
        assert app.pause_button.cget("text") == "Resume Sync"
        app.toggle_sync()
        assert not app.sync_paused
    app.sync_paused = True
    with mock.patch.object(app.engine, "start", side_effect=RuntimeError("Still stopping")):
        app.toggle_sync()
    assert app.sync_paused and app.sync_subtitle.cget("text") == "Still stopping"


def test_wizard_rejects_empty_folder_and_saves_mode(app, tmp_path):
    completed = []
    wizard = SetupWizard(app, completed.append)
    wizard.folder_entry.delete(0, "end")
    wizard._finish()
    assert not completed and "Could not save" in wizard.status_label.cget("text")
    wizard.folder_entry.insert(0, str(tmp_path / "selected"))
    wizard.mode_var.set("Backup")
    wizard._finish()
    assert completed[0]["sync_mode"] == "Backup"


def test_auth_wizard_remains_responsive_and_reports_failure(app):
    auth = mock.MagicMock()
    auth.authenticate.side_effect = RuntimeError("bad credentials")
    wizard = WelcomeWizard(app, auth, lambda: None)
    wizard.client_id_entry.insert(0, "client")
    wizard.client_secret_entry.insert(0, "secret")
    wizard._start_auth()
    pump(app)
    assert wizard.auth_button.cget("state") == "normal"
    assert "Could not connect" in wizard.status_label.cget("text")
    wizard.destroy()
