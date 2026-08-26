import logging
import webbrowser

import customtkinter as ctk

logger = logging.getLogger(__name__)


class WelcomeWizard(ctk.CTkToplevel):
    def __init__(self, auth_manager, on_success):
        super().__init__()

        self.auth_manager = auth_manager
        self.on_success = on_success

        self.title("Welcome to Horizon Drive")
        self.geometry("600x500")
        self.attributes("-topmost", True)

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.main_frame, text="Horizon Drive Setup", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=(30, 10))

        self.info_label = ctk.CTkLabel(
            self.main_frame,
            text="To ensure maximum privacy and speed, Horizon Drive uses your own personal Google connection.",
            wraplength=500,
            justify="center",
        )
        self.info_label.pack(pady=10)

        self.keys_button = ctk.CTkButton(
            self.main_frame,
            text="Get My Secure Keys",
            command=self._open_help_doc,
            fg_color="#3D3D3D",
            hover_color="#4D4D4D",
        )
        self.keys_button.pack(pady=10)

        self.client_id_label = ctk.CTkLabel(self.main_frame, text="Client ID:")
        self.client_id_label.pack(pady=(20, 0), anchor="w", padx=40)
        self.client_id_entry = ctk.CTkEntry(self.main_frame, width=400, placeholder_text="Paste your Client ID here")
        self.client_id_entry.pack(pady=5)

        self.client_secret_label = ctk.CTkLabel(self.main_frame, text="Client Secret:")
        self.client_secret_label.pack(pady=(10, 0), anchor="w", padx=40)
        self.client_secret_entry = ctk.CTkEntry(
            self.main_frame, width=400, placeholder_text="Paste your Client Secret here", show="*"
        )
        self.client_secret_entry.pack(pady=5)

        self.auth_button = ctk.CTkButton(
            self.main_frame,
            text="Connect to Google Drive",
            command=self._start_auth,
            height=40,
            font=ctk.CTkFont(weight="bold"),
        )
        self.auth_button.pack(pady=30)

        self.status_label = ctk.CTkLabel(self.main_frame, text="", text_color="gray")
        self.status_label.pack(pady=5)

    def _open_help_doc(self):
        # Placeholder for help doc
        webbrowser.open("https://github.com/HorizonHubMedia/HorizonDrive/wiki/Setup")

    def _start_auth(self):
        client_id = self.client_id_entry.get().strip()
        client_secret = self.client_secret_entry.get().strip()

        if not client_id or not client_secret:
            self.status_label.configure(text="Please enter both Client ID and Secret.", text_color="red")
            return

        self.status_label.configure(text="Authenticating in browser...", text_color="blue")
        self.update()

        try:
            self.auth_manager.set_client_secrets(client_id, client_secret)
            self.auth_manager.authenticate()
            self.status_label.configure(text="Authentication successful!", text_color="green")
            self.after(1000, self._on_complete)
        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}", text_color="red")

    def _on_complete(self):
        self.destroy()
        self.on_success()
