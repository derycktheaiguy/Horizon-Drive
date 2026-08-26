import io
import logging
import os
import threading
import time

from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

FILES_FIELDS = "files(id,name,mimeType,size,modifiedTime)"


class SyncHandler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine

    def on_created(self, event):
        if not event.is_directory:
            logger.info("Watchdog: Created file %s", event.src_path)
            self.engine.queue_upload(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            logger.info("Watchdog: Modified file %s", event.src_path)
            self.engine.queue_upload(event.src_path)


class SyncEngine:
    def __init__(self, auth_manager, sync_dir, status_callback=None):
        self.auth_manager = auth_manager
        self.sync_dir = os.path.expanduser(sync_dir)
        self.status_callback = status_callback
        self.observer = Observer()
        self.handler = SyncHandler(self)

        # Transfer queue
        self._active_transfers = {}
        self._transfer_lock = threading.Lock()

        # Ensure sync directory exists
        if not os.path.exists(self.sync_dir):
            os.makedirs(self.sync_dir)
            logger.info("SyncEngine: Created directory %s", self.sync_dir)

        # Downlink loop setup
        self._downlink_thread = None
        self._stop_event = threading.Event()

    @property
    def active_transfers(self):
        """Returns a list of active transfer dicts.

        Each dict: {type: 'upload'|'download', filename: str, progress: 0.0-1.0,
                     bytes_transferred: int, total_bytes: int}
        """
        with self._transfer_lock:
            return list(self._active_transfers.values())

    def start(self):
        self._stop_event.clear()
        self.observer.schedule(self.handler, self.sync_dir, recursive=False)
        self.observer.start()

        # Start background downlink polling
        self._downlink_thread = threading.Thread(target=self._downlink_loop)
        self._downlink_thread.daemon = True
        self._downlink_thread.start()

        logger.info("SyncEngine: Monitoring and Polling %s", self.sync_dir)

    def stop(self):
        self._stop_event.set()
        self.observer.stop()
        self.observer.join()
        if self._downlink_thread:
            self._downlink_thread.join(timeout=2)

    def queue_upload(self, local_path):
        thread = threading.Thread(target=self.upload_file, args=(local_path,))
        thread.daemon = True
        thread.start()

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
                t = self._active_transfers[transfer_id]
                t["bytes_transferred"] = bytes_transferred
                t["total_bytes"] = total_bytes
                t["progress"] = bytes_transferred / total_bytes if total_bytes > 0 else 0.0

    def _remove_transfer(self, transfer_id):
        with self._transfer_lock:
            self._active_transfers.pop(transfer_id, None)

    def upload_file(self, local_path):
        filename = os.path.basename(local_path)
        total_bytes = os.path.getsize(local_path)
        transfer_id = f"upload:{filename}"

        self._add_transfer(transfer_id, "upload", filename, total_bytes)

        # UI Feedback: Syncing
        if self.status_callback:
            self.status_callback("Syncing...", f"Uploading {filename}")

        try:
            service = self.auth_manager.get_service()

            file_metadata = {"name": filename}
            media = MediaFileUpload(local_path, resumable=True)

            logger.info("SyncEngine: Uploading %s to Google Drive...", filename)

            request = service.files().create(body=file_metadata, media_body=media, fields="id")
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    bytes_done = int(status.resumable_progress)
                    self._update_transfer(transfer_id, bytes_done, total_bytes)

            logger.info("SyncEngine: Uploaded successfully. File ID: %s", response.get("id"))

        except Exception as e:
            logger.error("SyncEngine: Error uploading file %s: %s", filename, e)
            if self.status_callback:
                self.status_callback("Sync Error", str(e))
            self._remove_transfer(transfer_id)
            return

        self._remove_transfer(transfer_id)

        # UI Feedback: Up to date
        if self.status_callback:
            self.status_callback("Up to date", "All files are synchronized")

    def list_files(self):
        """Fetches files from the root of Google Drive."""
        try:
            service = self.auth_manager.get_service()
            results = (
                service.files()
                .list(pageSize=50, fields=f"nextPageToken,{FILES_FIELDS}", q="'root' in parents and trashed = false")
                .execute()
            )
            return results.get("files", [])
        except Exception as e:
            logger.error("SyncEngine: Error listing files: %s", e)
            return []

    def list_recent_files(self, limit=10):
        """Fetches most recently modified files from Google Drive."""
        try:
            service = self.auth_manager.get_service()
            results = (
                service.files()
                .list(orderBy="modifiedTime desc", pageSize=limit, fields=FILES_FIELDS, q="trashed=false")
                .execute()
            )
            return results.get("files", [])
        except Exception as e:
            logger.error("SyncEngine: Error listing recent files: %s", e)
            return []

    def list_starred(self):
        """Fetches starred files from Google Drive."""
        try:
            service = self.auth_manager.get_service()
            results = service.files().list(pageSize=50, fields=FILES_FIELDS, q="starred=true").execute()
            return results.get("files", [])
        except Exception as e:
            logger.error("SyncEngine: Error listing starred files: %s", e)
            return []

    def list_trashed(self):
        """Fetches trashed files from Google Drive."""
        try:
            service = self.auth_manager.get_service()
            results = service.files().list(pageSize=50, fields=FILES_FIELDS, q="trashed=true").execute()
            return results.get("files", [])
        except Exception as e:
            logger.error("SyncEngine: Error listing trashed files: %s", e)
            return []

    def list_shared_with_me(self):
        """Fetches files shared with the user."""
        try:
            service = self.auth_manager.get_service()
            results = service.files().list(pageSize=50, fields=FILES_FIELDS, q="sharedWithMe=true").execute()
            return results.get("files", [])
        except Exception as e:
            logger.error("SyncEngine: Error listing shared files: %s", e)
            return []

    def download_file(self, file_id, filename):
        """Downloads a specific file from Google Drive."""
        local_path = os.path.join(self.sync_dir, filename)
        transfer_id = f"download:{filename}"

        self._add_transfer(transfer_id, "download", filename, 0)

        if self.status_callback:
            self.status_callback("Syncing...", f"Downloading {filename}")

        try:
            service = self.auth_manager.get_service()
            request = service.files().get_media(fileId=file_id)

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    total = status.total_size or 0
                    bytes_done = status.resumable_progress
                    self._update_transfer(transfer_id, bytes_done, total)

            with open(local_path, "wb") as f:
                f.write(fh.getbuffer())

            logger.info("SyncEngine: Downloaded %s", filename)
            self._remove_transfer(transfer_id)
            return True
        except Exception as e:
            logger.error("SyncEngine: Error downloading %s: %s", filename, e)
            self._remove_transfer(transfer_id)
            return False
        finally:
            if self.status_callback:
                self.status_callback("Up to date", "All files are synchronized")

    def _downlink_loop(self):
        """Background polling loop for cloud-to-local sync."""
        while not self._stop_event.is_set():
            logger.info("SyncEngine: Checking for remote changes (Downlink)...")
            cloud_files = self.list_files()
            local_files = os.listdir(self.sync_dir)

            for cf in cloud_files:
                if self._stop_event.is_set():
                    break

                # Flat files only for now, skip folders
                if cf["mimeType"] == "application/vnd.google-apps.folder":
                    continue

                if cf["name"] not in local_files:
                    logger.info("SyncEngine: Finding remote file %s missing locally. Downloading...", cf["name"])
                    self.download_file(cf["id"], cf["name"])

            # Sleep for 60 seconds unless stopped
            for _ in range(60):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
