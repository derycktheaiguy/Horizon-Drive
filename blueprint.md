# PROJECT BLUEPRINT: Horizon Drive (Linux Edition)

## OBJECTIVE
Build a "Flagship" Google Drive desktop client for Linux Mint Debian Edition (LMDE 7) that rivals the official Windows 11 client. This software will be the credibility anchor for Horizon Hub Media.

## KEY FEATURES (MVP)

### 1. The "Bring Your Own Key" (BYOK) Authentication Flow
* **Context:** To avoid Google's "Error 401: Disabled Client," we will not ship with a shared API key.
* **The Workflow:**
    1.  On first launch, show a "Welcome Wizard."
    2.  Explain clearly: "To ensure maximum privacy and speed, Horizon Drive uses your own personal Google connection."
    3.  Provide a button: "Get My Secure Keys" (Links to a help doc we will write later).
    4.  Input Fields: Client ID, Client Secret.
    5.  Action: Authenticate via Browser -> Save Token to Linux Keyring.

### 2. The "Windows 11" Dashboard
* Replicate the layout of the reference image.
* **Dashboard Tabs:**
    * **Activity:** Real-time log of files syncing ("Uploaded report.pdf", "Downloaded photo.jpg").
    * **Preferences:** Options to choose which local folder mirrors the cloud (Two-way Sync).
    * **Quota:** Visual progress bar of storage usage.

### 3. The Engine (Sync vs. Mount)
* **Phase 1 Goal:** Create a reliable **Two-Way Sync** engine.
    * Users select a local folder: `~/HorizonDrive`.
    * The app monitors changes in that folder (using `watchdog`) and uploads them instantly.
    * The app polls Google Drive API for remote changes and downloads them.
* *Note: Do not attempt FUSE mounting in Phase 1. Focus on bulletproof syncing first.*

### 4. System Tray Integration
* The app must minimize to the system tray (top right in Cinnamon/LMDE).
* Icon state changes:
    * Grey Icon: Paused/Offline.
    * Spinning/Blue Icon: Syncing.
    * Checkmark Icon: Up to date.

## DELIVERABLES FOR THIS SESSION
1.  Initialize the Python project structure (clean, modular folders).
2.  Create the `requirements.txt`.
3.  Build the `AuthManager` class (handling the BYOK flow).
4.  Build the Main GUI Shell (The visual skeleton matching the image).

Let's make HHM proud. Execute Phase 1.
