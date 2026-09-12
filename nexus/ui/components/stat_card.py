"""
Metric Telemetry Card Component
Displays real-time numeric counters with color-coded accent indicators.
"""

from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class StatCard(QFrame):
    """Card widget rendering a key performance indicator (KPI) with high-end glassmorphic finish."""

    def __init__(self, title: str, initial_value: str = "0", accent_color: str = "#ff1e38", parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.accent_color = accent_color

        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141826, stop:1 #0e111a);
                border: 1px solid #1c2336;
                border-top: 2px solid {self.accent_color};
                border-radius: 8px;
            }}
            QFrame#StatCard:hover {{
                border: 1px solid #28344f;
                border-top: 2px solid {self.accent_color};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #181d2e, stop:1 #111420);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Title Label
        self.title_label = QLabel(title.upper())
        title_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #7b849b; letter-spacing: 0.5px;")

        # Big Value Counter
        self.value_label = QLabel(str(initial_value))
        value_font = QFont("Segoe UI", 21, QFont.Weight.Bold)
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet(f"color: {self.accent_color}; letter-spacing: -0.5px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))

    def set_title(self, title: str):
        self.title_label.setText(title.upper())
