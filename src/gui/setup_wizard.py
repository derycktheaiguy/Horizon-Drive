import customtkinter as ctk
import os
import json
import logging
from tkinter import filedialog

logger = logging.getLogger(__name__)


class SetupWizard(ctk.CTkToplevel):
    def __init__(self, on_complete):
        super().__init__()
        self.on_complete = on_complete

        self.title("Horizon Drive - Initial Setup")
        self.geometry("600x500")
        self.attributes("-topmost", True)
        
        # Default configuration
        self.config = {
            "local_folder": os.path.expanduser("~/HorizonDrive"),
            "sync_mode": "Two-way"
        }

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Step 1: Welcome
        self.title_label = ctk.CTkLabel(self.main_frame, text="Welcome to Horizon Drive", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(30, 10))

        self.subtitle_label = ctk.CTkLabel(self.main_frame, text="Let's configure your local cargo hold.", font=ctk.CTkFont(size=14))
        self.subtitle_label.pack(pady=10)

        # Step 2: Choose Local Folder
        self.folder_label = ctk.CTkLabel(self.main_frame, text="Local Sync Folder:", font=ctk.CTkFont(weight="bold"))
        self.folder_label.pack(pady=(30, 5), anchor="w", padx=40)
        
        self.folder_inner_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.folder_inner_frame.pack(fill="x", padx=40)
        
        self.folder_entry = ctk.CTkEntry(self.folder_inner_frame, width=350)
        self.folder_entry.insert(0, self.config["local_folder"])
        self.folder_entry.pack(side="left", padx=(0, 10))
        
        self.browse_button = ctk.CTkButton(self.folder_inner_frame, text="Browse", width=80, command=self._browse_folder)
        self.browse_button.pack(side="left")

        # Step 3: Select Sync Mode
        self.mode_label = ctk.CTkLabel(self.main_frame, text="Sync Mode:", font=ctk.CTkFont(weight="bold"))
        self.mode_label.pack(pady=(30, 10), anchor="w", padx=40)
        
        self.mode_var = ctk.StringVar(value=self.config["sync_mode"])
        self.mode_two_way = ctk.CTkRadioButton(self.main_frame, text="Two-way Sync (Cloud <-> Local)", variable=self.mode_var, value="Two-way")
        self.mode_two_way.pack(pady=5, anchor="w", padx=60)
        
        self.mode_backup = ctk.CTkRadioButton(self.main_frame, text="Backup Only (Local -> Cloud)", variable=self.mode_var, value="Backup")
        self.mode_backup.pack(pady=5, anchor="w", padx=60)

        # Finish
        self.finish_button = ctk.CTkButton(self.main_frame, text="Start Syncing", command=self._finish, height=45, font=ctk.CTkFont(weight="bold"))
        self.finish_button.pack(pady=(40, 20))

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=os.path.expanduser("~"))
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)

    def _finish(self):
        self.config["local_folder"] = self.folder_entry.get().strip()
        self.config["sync_mode"] = self.mode_var.get()
        
        # Save config
        config_path = os.path.join(os.getcwd(), "config.json")
        try:
            with open(config_path, "w") as f:
                json.dump(self.config, f, indent=4)
            
            self.destroy()
            self.on_complete(self.config)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

if __name__ == "__main__":
    def dummy_complete(config):
        print(f"Setup complete: {config}")
    
    app = ctk.CTk()
    wizard = SetupWizard(dummy_complete)
    app.mainloop()
