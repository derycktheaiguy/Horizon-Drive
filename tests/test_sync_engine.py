"""Tests for the sync engine: handler, transfer queue, uploads/downloads, resilience."""

import threading
from unittest import mock

import pytest
from watchdog.events import DirCreatedEvent, FileCreatedEvent, FileModifiedEvent

import horizon_drive.engine.sync_engine as sync_engine_module
from horizon_drive.engine.sync_engine import FILES_FIELDS, SyncEngine, SyncHandler


class RecordingEngine:
    """Stands in for SyncEngine when testing the watchdog handler alone."""

    def __init__(self):
        self.uploaded = []

    def queue_upload(self, path):
        self.uploaded.append(path)


@pytest.fixture
def engine(tmp_path):
    auth_manager = mock.MagicMock()
    eng = SyncEngine(auth_manager, str(tmp_path / "sync"))
    yield eng
    if eng._downlink_thread and eng._downlink_thread.is_alive():
        eng.stop()


class TestSyncHandler:
    def test_created_and_modified_file_events_queue_upload(self):
        rec = RecordingEngine()
        handler = SyncHandler(rec)

        handler.on_created(FileCreatedEvent("/tmp/a.txt"))
        handler.on_modified(FileModifiedEvent("/tmp/b.txt"))

        assert rec.uploaded == ["/tmp/a.txt", "/tmp/b.txt"]

    def test_directory_events_ignored(self):
        rec = RecordingEngine()
        handler = SyncHandler(rec)
        handler.on_created(DirCreatedEvent("/tmp/folder"))
        handler.on_modified(DirCreatedEvent("/tmp/folder"))
        assert rec.uploaded == []


class TestEngineLifecycle:
    def test_creates_missing_sync_dir(self, tmp_path):
        target = tmp_path / "does_not_exist"
        SyncEngine(mock.MagicMock(), str(target))
        assert target.is_dir()

    def test_start_and_stop_spawn_downlink_thread(self, tmp_path):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        with mock.patch.object(engine, "_downlink_loop", lambda: None):
            engine.start()
            assert engine._downlink_thread is not None
            engine.stop()
            assert not engine._downlink_thread.is_alive()

    def test_expanduser_applied(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        engine = SyncEngine(mock.MagicMock(), "~/HorizonDrive")
        assert engine.sync_dir == str(tmp_path / "HorizonDrive")


class TestTransferQueue:
    def test_add_update_remove_cycle(self, tmp_path):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))

        engine._add_transfer("u1", "upload", "a.txt", 100)
        assert len(engine.active_transfers) == 1

        engine._update_transfer("u1", 50, 100)
        transfer = engine.active_transfers[0]
        assert transfer["bytes_transferred"] == 50
        assert transfer["progress"] == 0.5

        engine._remove_transfer("u1")
        assert engine.active_transfers == []

    def test_update_missing_transfer_is_noop(self, tmp_path):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        engine._update_transfer("ghost", 10, 100)
        assert engine.active_transfers == []

    def test_zero_total_bytes_progress_is_zero(self, tmp_path):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        engine._add_transfer("d1", "download", "b.bin", 0)
        engine._update_transfer("d1", 0, 0)
        assert engine.active_transfers[0]["progress"] == 0.0

    def test_concurrent_access_is_thread_safe(self, tmp_path):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        errors = []

        def worker(i):
            try:
                for n in range(50):
                    tid = f"t{i}-{n}"
                    engine._add_transfer(tid, "upload", tid, 10)
                    engine._update_transfer(tid, 5, 10)
                    assert engine.active_transfers
                    engine._remove_transfer(tid)
            except Exception as exc:  # pragma: no cover - surfaced via join
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert engine.active_transfers == []


class TestUploadDownload:
    def _fake_service(self, upload_id="drive-123"):
        request = mock.MagicMock()
        request.next_chunk.return_value = (None, {"id": upload_id})

        files = mock.MagicMock()
        files.create.return_value = request

        get_media_request = mock.MagicMock()
        files.get_media.return_value = get_media_request

        service = mock.MagicMock()
        service.files.return_value = files
        return service, files, request

    def test_upload_success_reports_status(self, engine, tmp_path):
        local = tmp_path / "report.txt"
        local.write_text("hello drive")

        service, _, request = self._fake_service()
        engine.auth_manager.get_service.return_value = service

        statuses = []
        engine.status_callback = lambda title, sub: statuses.append(title)

        engine.upload_file(str(local))

        assert request.next_chunk.call_count >= 1
        assert "Syncing..." in statuses
        assert statuses[-1] == "Up to date"
        assert engine.active_transfers == []

    def test_upload_failure_clears_transfer(self, engine, tmp_path):
        local = tmp_path / "broken.txt"
        local.write_text("data")

        service = mock.MagicMock()
        service.files.side_effect = RuntimeError("quota exceeded")
        engine.auth_manager.get_service.return_value = service

        statuses = []
        engine.status_callback = lambda title, sub: statuses.append(title)

        engine.upload_file(str(local))

        assert "Sync Error" in statuses
        assert engine.active_transfers == []

    def test_download_writes_file_locally(self, engine, tmp_path, monkeypatch):
        payload = b"cloud bytes"

        class FakeDownloader:
            def __init__(self, handle, request):
                self.handle = handle

            def next_chunk(self):
                self.handle.write(payload)
                return None, True

        monkeypatch.setattr(sync_engine_module, "MediaIoBaseDownload", FakeDownloader)

        service, files, _ = self._fake_service()
        engine.auth_manager.get_service.return_value = service

        assert engine.download_file("abc", "photo.png") is True
        assert (tmp_path / "sync" / "photo.png").read_bytes() == payload
        assert engine.active_transfers == []

    def test_download_failure_returns_false_and_cleans_up(self, engine, tmp_path):
        service = mock.MagicMock()
        service.files.side_effect = RuntimeError("network gone")
        engine.auth_manager.get_service.return_value = service

        assert engine.download_file("xyz", "missing.bin") is False
        assert engine.active_transfers == []
        assert not (tmp_path / "missing.bin").exists()


class TestListResilience:
    """All list_* methods must degrade to [] instead of raising."""

    def _engine_with_failing_service(self, engine):
        service = mock.MagicMock()
        service.files.side_effect = RuntimeError("offline")
        engine.auth_manager.get_service.return_value = service

    @pytest.mark.parametrize(
        "method",
        ["list_files", "list_recent_files", "list_starred", "list_trashed", "list_shared_with_me"],
    )
    def test_list_methods_return_empty_on_error(self, tmp_path, method):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        self._engine_with_failing_service(engine)
        assert getattr(engine, method)() == []

    def test_files_fields_projection(self):
        assert "id,name,mimeType,size,modifiedTime" in FILES_FIELDS


class TestDownlink:
    def test_downlink_downloads_missing_remote_file(self, tmp_path):
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        remote = [{"name": "new-cloud.txt", "mimeType": "text/plain", "id": "r1"}]

        with (
            mock.patch.object(engine, "list_files", return_value=remote),
            mock.patch.object(engine, "download_file", return_value=True) as download,
            mock.patch("time.sleep") as sleep,
        ):
            stop_after_first_pass = threading.Timer(0.2, engine._stop_event.set)
            stop_after_first_pass.start()
            engine._downlink_loop()

        assert download.called
        download.assert_called_with("r1", "new-cloud.txt")
        sleep.assert_called()  # loop slept in short increments, not one long block

    def test_downlink_skips_folders_and_known_files(self, tmp_path):
        (tmp_path / "known.txt").write_text("already here")
        engine = SyncEngine(mock.MagicMock(), str(tmp_path))
        remote = [
            {"name": "known.txt", "mimeType": "text/plain", "id": "k1"},
            {"name": "Some Folder", "mimeType": "application/vnd.google-apps.folder", "id": "f1"},
        ]

        with (
            mock.patch.object(engine, "list_files", return_value=remote),
            mock.patch.object(engine, "download_file") as download,
            mock.patch("time.sleep"),
        ):
            engine._stop_event.set()
            engine._downlink_loop()

        download.assert_not_called()
