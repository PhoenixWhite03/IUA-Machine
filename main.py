import sys
from PyQt5.QtWidgets import QApplication
from lib.paths import DATA_PATH, get_saved_theme
from src.iua_manager import IUAManager
from src.ui.app_window import IUAApp

# ==========================================
# PUNTO DE ENTRADA
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    manager = IUAManager(DATA_PATH)
    window = IUAApp(manager)
    window.showMaximized()

    # Aplica inmediatamente la interfaz y los logos según la última sesión guardada
    window.change_theme(get_saved_theme())
    window.change_logos(get_saved_theme())
    
    sys.exit(app.exec_())
