"""End-to-end reconciliation against a deterministic in-memory Drive service."""

import hashlib
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from horizon_drive.engine.sync_engine import FOLDER, SyncEngine


def md5(payload):
    return hashlib.md5(payload).hexdigest()


class Request:
    def __init__(self, action):
        self.action = action

    def execute(self, **kwargs):
        return self.action()

    def next_chunk(self, **kwargs):
        return None, self.action()


class Drive:
    def __init__(self):
        self.items = {}
        self.payloads = {}
        self.creates = 0
        self.updates = 0
        self.downloads = 0
        self.list_pages = []
        self.fail_listing = False

    def files(self):
        return self

    def add(self, name, payload=b"cloud", parent="root", mime="text/plain"):
        file_id = str(len(self.items) + 1)
        self.items[file_id] = {"id": file_id, "name": name, "mimeType": mime, "parents": [parent]}
        self.change(file_id, payload)
        return file_id

    def change(self, file_id, payload):
        self.payloads[file_id] = payload
        self.items[file_id].update(md5Checksum=md5(payload), size=str(len(payload)), modifiedTime=md5(payload))

    def list(self, **options):
        def execute():
            if self.fail_listing:
                raise OSError("offline")
            parent = options["q"].split("'")[1]
            all_items = [dict(item) for item in self.items.values() if parent in item["parents"]]
            # Small pages ensure every reconciliation exercises pagination.
            offset = int(options.get("pageToken", 0))
            self.list_pages.append(offset)
            result = {"files": all_items[offset : offset + 2]}
            if offset + 2 < len(all_items):
                result["nextPageToken"] = str(offset + 2)
            return result

        return Request(execute)

    def create(self, body, fields, media_body=None):
        def execute():
            self.creates += 1
            if media_body:
                media_body.stream().seek(0)
            payload = media_body.stream().read() if media_body else b""
            file_id = self.add(body["name"], payload, body["parents"][0], body.get("mimeType", "text/plain"))
            return dict(self.items[file_id])

        return Request(execute)

    def update(self, fileId, media_body, fields):
        def execute():
            self.updates += 1
            media_body.stream().seek(0)
            self.change(fileId, media_body.stream().read())
            return dict(self.items[fileId])

        return Request(execute)

    def get_media(self, fileId):
        self.downloads += 1
        return self.payloads[fileId]


class Downloader:
    def __init__(self, stream, payload, **kwargs):
        self.stream, self.payload = stream, payload

    def next_chunk(self, **kwargs):
        self.stream.write(self.payload)
        return SimpleNamespace(total_size=len(self.payload), resumable_progress=len(self.payload)), True


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr("horizon_drive.engine.sync_engine.MediaIoBaseDownload", Downloader)
    drive = Drive()
    auth = SimpleNamespace(get_service=lambda: drive, sync_identity="test-account")
    engine = SyncEngine(auth, str(tmp_path / "sync"))
    return engine, drive, Path(engine.sync_dir)


def test_initial_files_upload_once_and_edits_update_same_id(setup):
    engine, drive, root = setup
    (root / "report.txt").write_bytes(b"first")
    engine.sync_once()
    assert drive.creates == 1
    engine.sync_once()
    assert drive.creates == 1
    (root / "report.txt").write_bytes(b"second")
    engine.sync_once()
    assert drive.creates == 1 and drive.updates == 1
    assert drive.payloads["1"] == b"second"


def test_remote_download_and_edit_do_not_echo_upload(setup):
    engine, drive, root = setup
    file_id = drive.add("cloud.txt")
    engine.sync_once()
    assert (root / "cloud.txt").read_bytes() == b"cloud"
    engine.sync_once()
    assert drive.creates == drive.updates == 0
    drive.change(file_id, b"changed remotely")
    engine.sync_once()
    assert (root / "cloud.txt").read_bytes() == b"changed remotely"
    assert drive.downloads == 2


def test_history_survives_restart_without_duplicates(setup):
    engine, drive, root = setup
    (root / "local.txt").write_bytes(b"hello")
    engine.sync_once()
    restarted = SyncEngine(engine.auth_manager, str(root))
    restarted.sync_once()
    assert drive.creates == 1 and drive.updates == 0
    (root / "local.txt").write_bytes(b"offline edit")
    restarted.sync_once()
    assert drive.updates == 1


def test_conflicting_edits_preserve_both_contents(setup):
    engine, drive, root = setup
    file_id = drive.add("report.txt", b"original")
    engine.sync_once()
    (root / "report.txt").write_bytes(b"my edit")
    drive.change(file_id, b"their edit")
    engine.sync_once()
    assert (root / "report.txt").read_bytes() == b"their edit"
    copies = list(root.glob("report (local conflict *).txt"))
    assert len(copies) == 1 and copies[0].read_bytes() == b"my edit"
    engine.sync_once()
    assert b"my edit" in drive.payloads.values()


def test_first_run_name_collision_is_not_overwritten(setup):
    engine, drive, root = setup
    drive.add("same.txt", b"remote")
    (root / "same.txt").write_bytes(b"local")
    engine.sync_once()
    assert set(path.read_bytes() for path in root.iterdir()) == {b"remote", b"local"}


def test_backup_does_not_download_or_overwrite_conflicts(setup):
    engine, drive, root = setup
    engine.sync_mode = "Backup"
    drive.add("cloud.txt")
    drive.add("same.txt", b"remote")
    (root / "same.txt").write_bytes(b"local")
    (root / "new.txt").write_bytes(b"new")
    engine.sync_once()
    assert drive.downloads == 0 and drive.updates == 0 and drive.creates == 1
    assert not (root / "cloud.txt").exists()
    assert (root / "same.txt").read_bytes() == b"local"
    assert engine.last_error


def test_backup_updates_previously_backed_up_file(setup):
    engine, drive, root = setup
    engine.sync_mode = "Backup"
    (root / "backup.txt").write_bytes(b"before")
    engine.sync_once()
    (root / "backup.txt").write_bytes(b"after")
    engine.sync_once()
    assert drive.updates == 1 and drive.downloads == 0


def test_nested_folders_and_empty_directories_sync_both_directions(setup):
    engine, drive, root = setup
    cloud_folder = drive.add("remote folder", mime=FOLDER)
    drive.add("photo.txt", b"picture", parent=cloud_folder)
    (root / "local folder" / "empty").mkdir(parents=True)
    (root / "local folder" / "nested.txt").write_bytes(b"nested")
    engine.sync_once()
    assert (root / "remote folder" / "photo.txt").read_bytes() == b"picture"
    nested = next(item for item in drive.items.values() if item["name"] == "nested.txt")
    parent = drive.items[nested["parents"][0]]
    assert parent["name"] == "local folder"
    assert any(item["name"] == "empty" and item["mimeType"] == FOLDER for item in drive.items.values())
    engine.sync_once()
    assert drive.updates == 0


def test_all_pages_are_downloaded(setup):
    engine, drive, root = setup
    for number in range(7):
        drive.add(f"{number}.txt")
    engine.sync_once()
    assert len(list(root.iterdir())) == 7
    assert drive.list_pages == [0, 2, 4, 6]


def test_google_documents_are_not_sent_to_binary_download(setup):
    engine, drive, root = setup
    drive.add("Document", mime="application/vnd.google-apps.document")
    engine.sync_once()
    assert drive.downloads == 0 and not list(root.iterdir())


def test_duplicate_remote_names_stop_before_any_changes(setup):
    engine, drive, root = setup
    drive.add("same.txt", b"one")
    drive.add("same.txt", b"two")
    with pytest.raises(ValueError, match="Multiple Drive"):
        engine.sync_once()
    assert not list(root.iterdir()) and drive.creates == 0


@pytest.mark.parametrize("name", ["../escape", "/absolute", "dir\\file", "..", ".", "", ".horizon-private"])
def test_unsafe_remote_paths_cannot_write_outside_sync(setup, name):
    engine, drive, root = setup
    assert engine.download_file("id", name) is False
    assert drive.downloads == 0


def test_partial_download_keeps_existing_file_and_error_status(setup, monkeypatch):
    engine, drive, root = setup
    file_id = drive.add("safe.txt")
    (root / "safe.txt").write_bytes(b"keep me")

    def fail(self, **kwargs):
        self.stream.write(b"partial")
        raise OSError("network dropped")

    monkeypatch.setattr(Downloader, "next_chunk", fail)
    statuses = []
    engine.status_callback = lambda title, detail: statuses.append(title)
    assert not engine.download_file(file_id, "safe.txt")
    assert (root / "safe.txt").read_bytes() == b"keep me"
    assert not list(root.glob(".horizon-*"))
    assert statuses[-1] == "Sync Error"
    assert not engine.active_transfers


def test_edit_during_download_is_preserved(setup, monkeypatch):
    engine, drive, root = setup
    file_id = drive.add("live.txt")
    (root / "live.txt").write_bytes(b"original")
    original = Downloader.next_chunk

    def editing(self, **kwargs):
        (root / "live.txt").write_bytes(b"new local edit")
        return original(self, **kwargs)

    monkeypatch.setattr(Downloader, "next_chunk", editing)
    assert not engine.download_file(file_id, "live.txt")
    assert (root / "live.txt").read_bytes() == b"new local edit"


def test_mismatched_remote_checksum_preserves_local(setup):
    engine, drive, root = setup
    file_id = drive.add("check.txt")
    (root / "check.txt").write_bytes(b"safe")
    assert not engine.download_file(file_id, "check.txt", {"id": file_id, "md5Checksum": "mismatch"})
    assert (root / "check.txt").read_bytes() == b"safe"


def test_listing_failure_never_uploads_from_incomplete_snapshot(setup):
    engine, drive, root = setup
    (root / "local.txt").write_bytes(b"local")
    drive.fail_listing = True
    with pytest.raises(OSError):
        engine.sync_once()
    assert drive.creates == drive.updates == drive.downloads == 0


def test_remote_deletion_is_not_silently_recreated(setup):
    engine, drive, root = setup
    file_id = drive.add("removed.txt")
    engine.sync_once()
    del drive.items[file_id]
    engine.sync_once()
    assert (root / "removed.txt").read_bytes() == b"cloud"
    assert drive.creates == 0


def test_upload_event_storm_uses_one_worker(setup):
    engine, drive, root = setup
    with mock.patch("horizon_drive.engine.sync_engine.threading.Thread") as thread:
        for _ in range(1000):
            engine.queue_upload(str(root / "report.txt"))
    thread.assert_not_called()
    assert engine._wake_event.is_set()


def test_stop_before_start_and_repeated_stop_are_safe(setup):
    engine, _, _ = setup
    engine.stop()
    engine.stop()


def test_transfer_snapshot_cannot_mutate_engine(setup):
    engine, _, _ = setup
    engine._add_transfer("one", "upload", "file", 10)
    engine.active_transfers[0]["progress"] = 999
    assert engine.active_transfers[0]["progress"] == 0


def test_account_switch_uses_separate_history(setup):
    engine, _, root = setup
    other = SimpleNamespace(sync_identity="other", get_service=engine.auth_manager.get_service)
    assert SyncEngine(other, str(root)).state_path != engine.state_path


def test_unreadable_state_fails_closed(setup):
    engine, _, root = setup
    path = Path(engine.state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken")
    with pytest.raises(ValueError, match="history"):
        SyncEngine(engine.auth_manager, str(root))


def test_two_cycles_are_serialized(setup):
    engine, drive, root = setup
    (root / "one.txt").write_bytes(b"data")
    threads = [threading.Thread(target=engine.sync_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert drive.creates == 1
