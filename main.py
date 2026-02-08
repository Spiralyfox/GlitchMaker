"""Glitch Maker — entry point."""
import sys
import os

# When running as PyInstaller bundle, fix base path
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
    # Make sure bundled data folders are found
    base = sys._MEIPASS
    os.environ['GLITCH_BASE'] = base
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from utils.config import load_settings
from utils.translator import set_language

# Load saved language before creating QApplication
settings = load_settings()
set_language(settings.get("language", "en"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from gui.main_window import MainWindow

def main():
    """Point d entree — initialise PyQt6, charge la langue, lance MainWindow."""
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
