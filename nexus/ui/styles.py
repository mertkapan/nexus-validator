"""
NEXUS v1.0.0 High-End Cyber Design System
Obsidian matte dark backdrop (#0c0e15) paired with neon crimson red (#ff1e38) glassmorphic accents.
"""

from nexus.config import (
    COLOR_BG_DARK,
    COLOR_BG_CARD,
    COLOR_BORDER,
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
)

MAIN_STYLESHEET = f"""
/* Global Root & Typography */
QMainWindow, QWidget {{
    background-color: #0b0d14;
    color: {COLOR_TEXT_PRIMARY};
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: #ffffff;
}}

/* Cyber Cards & Container Panels with Subtle Glowing Top Border */
QFrame#CyberCard, QFrame#CardPanel {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #131724, stop:1 #0f121c);
    border: 1px solid #1c2338;
    border-top: 2px solid rgba(255, 30, 56, 0.65);
    border-radius: 8px;
}}

QFrame#CyberCard:hover, QFrame#CardPanel:hover {{
    border: 1px solid #283452;
    border-top: 2px solid #ff1e38;
}}

/* Sidebar Navigation */
QFrame#SidebarPanel {{
    background-color: #0b0d14;
    border-right: 1px solid #181d2e;
}}

QPushButton#SidebarTab {{
    background-color: transparent;
    color: #8c93a8;
    text-align: left;
    padding: 13px 20px;
    font-size: 13px;
    font-weight: 600;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
}}

QPushButton#SidebarTab:hover {{
    background-color: #151926;
    color: #ffffff;
}}

QPushButton#SidebarTab:checked {{
    background-color: #191f2e;
    color: #ffffff;
    font-weight: 700;
    border-left: 3px solid {COLOR_ACCENT};
}}

/* Bottom Status Box in Sidebar */
QFrame#SidebarStatusCard {{
    background-color: #121622;
    border: 1px solid #1f2638;
    border-radius: 8px;
    margin: 0px 14px;
    padding: 6px;
}}

/* Badges */
QLabel#ModeBadge {{
    background-color: rgba(0, 176, 255, 0.12);
    color: #00b0ff;
    border: 1px solid rgba(0, 176, 255, 0.3);
    border-radius: 12px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QLabel#AccountBadge {{
    background-color: rgba(255, 82, 82, 0.12);
    color: #ff5252;
    border: 1px solid rgba(255, 82, 82, 0.25);
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}

/* Standard Buttons */
QPushButton {{
    background-color: #181d2a;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #262d40;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 12px;
}}

QPushButton:hover {{
    background-color: #21283a;
    border-color: #3b4663;
    color: #ffffff;
}}

QPushButton:pressed {{
    background-color: #131722;
}}

QPushButton:disabled {{
    background-color: #11141d;
    color: #4a5163;
    border-color: #1a1f2b;
}}

/* Primary Neon Crimson Action Button (START ENGINE) */
QPushButton#PrimaryActionButton, QPushButton#PrimaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff2b44, stop:1 #d9122a);
    color: #ffffff;
    border: 1px solid #ff475e;
    border-bottom: 2px solid #b30e23;
    border-radius: 6px;
    padding: 10px 24px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.5px;
}}

QPushButton#PrimaryActionButton:hover, QPushButton#PrimaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff4258, stop:1 #e61730);
    border-color: #ff667a;
}}

QPushButton#PrimaryActionButton:pressed, QPushButton#PrimaryButton:pressed {{
    background: #b30e23;
    border-bottom: 1px solid #ff475e;
}}

/* Warning Action Button (PAUSE) */
QPushButton#WarningActionButton, QPushButton#WarningButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2e2213, stop:1 #1e160a);
    color: #ffb300;
    border: 1px solid #ffb300;
    border-radius: 6px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
}}

QPushButton#WarningActionButton:hover, QPushButton#WarningButton:hover {{
    background: #3d2d18;
    color: #ffca28;
}}

/* Danger Action Button (STOP) */
QPushButton#DangerActionButton, QPushButton#DangerButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2b1318, stop:1 #1c0b0e);
    color: #ff5252;
    border: 1px solid #ff5252;
    border-radius: 6px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
}}

QPushButton#DangerActionButton:hover, QPushButton#DangerButton:hover {{
    background: #3d1a21;
    color: #ff7575;
}}

/* Export Button */
QPushButton#ExportActionButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a2333, stop:1 #131924);
    color: #e2e8f0;
    border: 1px solid #33415c;
    border-radius: 6px;
    padding: 9px 20px;
    font-weight: 600;
    font-size: 12px;
}}

QPushButton#ExportActionButton:hover {{
    background: #232f45;
    border-color: #485c82;
}}

/* Emerald Cyber Add Button (Add Custom Proxies) */
QPushButton#AddProxyButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00e676, stop:1 #00ab55);
    color: #0b0d14;
    border: 1px solid #33ff99;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 12px;
}}

QPushButton#AddProxyButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #33ff99, stop:1 #00cc66);
    border-color: #66ffb3;
    color: #000000;
}}

QPushButton#AddProxyButton:pressed {{
    background: #008f44;
}}

/* Inputs & Editors */
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: #0d1017;
    color: #f1f5f9;
    border: 1px solid #1e2536;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 12px;
    selection-background-color: {COLOR_ACCENT};
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {COLOR_ACCENT};
    background-color: #10141d;
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT};
    background-color: #10141d;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid #1e2536;
}}

/* Tables */
QTableWidget {{
    background-color: #10131d;
    alternate-background-color: #131724;
    border: 1px solid #1c2338;
    border-radius: 8px;
    gridline-color: #161b29;
    color: #f1f5f9;
    font-size: 12px;
    selection-background-color: #242c3d;
    selection-color: #ffffff;
}}

QTableWidget::item {{
    color: #f1f5f9;
    padding: 8px 10px;
    border-bottom: 1px solid #161a27;
}}

QTableWidget::item:selected {{
    background-color: #22293d;
    color: #ffffff;
}}

QTableWidget::item:hover {{
    background-color: #1b2234;
}}

QHeaderView::section {{
    background-color: #0c0e15;
    color: #838ca3;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    border: none;
    border-bottom: 1px solid #1e2536;
    padding: 9px 12px;
}}

/* Progress Bar */
QProgressBar {{
    background-color: #0d1017;
    border: 1px solid #1c2230;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-weight: 600;
    font-size: 10px;
    height: 12px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff1e38, stop:1 #ff5266);
    border-radius: 3px;
}}

/* Minimalist ScrollBars */
QScrollBar:vertical {{
    background-color: #0b0d14;
    width: 7px;
    margin: 0px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical {{
    background-color: #242c3d;
    min-height: 25px;
    border-radius: 3px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLOR_ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
