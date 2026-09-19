"""Serialized, non-destructive reconciliation of a local folder and My Drive.

Content hashes suppress watcher echoes and detect concurrent edits. Deletions
are deliberately not propagated; the UI and README explain this policy.
"""

import hashlib
import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path, PureWindowsPath

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from horizon_drive.config import _read_json, atomic_write_json

logger = logging.getLogger(__name__)
FIELDS = "id,name,mimeType,size,modifiedTime,md5Checksum"
FILES_FIELDS = f"files({FIELDS})"
FOLDER = "application/vnd.google-apps.folder"
GOOGLE_NATIVE = "application/vnd.google-apps."


class SyncHandler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine

    def on_created(self, event):
        self.engine.queue_upload(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self.engine.queue_upload(event.src_path)

    def on_moved(self, event):
        self.engine.queue_upload(event.dest_path)

    def on_deleted(self, event):
        self.engine.queue_upload(event.src_path)


class SyncEngine:
    def __init__(self, auth_manager, sync_dir, status_callback=None, sync_mode="Two-way", state_path=None):
        if sync_mode not in ("Two-way", "Backup"):
            raise ValueError("Unknown sync mode")
        self.auth_manager = auth_manager
        self.sync_dir = os.path.abspath(os.path.expanduser(sync_dir))
        self.sync_mode = sync_mode
        self.status_callback = status_callback
        os.makedirs(self.sync_dir, exist_ok=True)
        self.observer = None
        self.handler = SyncHandler(self)
        self._active_transfers = {}
        self._transfer_lock = threading.Lock()
        self._sync_lock = threading.RLock()
        self._downlink_thread = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._running = False
        self.last_error = None
        self.activity = []
        identity = getattr(auth_manager, "sync_identity", "default")
        namespace = hashlib.sha256(f"{self.sync_dir}:{identity}".encode()).hexdigest()
        state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        if not os.path.isabs(state_home):
            state_home = os.path.expanduser("~/.local/state")
        self.state_path = str(state_path or Path(state_home) / "horizon-drive" / f"{namespace}.json")
        loaded = _read_json(self.state_path)
        if os.path.exists(self.state_path) and (loaded is None or loaded.get("version") != 1):
            raise ValueError("Sync history is unreadable. Restore it before resuming sync.")
        self._state = loaded.get("files", {}) if loaded else {}
        if not isinstance(self._state, dict) or any(not isinstance(value, dict) for value in self._state.values()):
            raise ValueError("Sync history is unreadable. Restore it before resuming sync.")

    @property
    def active_transfers(self):
        with self._transfer_lock:
            return [dict(value) for value in self._active_transfers.values()]

    def _status(self, title, detail):
        if self.status_callback:
            self.status_callback(title, detail)

    def _error(self, detail):
        self.last_error = detail
        logger.error("Sync: %s", detail)
        self._status("Sync Error", detail)

    def _record(self, action, filename):
        self.activity.append(f"{action} {filename}")
        self.activity[:] = self.activity[-100:]
        self._status("Syncing...", f"{action} {filename}")

    def start(self):
        if self._running:
            return
        if self._downlink_thread and self._downlink_thread.is_alive():
            raise RuntimeError("The previous transfer is stopping. Try Resume again shortly.")
        self._stop_event.clear()
        self._wake_event.clear()
        # Watchdog threads cannot be started twice. Resume needs a fresh observer.
        self.observer = Observer()
        self.observer.schedule(self.handler, self.sync_dir, recursive=True)
        self.observer.start()
        self._running = True
        self._downlink_thread = threading.Thread(target=self._downlink_loop, daemon=True)
        self._downlink_thread.start()

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
        if self._downlink_thread and self._downlink_thread is not threading.current_thread():
            self._downlink_thread.join(timeout=2)
        self._running = False

    def queue_upload(self, local_path):
        # Coalesce notifications instead of starting an unbounded thread per event.
        if not os.path.basename(local_path).startswith(".horizon-"):
            self._wake_event.set()

    def _add_transfer(self, transfer_id, transfer_type, filename, total_bytes):
        with self._transfer_lock:
            self._active_transfers[transfer_id] = {
                "type": transfer_type,
                "filename": filename,
                "progress": 0.0,
                "bytes_transferred": 0,
                "total_bytes": total_bytes,
            }

    def _update_transfer(self, transfer_id, bytes_transferred, total_bytes):
        with self._transfer_lock:
            if transfer_id in self._active_transfers:
                self._active_transfers[transfer_id].update(
                    bytes_transferred=bytes_transferred,
                    total_bytes=total_bytes,
                    progress=min(bytes_transferred / total_bytes, 1.0) if total_bytes else 0.0,
                )

    def _remove_transfer(self, transfer_id):
        with self._transfer_lock:
            self._active_transfers.pop(transfer_id, None)

    @staticmethod
    def _component(name):
        if not isinstance(name, str) or name in ("", ".", "..") or any(c in name for c in ("/", "\\", "\0")):
            raise ValueError("A Drive filename cannot be safely stored locally.")
        if name.startswith(".horizon-"):
            raise ValueError("A Drive filename uses Horizon Drive's reserved temporary prefix.")
        if os.name == "nt" and (":" in name or name.endswith((".", " ")) or PureWindowsPath(name).is_reserved()):
            raise ValueError("A Drive filename is not supported on this computer.")
        return name

    def _local_path(self, relative):
        parts = relative.split("/")
        for part in parts:
            self._component(part)
        path = Path(self.sync_dir)
        for part in parts:
            path = path / part
            if path.is_symlink():
                raise ValueError("Symbolic links are excluded from sync.")
        if os.path.commonpath([self.sync_dir, os.path.abspath(path)]) != self.sync_dir:
            raise ValueError("File is outside the sync folder.")
        return path

    @staticmethod
    def _digest(path):
        if not path.exists():
            return None
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "md5").hexdigest()

    def _remember(self, relative, remote, digest):
        self._state[relative] = {
            "id": remote["id"],
            "local_md5": digest,
            "remote_md5": remote.get("md5Checksum", digest),
            "modifiedTime": remote.get("modifiedTime"),
        }
        atomic_write_json(self.state_path, {"version": 1, "files": self._state})

    def _list(self, query, *, order_by=None, limit=None, service=None):
        service = service or self.auth_manager.get_service()
        files, token = [], None
        while True:
            options = {"q": query, "pageSize": min(limit or 1000, 1000), "fields": f"nextPageToken,{FILES_FIELDS}"}
            if token:
                options["pageToken"] = token
            if order_by:
                options["orderBy"] = order_by
            result = service.files().list(**options).execute(num_retries=3)
            files.extend(result.get("files", []))
            token = result.get("nextPageToken")
            if not token or (limit and len(files) >= limit):
                return files[:limit] if limit else files

    def _view_files(self, query, **kwargs):
        try:
            return self._list(query, **kwargs)
        except Exception:
            self._error("Could not load Drive files. Check your connection and Google account access.")
            return []

    def list_files(self):
        return self._view_files("'root' in parents and trashed = false")

    def list_recent_files(self, limit=10):
        return self._view_files("trashed=false", order_by="modifiedTime desc", limit=limit)

    def list_starred(self):
        return self._view_files("starred=true and trashed=false")

    def list_trashed(self):
        return self._view_files("trashed=true")

    def list_shared_with_me(self):
        return self._view_files("sharedWithMe=true and trashed=false")

    def _remote_tree(self, service):
        result, directories = {}, {"": "root"}
        pending = [("", "root")]
        visited = set()
        while pending:
            prefix, parent = pending.pop()
            if parent in visited:
                raise ValueError("Drive contains an ambiguous folder hierarchy.")
            visited.add(parent)
            names = set()
            for item in self._list(f"'{parent}' in parents and trashed=false", service=service):
                name = self._component(item["name"])
                normalized = os.path.normcase(name)
                if normalized in names:
                    raise ValueError(f"Multiple Drive items share the name '{name}'. Rename one in Drive to continue.")
                names.add(normalized)
                relative = f"{prefix}/{name}" if prefix else name
                self._local_path(relative)
                result[relative] = item
                if item["mimeType"] == FOLDER:
                    directories[relative] = item["id"]
                    pending.append((relative, item["id"]))
        return result, directories

    def _local_tree(self):
        files, directories = {}, []
        for root, dirs, names in os.walk(self.sync_dir, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith(".horizon-") and not Path(root, d).is_symlink()]
            for directory in dirs:
                directories.append(Path(root, directory).relative_to(self.sync_dir).as_posix())
            for name in names:
                path = Path(root, name)
                if path.is_symlink() or name.startswith(".horizon-"):
                    continue
                relative = path.relative_to(self.sync_dir).as_posix()
                self._local_path(relative)
                files[relative] = self._digest(path)
        return files, directories

    def _preserve_conflict(self, relative):
        path = self._local_path(relative)
        digest = self._digest(path)
        copy = path.with_name(f"{path.stem} (local conflict {digest}){path.suffix}")
        self._local_path(copy.relative_to(self.sync_dir).as_posix())
        if copy.exists() and self._digest(copy) != digest:
            raise ValueError("The conflict-copy filename is already occupied. Rename it before syncing.")
        if not copy.exists():
            shutil.copy2(path, copy)
        self._record("Preserved local conflict", copy.relative_to(self.sync_dir).as_posix())

    def upload_file(self, local_path, remote=None, parent_id="root"):
        relative = Path(os.path.abspath(local_path)).relative_to(self.sync_dir).as_posix()
        transfer_id = f"upload:{relative}"
        media = None
        with self._sync_lock:
            try:
                path = self._local_path(relative)
                digest = self._digest(path)
                if digest is None:
                    return False
                self._add_transfer(transfer_id, "upload", relative, path.stat().st_size)
                self._status("Syncing...", f"Uploading {relative}")
                service = self.auth_manager.get_service()
                media = MediaFileUpload(str(path), chunksize=1024 * 1024, resumable=True)
                if remote:
                    request = service.files().update(fileId=remote["id"], media_body=media, fields=FIELDS)
                else:
                    request = service.files().create(
                        body={"name": path.name, "parents": [parent_id]}, media_body=media, fields=FIELDS
                    )
                response = None
                while response is None:
                    if self._stop_event.is_set():
                        return False
                    status, response = request.next_chunk(num_retries=3)
                    if status:
                        self._update_transfer(transfer_id, status.resumable_progress, path.stat().st_size)
                # If the file changed mid-transfer, the next pass retries that edit.
                self._remember(relative, response, digest)
                self._record("Uploaded", relative)
                return True
            except Exception:
                self._error(f"Could not upload {relative}. Check your connection, storage space, and account access.")
                return False
            finally:
                if media is not None:
                    media.stream().close()
                self._remove_transfer(transfer_id)

    def download_file(self, file_id, filename, remote=None):
        transfer_id = f"download:{filename}"
        temporary = None
        with self._sync_lock:
            try:
                path = self._local_path(filename)
                before = self._digest(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                self._add_transfer(transfer_id, "download", filename, 0)
                self._status("Syncing...", f"Downloading {filename}")
                service = self.auth_manager.get_service()
                request = service.files().get_media(fileId=file_id)
                fd, temporary = tempfile.mkstemp(prefix=".horizon-", suffix=".part", dir=path.parent)
                with os.fdopen(fd, "wb") as handle:
                    downloader = MediaIoBaseDownload(handle, request, chunksize=1024 * 1024)
                    done = False
                    while not done:
                        if self._stop_event.is_set():
                            return False
                        status, done = downloader.next_chunk(num_retries=3)
                        if status:
                            self._update_transfer(transfer_id, status.resumable_progress, status.total_size or 0)
                    handle.flush()
                    os.fsync(handle.fileno())
                digest = self._digest(Path(temporary))
                if remote and remote.get("md5Checksum") and remote["md5Checksum"] != digest:
                    raise ValueError("The cloud file changed while downloading. It will be retried.")
                self._local_path(filename)  # Recheck links immediately before replacement.
                if self._digest(path) != before:
                    raise ValueError("Local file changed while downloading. Both copies were left intact.")
                os.replace(temporary, path)
                self._remember(filename, remote or {"id": file_id}, digest)
                self._record("Downloaded", filename)
                return True
            except Exception:
                self._error(f"Could not safely download {filename}. Your existing local file has been kept.")
                return False
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
                self._remove_transfer(transfer_id)

    def sync_once(self):
        """Reconcile a complete snapshot. Never interpret a failed listing as deletion."""
        with self._sync_lock:
            self.last_error = None
            service = self.auth_manager.get_service()
            remote, parents = self._remote_tree(service)
            local, local_dirs = self._local_tree()
            skipped = 0
            # Create folders before files, in depth order. Existing folders retain their IDs.
            for relative in sorted(local_dirs, key=lambda value: (value.count("/"), value)):
                if self._stop_event.is_set():
                    return
                if relative in remote and remote[relative]["mimeType"] != FOLDER:
                    raise ValueError(f"A local folder and cloud file both use '{relative}'. Rename one to continue.")
                if relative not in parents:
                    parent = relative.rpartition("/")[0]
                    created = (
                        service.files()
                        .create(
                            body={
                                "name": relative.rsplit("/", 1)[-1],
                                "mimeType": FOLDER,
                                "parents": [parents[parent]],
                            },
                            fields="id",
                        )
                        .execute()
                    )
                    parents[relative] = created["id"]
            if self.sync_mode == "Two-way":
                for relative in parents:
                    if relative:
                        self._local_path(relative).mkdir(parents=True, exist_ok=True)
            for relative in sorted(set(local) | set(remote)):
                if self._stop_event.is_set():
                    return
                cloud = remote.get(relative)
                if cloud and cloud["mimeType"].startswith(GOOGLE_NATIVE):
                    if cloud["mimeType"] != FOLDER:
                        skipped += 1
                    continue
                digest = local.get(relative)
                previous = self._state.get(relative)
                if not cloud:
                    if previous:
                        # Remote deletion/rename must not silently recreate an unwanted file.
                        skipped += 1
                    elif digest is not None:
                        self.upload_file(
                            str(self._local_path(relative)), parent_id=parents[relative.rpartition("/")[0]]
                        )
                    continue
                if digest is None:
                    if self.sync_mode == "Two-way":
                        self.download_file(cloud["id"], relative, cloud)
                    continue
                if cloud.get("md5Checksum") == digest:
                    self._remember(relative, cloud, digest)
                    continue
                local_changed = not previous or digest != previous.get("local_md5")
                remote_changed = (
                    not previous
                    or cloud["id"] != previous.get("id")
                    or (
                        cloud.get("md5Checksum") != previous.get("remote_md5")
                        or cloud.get("modifiedTime") != previous.get("modifiedTime")
                    )
                )
                if local_changed and remote_changed:
                    if self.sync_mode == "Backup":
                        self._error(
                            f"Conflict in {relative}. Both copies were kept. Rename your local copy to back it up."
                        )
                        continue
                    self._preserve_conflict(relative)
                    self.download_file(cloud["id"], relative, cloud)
                elif local_changed:
                    self.upload_file(str(self._local_path(relative)), cloud)
                elif remote_changed and self.sync_mode == "Two-way":
                    self.download_file(cloud["id"], relative, cloud)
            if not self.last_error and not self._stop_event.is_set():
                if skipped:
                    self._status(
                        "Sync limited", f"{skipped} cloud-only or removed items need attention. See sync policy."
                    )
                else:
                    self._status("Up to date", "All supported files are synchronized")

    def _downlink_loop(self):
        while not self._stop_event.is_set():
            self._wake_event.clear()
            try:
                self.sync_once()
            except Exception as exc:
                logger.warning("Sync cycle stopped: %s", exc)
                self._error(
                    "Sync could not finish. Check your connection, account, and duplicate or unsupported filenames."
                )
            self._wake_event.wait(60)
            if self._wake_event.is_set():
                self._stop_event.wait(0.5)
