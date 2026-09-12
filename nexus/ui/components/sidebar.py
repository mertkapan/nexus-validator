"""
Streamlined Vertical Sidebar Navigation Component
Features NEXUS cyber branding, exactly 2 navigation tabs (Dashboard, Proxy),
and a glowing operational status indicator.
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPixmap
import os
from nexus.config import COLOR_ACCENT, COLOR_HIT, COLOR_WARN, COLOR_INVALID, ICON_PATH


class StatusDot(QFrame):
    """Custom painted pulsing/glowing circular status indicator."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(COLOR_HIT)

    def set_state(self, state: str):
        state_lower = state.lower()
        if "running" in state_lower or "ready" in state_lower or "completed" in state_lower:
            self._color = QColor(COLOR_HIT)
        elif "paused" in state_lower or "fetch" in state_lower:
            self._color = QColor(COLOR_WARN)
        elif "stop" in state_lower or "error" in state_lower:
            self._color = QColor(COLOR_INVALID)
        else:
            self._color = QColor("#888888")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # Outer glow
        glow_color = QColor(self._color)
        glow_color.setAlpha(60)
        painter.setBrush(QBrush(glow_color))
        painter.drawEllipse(0, 0, 12, 12)
        # Inner solid dot
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(2, 2, 8, 8)


class Sidebar(QFrame):
    """Sleek vertical 2-tab navigation sidebar."""
    tab_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarPanel")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 24, 0, 20)
        layout.setSpacing(6)

        # Brand Header with Cyber Styling
        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(22, 0, 22, 24)
        brand_layout.setSpacing(3)

        self.brand_title = QLabel("NEXUS")
        brand_font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        brand_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        self.brand_title.setFont(brand_font)
        self.brand_title.setStyleSheet(f"color: {COLOR_ACCENT};")

        self.brand_sub = QLabel("AUTHENTICATION SUITE")
        sub_font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
        sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        self.brand_sub.setFont(sub_font)
        self.brand_sub.setStyleSheet("color: #616a82;")

        brand_top = QHBoxLayout()
        brand_top.setSpacing(10)
        if os.path.exists(ICON_PATH):
            logo_lbl = QLabel()
            pix = QPixmap(str(ICON_PATH)).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(pix)
            brand_top.addWidget(logo_lbl)
        brand_top.addWidget(self.brand_title)
        brand_top.addStretch()

        brand_layout.addLayout(brand_top)
        brand_layout.addWidget(self.brand_sub)
        layout.addLayout(brand_layout)

        # 2 Primary Navigation Tabs
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        tabs_data = [
            ("⚡ Dashboard", 0),
            ("🌐 Proxy Management", 1),
        ]

        self.tab_buttons = []
        for label, idx in tabs_data:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("SidebarTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if idx == 0:
                btn.setChecked(True)

            self.button_group.addButton(btn, idx)
            layout.addWidget(btn)
            self.tab_buttons.append(btn)

        self.button_group.idClicked.connect(self.tab_changed.emit)

        # Spacer
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Bottom Status Card
        status_box = QFrame()
        status_box.setObjectName("SidebarStatusCard")
        status_layout = QHBoxLayout(status_box)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(10)

        self.status_dot = StatusDot()
        self.status_label = QLabel("Ready!")
        self.status_label.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.status_label.setStyleSheet("color: #e2e8f0;")

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        layout.addWidget(status_box)

    def set_status(self, text: str):
        self.status_label.setText(text)
        self.status_dot.set_state(text)
