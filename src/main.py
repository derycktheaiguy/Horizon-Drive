#!/usr/bin/env python3
"""
Horizon Drive - Entry Point
LMDE 7 / X11 Compatible Version
"""

import os
import sys

# CRITICAL: Set environment variables BEFORE any Tkinter/CTk imports
# This prevents X11 BadLength errors on Linux Mint / LMDE
os.environ['TK_SCALING'] = '1.0'
os.environ['GDK_SCALE'] = '1'
os.environ['GDK_DPI_SCALE'] = '1'

import customtkinter as ctk

# Disable all automatic DPI handling
ctk.deactivate_automatic_dpi_awareness()
ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)

import json
from auth import AuthManager
from gui import MainWindow, WelcomeWizard, SetupWizard

def load_config():
    config_path = os.path.join(os.getcwd(), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return None


def main():
    auth_manager = AuthManager()
    config = load_config()

    if not auth_manager.is_authenticated():
        # Wizard flow: Auth -> Setup -> Main
        temp_root = ctk.CTk()
        temp_root.title("Horizon Drive - Setup")
        
        def on_auth_success():
            if not config:
                show_setup_wizard(auth_manager, temp_root)
            else:
                temp_root.destroy()
                show_main_app(auth_manager, config)

        wizard = WelcomeWizard(auth_manager, on_success=on_auth_success)
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
    
    wizard = SetupWizard(on_complete=on_setup_complete)
    parent_root.mainloop()


def show_main_app(auth_manager, config):
    sync_dir = config.get("local_folder", "~/HorizonDrive")
    app = MainWindow(auth_manager, sync_dir=sync_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
