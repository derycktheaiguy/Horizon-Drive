import logging
import queue
import threading
import webbrowser

import customtkinter as ctk

logger = logging.getLogger(__name__)
GOOGLE_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"


class WelcomeWizard(ctk.CTkToplevel):
    def __init__(self, master, auth_manager, on_success):
        super().__init__(master)

        self.auth_manager = auth_manager
        self.on_success = on_success

        self.title("Welcome to Horizon Drive")
        self.geometry("600x500")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.master.destroy)
        self._auth_results = queue.SimpleQueue()

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
        webbrowser.open(GOOGLE_CREDENTIALS_URL)

    def _start_auth(self):
        client_id = self.client_id_entry.get().strip()
        client_secret = self.client_secret_entry.get().strip()

        if not client_id or not client_secret:
            self.status_label.configure(text="Please enter both Client ID and Secret.", text_color="red")
            return

        self.status_label.configure(text="Authenticating in browser...", text_color="blue")
        self.auth_button.configure(state="disabled")

        def authenticate():
            try:
                self.auth_manager.set_client_secrets(client_id, client_secret)
                self.auth_manager.authenticate()
                self._auth_results.put(True)
            except Exception:
                self._auth_results.put(False)

        threading.Thread(target=authenticate, daemon=True).start()
        self.after(100, self._check_auth)

    def _check_auth(self):
        try:
            success = self._auth_results.get_nowait()
        except queue.Empty:
            self.after(100, self._check_auth)
            return
        self.auth_button.configure(state="normal")
        if success:
            self._on_complete()
        else:
            self.status_label.configure(
                text="Could not connect. Check your keys, test-user access, and unlocked system keyring.",
                text_color="#FF7777",
                wraplength=470,
            )

    def _on_complete(self):
        self.destroy()
        self.on_success()
