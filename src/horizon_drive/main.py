#!/usr/bin/env python3
"""
Horizon Drive - Entry Point
LMDE 7 / X11 Compatible Version
"""

import logging
import os

# CRITICAL: Set environment variables BEFORE any Tkinter/CTk imports
# This prevents X11 BadLength errors on Linux Mint / LMDE
os.environ["TK_SCALING"] = "1.0"
os.environ["GDK_SCALE"] = "1"
os.environ["GDK_DPI_SCALE"] = "1"

import customtkinter as ctk  # noqa: E402  (must import after env vars above)

# Disable all automatic DPI handling
ctk.deactivate_automatic_dpi_awareness()
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)

# System tray support is optional. In some Flatpak runtimes the
# AppIndicator D-Bus typelibs are unavailable, which makes importing
# pystray raise. Degrade gracefully so the main window still launches.
_TRY_TRAY = True
try:
    import pystray  # noqa: E402
except Exception as exc:  # noqa: BLE001
    import logging

    logging.getLogger(__name__).warning("System tray unavailable: %s", exc)
    pystray = None
    _TRY_TRAY = False

from PIL import Image, ImageDraw  # noqa: E402

from horizon_drive.auth import AuthManager  # noqa: E402
from horizon_drive.config import load_config  # noqa: E402
from horizon_drive.gui import MainWindow, SetupWizard, WelcomeWizard  # noqa: E402


def _create_tray_icons():
    """Generate 64x64 RGBA tray icons programmatically.

    Returns:
        dict with keys 'paused' (grey square), 'syncing' (blue square),
        'uptodate' (green circle with white checkmark).
    """
    size = 64

    # Grey rounded square — paused/offline
    grey = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(grey)
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(128, 128, 128, 255))

    # Blue rounded square — syncing
    blue = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(blue)
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(66, 133, 244, 255))

    # Green circle with white checkmark — up to date
    green = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(green)
    draw.ellipse([8, 8, 56, 56], fill=(52, 168, 83, 255))
    draw.line([(22, 33), (29, 42), (42, 24)], fill=(255, 255, 255, 255), width=5)

    return {
        "paused": grey,
        "syncing": blue,
        "uptodate": green,
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    auth_manager = AuthManager()
    config = load_config()

    if not auth_manager.is_authenticated():
        # Wizard flow: Auth -> Setup -> Main
        temp_root = ctk.CTk()
        temp_root.title("Horizon Drive - Setup")
        temp_root.withdraw()

        def on_auth_success():
            if not config:
                show_setup_wizard(auth_manager, temp_root)
            else:
                temp_root.destroy()
                show_main_app(auth_manager, config)

        WelcomeWizard(temp_root, auth_manager, on_success=on_auth_success)
        temp_root.mainloop()
    elif not config:
        # Already authed, but no config
        show_setup_wizard(auth_manager)
    else:
        show_main_app(auth_manager, config)


def show_setup_wizard(auth_manager, parent_root=None):
    if not parent_root:
        parent_root = ctk.CTk()
        parent_root.withdraw()

    def on_setup_complete(config):
        parent_root.destroy()
        show_main_app(auth_manager, config)

    SetupWizard(parent_root, on_complete=on_setup_complete)
    parent_root.mainloop()


def show_main_app(auth_manager, config):
    sync_dir = config.get("local_folder", "~/HorizonDrive")
    app = MainWindow(auth_manager, sync_dir=sync_dir)

    # Generate tray icons (used if a system tray is available)
    icons = _create_tray_icons()
    app.tray_icons = icons

    # System tray is optional: some Flatpak runtimes lack AppIndicator support.
    if pystray is not None:
        # Tray menu callbacks (must marshal into CTk thread via after())
        def restore_window(icon, item):
            app.after(0, app.restore_window)

        def toggle_sync(icon, item):
            app.after(0, app.toggle_sync)

        def force_quit(icon, item):
            app.after(0, app.force_quit)

        menu = pystray.Menu(
            pystray.MenuItem("Open", restore_window, default=True),
            pystray.MenuItem("Pause Sync", toggle_sync),
            pystray.MenuItem("Quit", force_quit),
        )

        tray_icon = pystray.Icon("horizon_drive", icons["uptodate"], "Horizon Drive", menu)
        app.tray_icon = tray_icon
        tray_icon.run_detached()

    app.mainloop()


if __name__ == "__main__":
    main()
