"""Glitch Maker — entry point with crash logging."""
import sys
import os

# When running as PyInstaller bundle, fix base path
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
    base = sys._MEIPASS
    os.environ['GLITCH_BASE'] = base
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from utils.config import load_settings
from utils.translator import set_language
from utils.logger import write_crash_log, _LOG_DIR

# Load saved language before creating QApplication
settings = load_settings()
set_language(settings.get("language", "en"))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QFont
from gui.main_window import MainWindow


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Catch unhandled exceptions, write crash log, show dialog."""
    # Don't intercept KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    # Write crash log
    crash_file = write_crash_log(exc_type, exc_value, exc_tb)

    # Print to stderr too
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_tb)

    # Show error dialog if QApplication exists
    try:
        app = QApplication.instance()
        if app is not None:
            msg = (f"An unexpected error occurred:\n\n"
                   f"{exc_type.__name__}: {exc_value}\n\n")
            if crash_file:
                msg += f"Crash log saved to:\n{crash_file}"
            QMessageBox.critical(None, "Glitch Maker — Crash", msg)
    except Exception:
        pass


def main():
    """Point d entree — initialise PyQt6, charge la langue, lance MainWindow."""
    sys.excepthook = _global_exception_handler

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
