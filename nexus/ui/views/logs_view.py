"""
Execution Logs View
High-contrast terminal console displaying timestamped engine events and network diagnostics.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor

from nexus.config import COLOR_HIT, COLOR_FREE, COLOR_INVALID, COLOR_WARN


class LogsView(QWidget):
    """Terminal event logging view."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        view_title = QLabel("EXECUTION LOGS")
        view_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        view_title.setStyleSheet("color: #ffffff;")

        view_desc = QLabel("Real-time event stream, cryptographic handshake telemetry, and worker events")
        view_desc.setStyleSheet("color: #7b8294; font-size: 12px;")

        title_box.addWidget(view_title)
        title_box.addWidget(view_desc)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.autoscroll_check = QCheckBox("Auto-scroll")
        self.autoscroll_check.setChecked(True)
        header_layout.addWidget(self.autoscroll_check)

        self.clear_btn = QPushButton("Clear Console")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_logs)

        self.save_btn = QPushButton("Save Logs")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_logs)

        header_layout.addWidget(self.clear_btn)
        header_layout.addWidget(self.save_btn)
        layout.addLayout(header_layout)

        # Log Terminal Console
        self.console = QPlainTextEdit()
        self.console.setObjectName("LogConsole")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)

        layout.addWidget(self.console)

    def append_log(self, message: str, level: str = "INFO"):
        color_map = {
            "SUCCESS": COLOR_HIT,
            "INFO": "#80b3ff",
            "WARNING": COLOR_WARN,
            "ERROR": COLOR_INVALID,
        }
        color = color_map.get(level.upper(), "#c9d1d9")
        html_line = f"<span style='color: {color};'>{message}</span>"
        
        self.console.appendHtml(html_line)

        if self.autoscroll_check.isChecked():
            self.console.moveCursor(QTextCursor.MoveOperation.End)

    def _clear_logs(self):
        self.console.clear()

    def _save_logs(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Log Output", "execution.log", "Log Files (*.log);;All Files (*)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.console.toPlainText())
