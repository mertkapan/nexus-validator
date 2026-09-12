"""
Real-Time Telemetry Results Grid
Custom QTableWidget featuring status tags, latency indicators, and row inspection triggers.
"""

from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QAction, QFont
import webbrowser

from nexus.config import COLOR_HIT, COLOR_FREE, COLOR_INVALID, COLOR_2FA, COLOR_TEXT_PRIMARY
from nexus.ui.components.library_modal import LibraryInspectionModal


class ResultsTable(QTableWidget):
    """High-throughput data grid for displaying live validation records."""
    
    inspect_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items_data: List[Dict[str, Any]] = []

        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "#", "Account", "Status", "Details", "Games", "Country", "Ping (ms)"
        ])

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        self.setColumnWidth(1, 190)
        self.setColumnWidth(5, 110)

        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)
        header.setFixedHeight(36)
        self.setShowGrid(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._handle_double_click)

    def add_result(self, item: Dict[str, Any], max_ui_rows: int = 5000):
        """
        Appends a new verified item to the table.
        Maintains a rolling window of recent entries (up to max_ui_rows) to prevent PyQt6 GUI memory freeze
        when processing 900k+ account batches, while 100% of hits are persisted to disk in real-time.
        """
        # If UI table reaches max display limit, drop the oldest row
        if self.rowCount() >= max_ui_rows:
            self.removeRow(0)
            if self.items_data:
                self.items_data.pop(0)

        row = self.rowCount()
        self.insertRow(row)
        self.items_data.append(item)

        idx_item = QTableWidgetItem(str(row + 1))
        idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        account_item = QTableWidgetItem(item.get("account", ""))
        
        status = item.get("status", "")
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        details_text = item.get("details", "")
        wallet_val = item.get("wallet", "")
        if wallet_val and "Wallet:" not in details_text:
            details_text = f"{details_text} | 💰 {wallet_val}"

        details_item = QTableWidgetItem(details_text)
        details_item.setToolTip(details_text)
        
        total_g = item.get("total_games", 0)
        paid_g = item.get("paid_games", 0)
        games_display = f"{total_g} ({paid_g} Paid)" if paid_g > 0 else str(total_g)
        games_item = QTableWidgetItem(games_display)
        games_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Build full hover tooltip of games
        games_list = item.get("games", [])
        if games_list:
            clean_names = [g.get("name") for g in games_list if g.get("name")]
            preview_tooltip = "Owned Games:\n" + "\n".join([f"• {n}" for n in clean_names[:40]])
            if len(clean_names) > 40:
                preview_tooltip += f"\n... and {len(clean_names) - 40} more"
            games_item.setToolTip(preview_tooltip)

        country_str = item.get("country", "🌐 Global")
        loc_str = item.get("location", "")
        if loc_str:
            country_str = f"{country_str} ({loc_str})"
        country_item = QTableWidgetItem(country_str)
        country_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        ping_val = item.get("ping_ms", 0)
        ping_str = f"{ping_val} ms" if ping_val > 0 else "--"
        ping_item = QTableWidgetItem(ping_str)
        ping_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # High-contrast foreground styling
        color_text = QColor(COLOR_TEXT_PRIMARY)
        idx_item.setForeground(QColor("#7e889e"))
        account_item.setForeground(color_text)
        details_item.setForeground(color_text)
        games_item.setForeground(QColor("#00e676") if paid_g > 0 else (QColor("#00b0ff") if total_g > 0 else QColor("#7e889e")))
        country_item.setForeground(color_text)

        if ping_val > 0:
            ping_color = QColor("#00e676") if ping_val < 200 else (QColor("#ffab00") if ping_val < 500 else QColor("#ff5252"))
        else:
            ping_color = QColor("#7e889e")
        ping_item.setForeground(ping_color)

        status_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        status_item.setFont(status_font)

        if status == "HIT":
            status_item.setForeground(QColor(COLOR_HIT))
            status_item.setBackground(QColor(0, 230, 118, 28))
        elif status == "2FA_HIT":
            status_item.setForeground(QColor(COLOR_2FA))
            status_item.setBackground(QColor(255, 171, 0, 28))
        elif status == "FREE":
            status_item.setForeground(QColor(COLOR_FREE))
            status_item.setBackground(QColor(0, 176, 255, 24))
        elif status == "RATE_LIMIT":
            status_item.setForeground(QColor("#ff9100"))
            status_item.setBackground(QColor(255, 145, 0, 24))
        else:
            status_item.setForeground(QColor(COLOR_INVALID))
            status_item.setBackground(QColor(255, 82, 82, 22))

        if paid_g > 0:
            games_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            games_item.setFont(games_font)
            games_item.setBackground(QColor(0, 230, 118, 16))

        for col_item in (idx_item, account_item, status_item, details_item, games_item, country_item, ping_item):
            col_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

        self.setItem(row, 0, idx_item)
        self.setItem(row, 1, account_item)
        self.setItem(row, 2, status_item)
        self.setItem(row, 3, details_item)
        self.setItem(row, 4, games_item)
        self.setItem(row, 5, country_item)
        self.setItem(row, 6, ping_item)

    def clear_results(self):
        self.setRowCount(0)
        self.items_data.clear()

    def _handle_double_click(self, row: int, column: int):
        if 0 <= row < len(self.items_data):
            self._inspect_item(self.items_data[row])

    def _inspect_item(self, item_data: Dict[str, Any]):
        dialog = LibraryInspectionModal(item_data, self)
        dialog.exec()

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        row = item.row()
        if not (0 <= row < len(self.items_data)):
            return

        item_data = self.items_data[row]
        menu = QMenu(self)

        inspect_act = QAction("Inspect Game Library", self)
        inspect_act.triggered.connect(lambda: self._inspect_item(item_data))
        menu.addAction(inspect_act)

        menu.addSeparator()

        copy_acc_act = QAction("Copy Credential Tuple (user:pass)", self)
        copy_acc_act.triggered.connect(lambda: QApplication.clipboard().setText(item_data.get("account", "")))
        menu.addAction(copy_acc_act)

        copy_user_act = QAction("Copy Username", self)
        copy_user_act.triggered.connect(lambda: QApplication.clipboard().setText(item_data.get("username", "")))
        menu.addAction(copy_user_act)

        copy_pass_act = QAction("Copy Password", self)
        copy_pass_act.triggered.connect(lambda: QApplication.clipboard().setText(item_data.get("password", "")))
        menu.addAction(copy_pass_act)

        if item_data.get("steamid"):
            menu.addSeparator()
            open_prof_act = QAction("Open Community Profile", self)
            open_prof_act.triggered.connect(lambda: webbrowser.open(f"https://steamcommunity.com/profiles/{item_data.get('steamid')}"))
            menu.addAction(open_prof_act)

        menu.exec(self.viewport().mapToGlobal(pos))
