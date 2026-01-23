from auth import AuthManager
from gui import MainWindow, WelcomeWizard
import customtkinter as ctk

class HorizonDriveApp:
    def __init__(self):
        self.auth_manager = AuthManager()
        self.root = None

    def run(self):
        if not self.auth_manager.is_authenticated():
            self._show_welcome_wizard()
        else:
            self._show_main_window()

    def _show_welcome_wizard(self):
        self.wizard = WelcomeWizard(self.auth_manager, on_success=self._show_main_window)
        self.wizard.mainloop()

    def _show_main_window(self):
        if hasattr(self, 'wizard') and self.wizard:
            # WelcomeWizard is a Toplevel, but since it's the first window, 
            # we need to handle the transition carefully if we want it to be the main loop.
            # Actually, standard CTk practice is one CTk instance.
            pass
        
        self.root = MainWindow()
        self.root.mainloop()

if __name__ == "__main__":
    # Standardizing on a single main loop
    auth_manager = AuthManager()
    
    if not auth_manager.is_authenticated():
        # Setup temporary root for wizard
        temp_root = ctk.CTk()
        temp_root.withdraw()
        
        def on_auth_success():
            temp_root.destroy()
            app = MainWindow()
            app.mainloop()

        wizard = WelcomeWizard(auth_manager, on_success=on_auth_success)
        temp_root.mainloop()
    else:
        app = MainWindow()
        app.mainloop()
