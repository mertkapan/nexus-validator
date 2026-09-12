"""
NEXUS v1.0.0 Application Bootstrap & Main Entry Point
Platform Authentication State Validator and Telemetry Extraction Suite.
"""

import sys
import os

# Ensure local nexus package is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from nexus.config import APP_NAME
from nexus.ui.main_window import NexusMainWindow


def main():
    # Enable High DPI Scaling
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)

    window = NexusMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
