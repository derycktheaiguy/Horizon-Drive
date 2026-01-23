import customtkinter as ctk
from PIL import Image
import os

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Horizon Drive")
        self.geometry("1100x700")

        # Set appearance mode and color theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_content()

    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Google Drive", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.home_button = self._create_sidebar_button("Home", row=1)
        self.my_drive_button = self._create_sidebar_button("My Drive", row=2)
        self.shared_button = self._create_sidebar_button("Shared with me", row=3)
        self.computers_button = self._create_sidebar_button("Computers", row=4)
        
        # Spacer
        self.starred_button = self._create_sidebar_button("Starred", row=5, pady=(40, 0))
        self.trash_button = self._create_sidebar_button("Trash", row=6)
        self.storage_button = self._create_sidebar_button("Storage", row=7)

    def _create_sidebar_button(self, text, row, pady=5):
        button = ctk.CTkButton(self.sidebar_frame, text=text, corner_radius=8, height=40, font=ctk.CTkFont(size=14))
        button.grid(row=row, column=0, padx=20, pady=pady, sticky="ew")
        return button

    def _build_main_content(self):
        self.main_container = ctk.CTkFrame(self, corner_radius=15, fg_color="#1E1E1E")
        self.main_container.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Header Section (Syncing Status & Quota)
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        # Syncing Status Card
        self.sync_card = ctk.CTkFrame(self.header_frame, corner_radius=10, fg_color="#2D2D2D", border_width=1, border_color="#3D3D3D")
        self.sync_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        
        self.sync_title = ctk.CTkLabel(self.sync_card, text="Syncing...", font=ctk.CTkFont(size=20, weight="bold"))
        self.sync_title.pack(padx=20, pady=(15, 5), anchor="w")
        self.sync_subtitle = ctk.CTkLabel(self.sync_card, text="All files are up to date", font=ctk.CTkFont(size=12), text_color="gray")
        self.sync_subtitle.pack(padx=20, pady=(0, 15), anchor="w")

        # Quota Card
        self.quota_card = ctk.CTkFrame(self.header_frame, corner_radius=10, fg_color="#2D2D2D", border_width=1, border_color="#3D3D3D")
        self.quota_card.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        
        self.quota_title = ctk.CTkLabel(self.quota_card, text="Storage quota", font=ctk.CTkFont(size=14, weight="bold"))
        self.quota_title.pack(padx=20, pady=(15, 5), anchor="w")
        
        self.quota_bar = ctk.CTkProgressBar(self.quota_card, width=200)
        self.quota_bar.set(0.45)
        self.quota_bar.pack(padx=20, pady=5)
        
        self.quota_text = ctk.CTkLabel(self.quota_card, text="45GB of 100GB used", font=ctk.CTkFont(size=12), text_color="gray")
        self.quota_text.pack(padx=20, pady=(0, 15), anchor="w")

        # Search Bar
        self.search_entry = ctk.CTkEntry(self.main_container, placeholder_text="Search in Drive", height=40, corner_radius=20, fg_color="#2D2D2D", border_color="#3D3D3D")
        self.search_entry.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        # File List Area (Placeholder for now)
        self.file_list_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.file_list_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.main_container.grid_rowconfigure(2, weight=1)

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
