"""
Results Telemetry View
Interactive results grid with category filters, keyword search, and export shortcuts.
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from nexus.ui.components.results_table import ResultsTable


class ResultsView(QWidget):
    """Full-page view dedicated to results inspection and search."""

    export_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title & Actions
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        view_title = QLabel("RESULTS TELEMETRY")
        view_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        view_title.setStyleSheet("color: #ffffff;")

        view_desc = QLabel("Real-time data grid of verified accounts, game counts, and network latency")
        view_desc.setStyleSheet("color: #7b8294; font-size: 12px;")

        title_box.addWidget(view_title)
        title_box.addWidget(view_desc)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.export_btn = QPushButton("Export Results")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_requested.emit)

        self.clear_btn = QPushButton("Clear Grid")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._handle_clear)

        header_layout.addWidget(self.export_btn)
        header_layout.addWidget(self.clear_btn)
        layout.addLayout(header_layout)

        # Search & Category Filter Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search accounts, details, or games...")
        self.search_input.textChanged.connect(self._apply_filters)

        self.category_filter = QComboBox()
        self.category_filter.addItems(["All Categorizations", "HITs Only", "Free Tier Only", "Invalid Only"])
        self.category_filter.currentIndexChanged.connect(self._apply_filters)
        self.category_filter.setFixedWidth(180)

        toolbar.addWidget(self.search_input)
        toolbar.addWidget(self.category_filter)
        layout.addLayout(toolbar)

        # Main Table Grid
        self.table = ResultsTable()
        layout.addWidget(self.table)

    def add_result(self, item: Dict[str, Any]):
        self.table.add_result(item)
        self._apply_filters()

    def _handle_clear(self):
        self.table.clear_results()
        self.clear_requested.emit()

    def _apply_filters(self):
        query = self.search_input.text().lower().strip()
        cat_idx = self.category_filter.currentIndex()

        for row in range(self.table.rowCount()):
            account_item = self.table.item(row, 1)
            status_item = self.table.item(row, 2)
            details_item = self.table.item(row, 3)

            account_text = account_item.text().lower() if account_item else ""
            status_text = status_item.text().upper() if status_item else ""
            details_text = details_item.text().lower() if details_item else ""

            # Match search query
            matches_search = (not query) or (query in account_text or query in details_text)

            # Match category filter
            matches_cat = True
            if cat_idx == 1:  # HITs Only
                matches_cat = "HIT" in status_text
            elif cat_idx == 2:  # Free Tier Only
                matches_cat = "FREE" in status_text
            elif cat_idx == 3:  # Invalid Only
                matches_cat = "INVALID" in status_text

            self.table.setRowHidden(row, not (matches_search and matches_cat))
