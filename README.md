# 🌌 Horizon Drive (Linux Edition)

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/derycktheaiguy/Horizon-Drive/actions/workflows/ci.yml/badge.svg)](https://github.com/derycktheaiguy/Horizon-Drive/actions/workflows/ci.yml)
[![OS: Linux](https://img.shields.io/badge/OS-Linux-orange.svg)](https://www.linux.org/)

**Horizon Drive** is a premium, native Google Drive desktop client for Linux. Designed for power users transitioning from Windows, it brings the "Fluent Design" aesthetic and bulletproof syncing to the Linux desktop.

- **System Tray with live status icons** (grey = paused/offline, blue = syncing, green = up to date)
- **Real-time transfer queue** with progress bars for uploads and downloads
- **Live Google Drive storage quota** display in the sidebar
- **Smart views**: Recent files, Starred, Trash, and Shared with me — all live from Google Drive
- **BYOK (Bring Your Own Key)**: Enhanced privacy and speed by using your own Google Cloud API credentials. No shared client bottlenecks.
- **Two-Way Sync Engine**: Background sync powered by `watchdog` for real-time file monitoring plus cloud-to-local polling.
- **Dark-themed Fluent Design UI**: Glassmorphism, rounded corners, smooth micro-animations.
- **Secure by Design**: Credentials and tokens are stored exclusively in the Linux `keyring`. No plain-text secrets.

---

## 📦 Installation

All releases are published at:
**https://github.com/derycktheaiguy/Horizon-Drive/releases/latest**

Three packages are provided. Pick **one**:

| Package | Best for | Needs |
|---|---|---|
| `.AppImage` | Any distro, zero setup | `libfuse2`, desktop session |
| `.flatpak` | Flatpak users (Pop!_OS, Mint, Fedora…) | `flatpak` |
| `.whl` | Developers, CLI users | Python 3.12+ |

### Option 1 — AppImage (recommended, works everywhere)

```bash
# Download from the releases page, then:
chmod +x HorizonDrive-*-x86_64.AppImage
./HorizonDrive-*-x86_64.AppImage
```

Optional — integrate into your app menu so it behaves like a normal installed app:

- **Easiest:** install [AppImageLauncher](https://github.com/TheAssassin/AppImageLauncher) — double-clicking any AppImage then offers "Integrate and run".
- **Manual:** move it somewhere permanent and launch from there:

```bash
mkdir -p ~/.local/bin
mv HorizonDrive-*-x86_64.AppImage ~/.local/bin/horizon-drive
~/.local/bin/horizon-drive
```

> The AppImage is self-contained: it bundles its own Python interpreter and all libraries. Nothing else to install.

### Option 2 — Flatpak

The bundle is distributed via GitHub Releases (not yet on Flathub), so install it directly:

```bash
flatpak install --user ./Horizon-Drive-*-x86_64.flatpak
flatpak run io.github.derycktheaiguy.HorizonDrive
```

### Option 3 — Wheel (pip / pipx)

Requires **Python 3.12+** and `tk` on your system:

```bash
# pipx (isolated, recommended)
pipx install horizon_drive-0.2.1-py3-none-any.whl

# or plain pip
pip install horizon_drive-0.2.1-py3-none-any.whl
```

Then launch with `horizon-drive`.

If Python complains about `tkinter`, install the system tk package first (see [Troubleshooting](#-troubleshooting)).

### Option 4 — From source

```bash
git clone https://github.com/derycktheaiguy/Horizon-Drive.git
cd Horizon-Drive

python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]

horizon-drive          # run the app
pytest                 # run the test suite
```

Without installing, you can also run directly from a checkout:

```bash
PYTHONPATH=src python3 -m horizon_drive.main
```

---

## 🔑 First Run — Google API Setup (BYOK)

Horizon Drive uses **your own** Google Cloud credentials, so your data never passes through a shared intermediary.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named e.g. "Horizon Drive".
3. Enable the **Google Drive API** (*APIs & Services → Library*).
4. Configure the **OAuth Consent Screen** (*External* is fine).
   - While your app is in *Testing* mode, add your own Google account under **Test users** — otherwise login will fail with `access_blocked`.
5. Create **OAuth 2.0 Client IDs** (*Credentials → Create Credentials*):
   - Application type: **Desktop App** ← must be Desktop, or you'll get `redirect_uri_mismatch`
6. Launch Horizon Drive and paste your **Client ID** and **Client Secret** into the Welcome Wizard.
7. A browser window opens → sign in → allow access. Tokens are stored in your system keyring.

Your sync folder defaults to `~/HorizonDrive` and is created automatically.

---

## ⚙️ Configuration

Settings live in a simple `config.json`:

```json
{
    "local_folder": "/home/you/HorizonDrive",
    "sync_mode": "Two-way"
}
```

> **Note:** the app looks for `config.json` in the directory it is launched **from**. If you change your sync folder in the Setup Wizard, the file is written next to wherever you started the app. Simplest fix: delete `config.json` and re-run the wizard from the same place you normally launch Horizon Drive from (usually your home directory).

To reset everything (including stored credentials):

```bash
rm config.json
python3 -c "import keyring; [keyring.delete_password('HorizonDrive', k) for k in ('client_id','client_secret','refresh_token')]"
```

---

## 🛠 Troubleshooting

Common failure modes and their fixes, grouped by symptom.

### AppImage won't start

**Error: `dlopen(): error loading libfuse.so.2`**
Your system lacks FUSE 2. Either install it, or run the AppImage without FUSE:

```bash
# Ubuntu / Debian / Pop!_OS / Mint
sudo apt install libfuse2        # or libfuse2t64 on newer releases

# Fedora
sudo dnf install fuse

# Arch
sudo pacman -S fuse2

# Permanent no-FUSE workaround: extract once, run the binary directly
./HorizonDrive-*-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun
```

**Error: `Permission denied`**
You forgot to make it executable: `chmod +x HorizonDrive-*-x86_64.AppImage`.

**"No such file or directory" on old 32-bit systems**
Releases are x86_64 only. An ARM build is not yet provided.

### Blank window / rendering glitches on Wayland

CustomTkinter renders through XWayland. The app sets safe DPI variables itself, but if you see blank/frozen visuals:

```bash
GDK_BACKEND=x11 ./HorizonDrive-*-x86_64.AppImage
```

On NVIDIA + Wayland, also try:

```bash
__GL_YIELD="USLEEP" GDK_BACKEND=x11 ./HorizonDrive-*-x86_64.AppImage
```

### `ModuleNotFoundError: No module named 'tkinter'` (source/wheel installs)

Tkinter is part of Python but shipped as a separate system package:

```bash
# Ubuntu / Debian / Pop!_OS / Mint / LMDE
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk

# openSUSE
sudo zypper install python3-tk
```

### Keyring / credential errors at startup

**Error: `NoKeyringError` or `Cannot connect to Secret Service`**

Horizon Drive stores tokens in your desktop keyring. Headless or minimal systems may lack one:

```bash
# GNOME-based systems (Pop!_OS, Mint, Fedora Workstation)
sudo apt install gnome-keyring libsecret-1-0   # deb-based
sudo dnf install gnome-keyring                  # Fedora

# KDE systems
sudo apt install kwalletmanager                 # deb-based
```

Then make sure a keyring daemon is running (`gnome-keyring-daemon` or `kwalletd5`). On servers without any GUI, there is no secure storage available — run Horizon Drive on a desktop session.

**Emergency fallback (stores secret in plain text — use only on single-user machines):**

```bash
pip install keyrings.alt
```

### Login window opens but authentication fails

| Error shown by Google | Cause | Fix |
|---|---|---|
| `redirect_uri_mismatch` | Client created as "Web application" | Recreate as **Desktop App** type |
| `access_blocked` / app not verified | OAuth consent screen still in Testing | Add your account under **Test users** |
| `invalid_grant` | Stale refresh token | Delete stored credentials (see reset above), re-authenticate |
| Browser doesn't open | No default browser set | Copy the printed URL into a browser manually |

**Firewall note:** the OAuth flow starts a temporary local HTTP server on `localhost` with a random port. Outbound HTTPS to `accounts.google.com` must be allowed; nothing external connects *in*, so port-forwarding is never required.

### Sync behaves unexpectedly

- **Files upload but never appear locally / vice-versa:** the downlink poll runs every 60 seconds. Give it a minute.
- **Deleted files come back:** deletion propagation isn't implemented in v0.2.x — deleting locally re-downloads on the next poll, and vice versa. Move files out of the sync folder rather than deleting if unsure.
- **Subfolders aren't synced:** only flat top-level files are supported right now.
- **Sync seems stuck after suspend/resume:** pause and resume from the tray menu (Pause Sync).

### System tray icon missing (GNOME)

GNOME removed legacy tray support. Install an extension:

```bash
sudo apt install gnome-shell-extension-appindicator   # Pop!_OS / Mint / Ubuntu
```

Log out/in afterwards. KDE Plasma and Cinnamon show the tray out of the box.

### Flatpak-specific issues

**Tray icon or keyring prompt missing inside sandbox:**

```bash
flatpak override --user --talk-name=org.kde.StatusNotifierWatcher \
  --talk-name=org.freedesktop.secrets io.github.derycktheaiguy.HorizonDrive
```

(The bundled build already requests these — this override helps if your desktop's portal stack is unusual.)

**Sync folder outside `$HOME`:**

```bash
flatpak override --user --filesystem=/mnt/data io.github.derycktheaiguy.HorizonDrive
```

**Reset the app entirely:**

```bash
flatpak uninstall --user --delete-data io.github.derycktheaiguy.HorizonDrive
```

### Verbose logging

Launch with debug output to attach to a bug report:

```bash
PYTHONFAULTHANDLER=1 python3 -m horizon_drive.main 2>&1 | tee horizon-debug.log
```

Open an issue at https://github.com/derycktheaiguy/Horizon-Drive/issues with the log attached (redact anything that looks like a token!).

---

## 🧪 Development

```bash
pip install -e .[dev]
pytest                          # 42 tests
ruff check src/ tests/          # lint
ruff format --check src/ tests/ # formatting gate
python -m build --wheel         # build artifact
```

CI runs all of the above on every push to `main`; tagging `v*` publishes wheel + AppImage + Flatpak bundle to GitHub Releases automatically.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---
Built with ❤️ by **Horizon Hub Media**. Let's make Linux beautiful.
