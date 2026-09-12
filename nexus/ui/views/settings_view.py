"""
Settings Configuration View
Allows customization of storage directories, export formats, custom headers, and notification webhooks.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QCheckBox, QFileDialog, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from nexus.config import RESULTS_DIR, DEFAULT_USER_AGENT, COLOR_ACCENT


class SettingsView(QWidget):
    """Configuration management view."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        view_title = QLabel("SYSTEM CONFIGURATION")
        view_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        view_title.setStyleSheet("color: #ffffff;")

        view_desc = QLabel("Configure persistence targets, network telemetry profiles, and notification sinks")
        view_desc.setStyleSheet("color: #7b8294; font-size: 12px;")

        title_box.addWidget(view_title)
        title_box.addWidget(view_desc)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Settings Card 1: Storage and Persistence
        card1 = QFrame()
        card1.setObjectName("CardPanel")
        c1_layout = QVBoxLayout(card1)
        c1_layout.setContentsMargins(18, 16, 18, 16)
        c1_layout.setSpacing(12)

        c1_title = QLabel("STORAGE & EXPORT FORMATS")
        c1_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c1_title.setStyleSheet(f"color: {COLOR_ACCENT};")
        c1_layout.addWidget(c1_title)

        dir_lbl = QLabel("Results Destination Directory:")
        dir_lbl.setStyleSheet("color: #a0a6b5;")
        self.dir_input = QLineEdit(str(RESULTS_DIR))
        self.browse_dir_btn = QPushButton("Select Folder")
        self.browse_dir_btn.clicked.connect(self._browse_dir)

        dir_box = QHBoxLayout()
        dir_box.addWidget(self.dir_input)
        dir_box.addWidget(self.browse_dir_btn)
        c1_layout.addWidget(dir_lbl)
        c1_layout.addLayout(dir_box)

        # Format checkboxes
        format_lbl = QLabel("Active Export Targets:")
        format_lbl.setStyleSheet("color: #a0a6b5;")
        c1_layout.addWidget(format_lbl)

        formats_box = QHBoxLayout()
        self.chk_hits_txt = QCheckBox("Formatted Hits (hits.txt)")
        self.chk_hits_txt.setChecked(True)
        self.chk_free_txt = QCheckBox("Free Tier (free.txt)")
        self.chk_free_txt.setChecked(True)
        self.chk_json = QCheckBox("Structured Telemetry (results.json)")
        self.chk_json.setChecked(True)
        self.chk_csv = QCheckBox("Summary Table (summary.csv)")
        self.chk_csv.setChecked(True)

        formats_box.addWidget(self.chk_hits_txt)
        formats_box.addWidget(self.chk_free_txt)
        formats_box.addWidget(self.chk_json)
        formats_box.addWidget(self.chk_csv)
        c1_layout.addLayout(formats_box)

        layout.addWidget(card1)

        # Settings Card 2: Network Profile
        card2 = QFrame()
        card2.setObjectName("CardPanel")
        c2_layout = QVBoxLayout(card2)
        c2_layout.setContentsMargins(18, 16, 18, 16)
        c2_layout.setSpacing(12)

        c2_title = QLabel("NETWORK TELEMETRY PROFILE")
        c2_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        c2_title.setStyleSheet(f"color: {COLOR_ACCENT};")
        c2_layout.addWidget(c2_title)

        ua_lbl = QLabel("Custom User-Agent Signature:")
        ua_lbl.setStyleSheet("color: #a0a6b5;")
        self.ua_input = QLineEdit(DEFAULT_USER_AGENT)
        c2_layout.addWidget(ua_lbl)
        c2_layout.addWidget(self.ua_input)

        webhook_lbl = QLabel("Notification Webhook URL (Optional Alert Sink):")
        webhook_lbl.setStyleSheet("color: #a0a6b5;")
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("https://discord.com/api/webhooks/... or HTTPS endpoint")
        c2_layout.addWidget(webhook_lbl)
        c2_layout.addWidget(self.webhook_input)

        layout.addWidget(card2)

        # Save Feedback
        btn_box = QHBoxLayout()
        self.save_btn = QPushButton("APPLY CONFIGURATION")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_settings)

        self.save_feedback = QLabel("")
        self.save_feedback.setStyleSheet("color: #00e676; font-weight: 500;")

        btn_box.addWidget(self.save_btn)
        btn_box.addWidget(self.save_feedback)
        btn_box.addStretch()

        layout.addLayout(btn_box)
        layout.addStretch()

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Results Folder", self.dir_input.text())
        if folder:
            self.dir_input.setText(folder)

    def _save_settings(self):
        self.save_feedback.setText("Configuration successfully saved.")

    def get_results_dir(self) -> Path:
        return Path(self.dir_input.text().strip())
