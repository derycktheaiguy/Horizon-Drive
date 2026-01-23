import customtkinter as ctk
from PIL import Image, ImageTk
import os
import sys
import webbrowser
import threading
from engine.sync_engine import SyncEngine


class MainWindow(ctk.CTk):
    def __init__(self, auth_manager, sync_dir="~/HorizonDrive"):
        super().__init__()
        
        self.auth_manager = auth_manager
        self.sync_dir = sync_dir
        self._after_ids = []
        self._is_closing = False

        self.title("Horizon Drive")
        self.geometry("1100x700")

        # Load and set window icon
        self._setup_icon()

        # Set appearance mode and color theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.current_view = "Home"
        self.view_mode = "List"  # Grid vs List
        self.show_transfer_queue = False
        
        # Initialize and Start Sync Engine
        self.engine = SyncEngine(self.auth_manager, self.sync_dir, status_callback=self.update_sync_status)
        self.engine.start()

        self._build_sidebar()
        self._build_main_content()
        
        # Safe Shutdown Protocol
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_icon(self):
        """Load and apply the Google Drive icon for taskbar and sidebar with proper aspect ratio."""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            
            # Try multiple possible icon names
            icon_candidates = [
                os.path.join(project_root, "assets", "google_drive_icon.png"),
                os.path.join(project_root, "assets", "google_drive_icon"),
                os.path.join(project_root, "assets", "icon.png"),
            ]
            
            icon_path = None
            for candidate in icon_candidates:
                if os.path.exists(candidate):
                    icon_path = candidate
                    break
            
            if icon_path:
                img = Image.open(icon_path)
                
                # Convert to RGBA if not already (for transparency support)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # --- TASKBAR ICON (64x64 with preserved aspect ratio) ---
                taskbar_size = 64
                original_w, original_h = img.size
                ratio = min(taskbar_size / original_w, taskbar_size / original_h)
                new_w = int(original_w * ratio)
                new_h = int(original_h * ratio)
                
                # Resize preserving aspect ratio
                img_scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Create transparent canvas and paste centered
                taskbar_canvas = Image.new('RGBA', (taskbar_size, taskbar_size), (0, 0, 0, 0))
                offset_x = (taskbar_size - new_w) // 2
                offset_y = (taskbar_size - new_h) // 2
                taskbar_canvas.paste(img_scaled, (offset_x, offset_y), img_scaled)
                
                self.taskbar_icon = ImageTk.PhotoImage(taskbar_canvas)
                self.wm_iconphoto(True, self.taskbar_icon)
                
                # --- SIDEBAR LOGO (height=32, width proportional) ---
                sidebar_height = 32
                sidebar_ratio = sidebar_height / original_h
                sidebar_w = int(original_w * sidebar_ratio)
                
                img_sidebar = img.resize((sidebar_w, sidebar_height), Image.Resampling.LANCZOS)
                
                self.sidebar_icon_img = ctk.CTkImage(
                    light_image=img_sidebar,
                    dark_image=img_sidebar,
                    size=(sidebar_w, sidebar_height)
                )
            else:
                self.sidebar_icon_img = None
                print("UI Warning: No icon found in assets/")
        except Exception as e:
            self.sidebar_icon_img = None
            print(f"UI Warning: Could not load icon: {e}")


    def _build_sidebar(self):
        # Sidebar - Pitch Black (#121212)
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#121212")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Logo container with icon + text
        self.logo_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.logo_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        if hasattr(self, 'sidebar_icon_img') and self.sidebar_icon_img:
            self.logo_icon = ctk.CTkLabel(self.logo_frame, image=self.sidebar_icon_img, text="")
            self.logo_icon.pack(side="left", padx=(0, 10))
        
        self.logo_label = ctk.CTkLabel(self.logo_frame, text="Horizon Drive", font=ctk.CTkFont(size=18, weight="bold"))
        self.logo_label.pack(side="left")

        # Navigation buttons
        self.home_button = self._create_sidebar_button("🏠  Home", row=1, command=lambda: self._switch_view("Home"))
        self.my_drive_button = self._create_sidebar_button("📁  My Drive", row=2, command=lambda: self._switch_view("My Drive"))
        self.shared_button = self._create_sidebar_button("👥  Shared with me", row=3, command=lambda: self._switch_view("Shared"))
        self.computers_button = self._create_sidebar_button("💻  Computers", row=4, command=lambda: self._switch_view("Computers"))
        
        # Separator space
        self.starred_button = self._create_sidebar_button("⭐  Starred", row=5, pady=(40, 5), command=lambda: self._switch_view("Starred"))
        self.trash_button = self._create_sidebar_button("🗑️  Trash", row=6, command=lambda: self._switch_view("Trash"))
        self.storage_button = self._create_sidebar_button("📊  Storage", row=7, command=lambda: self._switch_view("Storage"))

        # --- STORAGE SECTION (Pinned to bottom) ---
        self.sidebar_bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.sidebar_bottom_frame.grid(row=9, column=0, sticky="ew", padx=15, pady=20)
        
        # Mini Quota
        self.sidebar_quota_label = ctk.CTkLabel(self.sidebar_bottom_frame, text="Storage (45%)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#888888")
        self.sidebar_quota_label.pack(anchor="w", padx=5)
        
        self.sidebar_quota_bar = ctk.CTkProgressBar(self.sidebar_bottom_frame, height=6, progress_color="#34A853", fg_color="#404040")
        self.sidebar_quota_bar.set(0.45)
        self.sidebar_quota_bar.pack(fill="x", pady=5, padx=5)
        
        self.buy_storage_btn = ctk.CTkButton(
            self.sidebar_bottom_frame, text="Buy Storage", height=30, 
            fg_color="#3D3D3D", hover_color="#4D4D4D", font=ctk.CTkFont(size=12),
            command=lambda: webbrowser.open("https://one.google.com/storage")
        )
        self.buy_storage_btn.pack(fill="x", pady=(10, 5))

        self.trash_indicator = ctk.CTkLabel(self.sidebar_bottom_frame, text="🗑  Trash: 0 items", font=ctk.CTkFont(size=10), text_color="#666666")
        self.trash_indicator.pack(anchor="w", padx=5)

    def _create_sidebar_button(self, text, row, pady=5, command=None):
        button = ctk.CTkButton(
            self.sidebar_frame, text=text, corner_radius=8, height=40,
            font=ctk.CTkFont(size=14), fg_color="transparent",
            text_color="#E0E0E0", hover_color="#2D2D2D", anchor="w",
            command=command
        )
        button.grid(row=row, column=0, padx=15, pady=pady, sticky="ew")
        return button

    def _build_main_content(self):
        # Main Content - Dark Grey (#1E1E1E)
        self.main_container = ctk.CTkFrame(self, corner_radius=15, fg_color="#1E1E1E")
        self.main_container.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(2, weight=1)

        # Header with Status Cards
        self.header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        # Sync Status Card (Now full width or center)
        self.sync_card = ctk.CTkFrame(self.header_frame, corner_radius=12, fg_color="#2D2D2D", border_width=1, border_color="#3D3D3D")
        self.sync_card.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        
        self.sync_title = ctk.CTkLabel(self.sync_card, text="Up to date", font=ctk.CTkFont(size=18, weight="bold"))
        self.sync_title.pack(padx=20, pady=(15, 5), anchor="w")
        self.sync_subtitle = ctk.CTkLabel(self.sync_card, text="Monitoring ~/HorizonDrive", font=ctk.CTkFont(size=12), text_color="#888888")
        self.sync_subtitle.pack(padx=20, pady=(0, 15), anchor="w")

        # Transfer Queue Toggle (Header Right)
        self.transfer_btn = ctk.CTkButton(
            self.header_frame, text="⇅  Transfers", width=120, height=45,
            corner_radius=8, fg_color="#2D2D2D", border_width=1, border_color="#3D3D3D",
            hover_color="#3D3D3D", command=self._toggle_transfer_queue
        )
        self.transfer_btn.grid(row=0, column=1, sticky="nse")

        # Search Bar & View Toggles
        self.search_row_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.search_row_frame.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="ew")
        self.search_row_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            self.search_row_frame, placeholder_text="🔍  Search in Drive", 
            height=45, corner_radius=22, fg_color="#2D2D2D", border_color="#3D3D3D",
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        
        self.view_toggle_frame = ctk.CTkFrame(self.search_row_frame, fg_color="transparent")
        self.view_toggle_frame.grid(row=0, column=1, padx=(15, 0))
        
        self.list_view_btn = ctk.CTkButton(self.view_toggle_frame, text="☰", width=40, height=40, corner_radius=8, fg_color="#2D2D2D", command=lambda: self._set_view_mode("List"))
        self.list_view_btn.pack(side="left", padx=2)
        
        self.grid_view_btn = ctk.CTkButton(self.view_toggle_frame, text="▦", width=40, height=40, corner_radius=8, fg_color="transparent", command=lambda: self._set_view_mode("Grid"))
        self.grid_view_btn.pack(side="left", padx=2)

        # Dynamic Content Area
        self.content_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        # Transfer Queue Panel (Hidden by default)
        self.transfer_panel = ctk.CTkFrame(self.main_container, height=150, corner_radius=12, fg_color="#121212", border_width=1, border_color="#3D3D3D")
        # Grid placement managed by toggle
        
        self._switch_view("Home")

    def update_sync_status(self, title, subtitle):
        """Thread-safe sync status update."""
        if self._is_closing:
            return
        try:
            after_id = self.after(0, lambda: self._update_ui_labels(title, subtitle))
            self._after_ids.append(after_id)
        except:
            pass

    def _update_ui_labels(self, title, subtitle):
        if self._is_closing:
            return
        try:
            self.sync_title.configure(text=title)
            self.sync_subtitle.configure(text=subtitle)
        except:
            pass

    def _switch_view(self, view_name):
        """Switch the main content area based on navigation selection."""
        if self._is_closing:
            return

        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        self.current_view = view_name
        
        if view_name == "Home":
            self._render_home_view()
        elif view_name == "My Drive":
            self._render_loading_state()
            # Threaded fetch
            threading.Thread(target=self._fetch_and_render_my_drive).start()
        elif view_name == "Shared":
            self._render_placeholder_view("Shared with me", "Files shared with you will appear here.")
        elif view_name == "Computers":
            self._render_placeholder_view("Computers", "Backup folders from your computers.")
        elif view_name == "Starred":
            self._render_placeholder_view("Starred", "Your starred files and folders.")
        elif view_name == "Trash":
            self._render_placeholder_view("Trash", "Items in trash will be deleted after 30 days.")
        elif view_name == "Storage":
            self._render_storage_view()
    
    def _render_loading_state(self):
        """Shows a loading message while fetching data."""
        self.loading_label = ctk.CTkLabel(self.content_frame, text="Fetching files from Google Drive...", font=ctk.CTkFont(size=14))
        self.loading_label.pack(pady=50)

    def _fetch_and_render_my_drive(self):
        """Background thread operation to list files."""
        if not hasattr(self, 'engine') or self.engine is None:
            return

        files = self.engine.list_files()
        if not self._is_closing:
            self.after(0, lambda: self._render_my_drive_view(files))

    def _render_my_drive_view(self, cloud_files=None):
        """My Drive view with real cloud data or placeholder."""
        if self._is_closing:
            return

        # Clear loading state
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        header_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 20))
        
        header = ctk.CTkLabel(header_frame, text="My Drive", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(side="left")
        
        if not cloud_files:
            empty_label = ctk.CTkLabel(self.content_frame, text="Your Drive is empty or could not be loaded.", font=ctk.CTkFont(size=14), text_color="#666666")
            empty_label.pack(pady=50)
            return

        # Render based on mode
        if self.view_mode == "Grid":
            self._render_grid_view(cloud_files)
        else:
            self._render_list_view(cloud_files)

    def _render_list_view(self, cloud_files):
        """Classic list view with folders at top."""
        # Split into folders and files
        folders = [f for f in cloud_files if f['mimeType'] == 'application/vnd.google-apps.folder']
        files = [f for f in cloud_files if f['mimeType'] != 'application/vnd.google-apps.folder']

        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)

        # Folders
        if folders:
            ctk.CTkLabel(scroll, text="Folders", font=ctk.CTkFont(size=13), text_color="#888888").pack(anchor="w", padx=5, pady=(0, 10))
            for f in folders:
                item = self._create_list_item(scroll, "📁", f['name'], "Folder")
                item.pack(fill="x", pady=2)

        # Files
        if files:
            ctk.CTkLabel(scroll, text="Files", font=ctk.CTkFont(size=13), text_color="#888888").pack(anchor="w", padx=5, pady=(20, 10))
            for f in files:
                icon = self._get_mime_icon(f['mimeType'])
                size = self._format_size(f.get('size', 0))
                item = self._create_list_item(scroll, icon, f['name'], size)
                item.pack(fill="x", pady=2)

    def _render_grid_view(self, cloud_files):
        """Modern grid view with large icons."""
        scroll = ctk.CTkScrollableFrame(self.content_frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        
        # Grid settings
        columns = 4
        
        for i, f in enumerate(cloud_files):
            row = i // columns
            col = i % columns
            
            card = ctk.CTkFrame(scroll, fg_color="#2A2A2A", corner_radius=12, width=160, height=140)
            card.grid(row=row, column=col, padx=10, pady=10)
            card.grid_propagate(False)
            
            icon = "📁" if f['mimeType'] == 'application/vnd.google-apps.folder' else self._get_mime_icon(f['mimeType'])
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=40)).pack(pady=(25, 10))
            ctk.CTkLabel(card, text=self._truncate_string(f['name'], 15), font=ctk.CTkFont(size=12, weight="bold")).pack()

    def _create_list_item(self, master, icon, name, details):
        item = ctk.CTkFrame(master, fg_color="#262626", corner_radius=8, height=50)
        item.pack_propagate(False)
        ctk.CTkLabel(item, text=icon, font=ctk.CTkFont(size=18)).pack(side="left", padx=15)
        ctk.CTkLabel(item, text=name, font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkLabel(item, text=details, font=ctk.CTkFont(size=11), text_color="#888888").pack(side="right", padx=15)
        return item

    def _set_view_mode(self, mode):
        if self.view_mode == mode: return
        self.view_mode = mode
        # Update button styles
        if mode == "Grid":
            self.grid_view_btn.configure(fg_color="#2D2D2D")
            self.list_view_btn.configure(fg_color="transparent")
        else:
            self.list_view_btn.configure(fg_color="#2D2D2D")
            self.grid_view_btn.configure(fg_color="transparent")
        # Re-render if in My Drive
        if self.current_view == "My Drive":
            self._switch_view("My Drive")

    def _toggle_transfer_queue(self):
        self.show_transfer_queue = not self.show_transfer_queue
        if self.show_transfer_queue:
            self.transfer_panel.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")
            self.transfer_btn.configure(fg_color="#1E1E1E")
            self._render_transfer_queue()
        else:
            self.transfer_panel.grid_forget()
            self.transfer_btn.configure(fg_color="#2D2D2D")

    def _render_transfer_queue(self):
        for widget in self.transfer_panel.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(self.transfer_panel, text="Active Transfers", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10, padx=20, anchor="w")
        
        # Dummy data for now
        dummy_transfers = [
            ("↑  Uploading", "Quarterly_Results.pdf", 0.75),
            ("↓  Downloading", "Vacation_Videos.zip", 0.30)
        ]
        
        for status, name, progress in dummy_transfers:
            row = ctk.CTkFrame(self.transfer_panel, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=2)
            ctk.CTkLabel(row, text=f"{status}: {name}", font=ctk.CTkFont(size=12)).pack(side="left")
            bar = ctk.CTkProgressBar(row, width=200, height=4, progress_color="#34A853")
            bar.set(progress)
            bar.pack(side="right", padx=10)

    def _truncate_string(self, s, length):
        return s if len(s) <= length else s[:length-3] + "..."

    def _get_mime_icon(self, mime_type):
        if "pdf" in mime_type: return "📄"
        if "spreadsheet" in mime_type or "excel" in mime_type: return "📊"
        if "wordprocessingml" in mime_type or "word" in mime_type: return "📝"
        if "image" in mime_type: return "🖼️"
        if "video" in mime_type: return "🎬"
        return "📄"

    def _format_size(self, size_bytes):
        size_bytes = int(size_bytes)
        if size_bytes == 0: return "0 B"
        import math
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
    
    def _render_home_view(self):
        """Placeholder for Home view."""
        header = ctk.CTkLabel(self.content_frame, text="Home / Recent Activity", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(padx=10, pady=(10, 20), anchor="w")
        
        placeholder = ctk.CTkLabel(self.content_frame, text="Recent activity will appear here soon.", font=ctk.CTkFont(size=14), text_color="#666666")
        placeholder.pack(pady=50)

    def _render_placeholder_view(self, title, message):
        """Generic placeholder for unimplemented views."""
        header = ctk.CTkLabel(self.content_frame, text=title, font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(padx=10, pady=(10, 20), anchor="w")
        
        placeholder = ctk.CTkLabel(self.content_frame, text=message, font=ctk.CTkFont(size=14), text_color="#666666")
        placeholder.pack(pady=50)
    
    def _render_storage_view(self):
        """Storage breakdown view."""
        header = ctk.CTkLabel(self.content_frame, text="Storage", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(padx=10, pady=(10, 20), anchor="w")
        
        # Large progress indicator
        progress_frame = ctk.CTkFrame(self.content_frame, fg_color="#2A2A2A", corner_radius=15, height=120)
        progress_frame.pack(fill="x", padx=10, pady=10)
        progress_frame.pack_propagate(False)
        
        ctk.CTkLabel(progress_frame, text="45 GB of 100 GB used (45%)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))
        
        large_bar = ctk.CTkProgressBar(progress_frame, width=400, height=12, progress_color="#34A853", fg_color="#404040")
        large_bar.set(0.45)
        large_bar.pack(pady=(0, 20))
        
        # Breakdown
        breakdown = [
            ("📄 Google Drive", "30 GB", 0.67),
            ("📧 Gmail", "10 GB", 0.22),
            ("📸 Google Photos", "5 GB", 0.11),
        ]
        
        for label, size, pct in breakdown:
            item = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            item.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(item, text=label, font=ctk.CTkFont(size=13)).pack(side="left")
            ctk.CTkLabel(item, text=size, font=ctk.CTkFont(size=13), text_color="#888888").pack(side="right")

    def on_closing(self):
        """Safe shutdown."""
        if self._is_closing:
            return
            
        self._is_closing = True
        print("Shutting down...")
        
        if hasattr(self, 'engine'):
            try:
                self.engine.stop()
            except:
                pass
            
        for aid in self._after_ids:
            try:
                self.after_cancel(aid)
            except:
                pass
        
        self.destroy()
        self.quit()


if __name__ == "__main__":
    pass
