import os
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

class SyncHandler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine

    def on_created(self, event):
        if not event.is_directory:
            print(f"Watchdog: Created file {event.src_path}")
            self.engine.queue_upload(event.src_path)

    def on_modified(self, event):
        # Optional: Handle modifications if needed, but spec emphasizes creation for now
        if not event.is_directory:
            print(f"Watchdog: Modified file {event.src_path}")
            self.engine.queue_upload(event.src_path)

class SyncEngine:
    def __init__(self, auth_manager, sync_dir, status_callback=None):
        self.auth_manager = auth_manager
        self.sync_dir = os.path.expanduser(sync_dir)
        self.status_callback = status_callback
        self.observer = Observer()
        self.handler = SyncHandler(self)
        
        # Ensure sync directory exists
        if not os.path.exists(self.sync_dir):
            os.makedirs(self.sync_dir)
            print(f"SyncEngine: Created directory {self.sync_dir}")
        
        # Downlink loop setup
        self._downlink_thread = None
        self._stop_event = threading.Event()

    def start(self):
        self._stop_event.clear()
        self.observer.schedule(self.handler, self.sync_dir, recursive=False)
        self.observer.start()
        
        # Start background downlink polling
        self._downlink_thread = threading.Thread(target=self._downlink_loop)
        self._downlink_thread.daemon = True
        self._downlink_thread.start()
        
        print(f"SyncEngine: Monitoring and Polling {self.sync_dir}")

    def stop(self):
        self._stop_event.set()
        self.observer.stop()
        self.observer.join()
        if self._downlink_thread:
            self._downlink_thread.join(timeout=2)

    def queue_upload(self, local_path):
        # For now, immediate upload in a new thread to avoid blocking watchdog
        thread = threading.Thread(target=self.upload_file, args=(local_path,))
        thread.daemon = True
        thread.start()

    def upload_file(self, local_path):
        filename = os.path.basename(local_path)
        
        # UI Feedback: Syncing
        if self.status_callback:
            self.status_callback("Syncing...", f"Uploading {filename}")

        try:
            service = self.auth_manager.get_service()
            
            file_metadata = {'name': filename}
            media = MediaFileUpload(local_path, resumable=True)
            
            print(f"SyncEngine: Uploading {filename} to Google Drive...")
            file = service.files().create(body=file_metadata,
                                        media_body=media,
                                        fields='id').execute()
            print(f"SyncEngine: Uploaded successfully. File ID: {file.get('id')}")

        except Exception as e:
            print(f"SyncEngine: Error uploading file {filename}: {e}")
            if self.status_callback:
                self.status_callback("Sync Error", str(e))
                return

        # UI Feedback: Up to date
        if self.status_callback:
            self.status_callback("Up to date", "All files are synchronized")

    def list_files(self):
        """Fetches files from the root of Google Drive."""
        try:
            service = self.auth_manager.get_service()
            results = service.files().list(
                pageSize=50,
                fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                q="'root' in parents and trashed = false"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"SyncEngine: Error listing files: {e}")
            return []

    def download_file(self, file_id, filename):
        """Downloads a specific file from Google Drive."""
        local_path = os.path.join(self.sync_dir, filename)
        
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
                # print(f"Download {filename} {int(status.progress() * 100)}%.")

            with open(local_path, 'wb') as f:
                f.write(fh.getbuffer())
                
            print(f"SyncEngine: Downloaded {filename}")
            return True
        except Exception as e:
            print(f"SyncEngine: Error downloading {filename}: {e}")
            return False
        finally:
             if self.status_callback:
                self.status_callback("Up to date", "All files are synchronized")

    def _downlink_loop(self):
        """Background polling loop for cloud-to-local sync."""
        while not self._stop_event.is_set():
            print("SyncEngine: Checking for remote changes (Downlink)...")
            cloud_files = self.list_files()
            local_files = os.listdir(self.sync_dir)
            
            for cf in cloud_files:
                if self._stop_event.is_set(): break
                
                # Flat files only for now, skip folders
                if cf['mimeType'] == 'application/vnd.google-apps.folder':
                    continue
                    
                if cf['name'] not in local_files:
                    print(f"SyncEngine: Finding remote file {cf['name']} missing locally. Downloading...")
                    self.download_file(cf['id'], cf['name'])
            
            # Sleep for 60 seconds unless stopped
            for _ in range(60):
                if self._stop_event.is_set(): break
                time.sleep(1)
