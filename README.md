# 🌌 Horizon Drive (Linux Edition)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/derycktheaiguy/Horizon-Drive/actions/workflows/ci.yml/badge.svg)](https://github.com/derycktheaiguy/Horizon-Drive/actions/workflows/ci.yml)
[![OS: Linux](https://img.shields.io/badge/OS-Linux-orange.svg)](https://www.linux.org/)

**Horizon Drive** is a premium, native Google Drive desktop client for Linux (optimized for LMDE 7). Designed for power users transitioning from Windows, it brings the "Fluent Design" aesthetic and bulletproof syncing to the Linux desktop.


## ✨ Features

- **System Tray with live status icons** (grey = paused/offline, blue = syncing, green = up to date)
- **Real-time transfer queue** with progress bars for uploads and downloads
- **Live Google Drive storage quota** display in the sidebar
- **Smart views**: Recent files, Starred, Trash, and Shared with me — all live from Google Drive
- **BYOK (Bring Your Own Key)**: Enhanced privacy and speed by using your own Google Cloud API credentials. No shared client bottlenecks.
- **Two-Way Sync Engine**: Reliable background sync powered by `watchdog` for real-time file monitoring.
- **Dark-themed Fluent Design UI**: Polished interface with glassmorphism, rounded corners, and smooth micro-animations.
- **Secure by Design**: Credentials and tokens are stored exclusively in the Linux `keyring`. No plain-text secrets.

## 🚀 Getting Started

### Prerequisites

- Python 3.12 or higher
- `pip` (Python package manager)
- A Google Cloud Project (for API keys)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/derycktheaiguy/Horizon-Drive.git
   cd Horizon-Drive
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Or install as a package**:
   ```bash
   # Install directly
   pip install .

   # Or install in editable/dev mode
   pip install -e .[dev]
   ```

4. **Launch the application**:
   ```bash
   horizon-drive

   # Or from a source checkout (no install):
   PYTHONPATH=src python3 -m horizon_drive.main
   ```

### Development

```bash
pip install -e .[dev]

# Run the test suite
pytest

# Lint and format checks
ruff check src/ tests/
ruff format --check src/ tests/

# Build a wheel
python -m build --wheel
```

> **Coming soon:** `pip install horizon-drive` will be available on PyPI.

## 📸 Screenshots

<!-- Add screenshots to assets/ directory -->

## 🎨 Icon Assets

Icons are generated programmatically by pystray at runtime (grey, blue, and green status indicators). For custom icons, place PNG files in `assets/`:

- `assets/google_drive_icon.png` — the main window icon

## 🛠 Setup (BYOK Flow)

To protect your privacy and ensure maximum performance, Horizon Drive requires your own Google API keys:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named "Horizon Drive".
3. Enable the **Google Drive API**.
4. Configure the **OAuth Consent Screen** (External).
5. Create **OAuth 2.0 Client IDs** (Application type: Desktop App).
6. Copy your **Client ID** and **Client Secret** into the Horizon Drive Welcome Wizard.

## 🏛 Core Philosophy

1. **Credibility First**: Clean, modular code structured for public audits.
2. **User Sovereignty**: You own your data. We facilitate, we do not control.
3. **Visual Excellence**: No default widgets. Every pixel is styled to feel premium.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---
Built with ❤️ by **Horizon Hub Media**. Let's make Linux beautiful.
