"""
Unified Mission Control & Live Telemetry Dashboard
Hosts operational controls, real-time account parser badge, KPI cards, category filter pills, and live results data grid.
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QSpinBox, QFileDialog, QProgressBar, QFrame, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from nexus.config import (
    COLOR_ACCENT, COLOR_HIT, COLOR_FREE, COLOR_INVALID,
    DEFAULT_CONCURRENCY, DEFAULT_TIMEOUT_SEC, DEFAULT_MAX_RETRIES,
    load_user_config, save_user_config, DISCORD_WEBHOOK_URL
)
from nexus.utils.discord import send_discord_test_message
from nexus.ui.components.stat_card import StatCard
from nexus.ui.components.results_table import ResultsTable


class DashboardView(QWidget):
    """Unified primary dashboard combining controls and live results telemetry."""

    start_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    export_requested = pyqtSignal()
    quick_scrape_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded_accounts_count = 0
        self.current_category = "ALL"
        self.cat_counts = {
            "ALL": 0,
            "HIT": 0,
            "FREE": 0,
            "BANNED": 0,
            "INVALID": 0,
            "ERROR": 0
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        view_title = QLabel("MISSION CONTROL & LIVE TELEMETRY")
        view_title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
        view_title.setFont(view_title_font)
        view_title.setStyleSheet("color: #ffffff; letter-spacing: 0.5px;")

        view_desc = QLabel("Real-time Platform Authentication State Validator & Owned Game Telemetry Suite")
        view_desc.setStyleSheet("color: #7b849b; font-size: 12px;")

        title_box.addWidget(view_title)
        title_box.addWidget(view_desc)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Mode Tag (Direct / Proxy)
        self.mode_badge = QLabel("⚡ Direct Connection Mode")
        self.mode_badge.setObjectName("ModeBadge")
        header_layout.addWidget(self.mode_badge)

        layout.addLayout(header_layout)

        # 2. Controls Panel Card
        control_card = QFrame()
        control_card.setObjectName("CyberCard")
        control_layout = QVBoxLayout(control_card)
        control_layout.setContentsMargins(18, 16, 18, 16)
        control_layout.setSpacing(12)

        # Row A: Combos File Picker with Real-time Account Count Badge
        combo_header_row = QHBoxLayout()
        combo_lbl = QLabel("CREDENTIALS BATCH (username:password)")
        combo_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        combo_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; letter-spacing: 0.5px;")

        self.account_counter_badge = QLabel("0 Accounts Loaded")
        self.account_counter_badge.setObjectName("AccountBadge")
        
        combo_header_row.addWidget(combo_lbl)
        combo_header_row.addStretch()
        combo_header_row.addWidget(self.account_counter_badge)
        control_layout.addLayout(combo_header_row)

        combo_input_row = QHBoxLayout()
        combo_input_row.setSpacing(10)
        self.combo_input = QLineEdit()
        self.combo_input.setPlaceholderText("Select credential list file (.txt)...")
        self.combo_input.textChanged.connect(self._on_combo_path_changed)

        self.browse_combo_btn = QPushButton("📂 Browse File")
        self.browse_combo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_combo_btn.clicked.connect(self._browse_combos)

        combo_input_row.addWidget(self.combo_input)
        combo_input_row.addWidget(self.browse_combo_btn)
        control_layout.addLayout(combo_input_row)

        # Row: Discord Webhook Integration
        webhook_row = QHBoxLayout()
        webhook_row.setSpacing(10)

        webhook_lbl = QLabel("DISCORD WEBHOOK:")
        webhook_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        webhook_lbl.setStyleSheet("color: #5865f2; letter-spacing: 0.5px;")

        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("https://discord.com/api/webhooks/... (Instant hit telemetry alerts)")
        cfg = load_user_config()
        self.webhook_input.setText(cfg.get("webhook_url", ""))
        self.webhook_input.textChanged.connect(self._on_webhook_changed)

        self.test_webhook_btn = QPushButton("📡 Test Webhook")
        self.test_webhook_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_webhook_btn.clicked.connect(self._test_discord_webhook)

        webhook_row.addWidget(webhook_lbl)
        webhook_row.addWidget(self.webhook_input)
        webhook_row.addWidget(self.test_webhook_btn)
        control_layout.addLayout(webhook_row)

        # Row B: Parameters (Threads, Timeout, Retries) & Fast Scrape
        params_row = QHBoxLayout()
        params_row.setSpacing(14)

        # Workers
        w_box = QHBoxLayout()
        w_lbl = QLabel("Threads:")
        w_lbl.setStyleSheet("color: #9499aa; font-weight: 500;")
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 500)
        self.concurrency_spin.setValue(DEFAULT_CONCURRENCY)
        self.concurrency_spin.setFixedWidth(75)
        w_box.addWidget(w_lbl)
        w_box.addWidget(self.concurrency_spin)

        # Timeout
        t_box = QHBoxLayout()
        t_lbl = QLabel("Timeout (s):")
        t_lbl.setStyleSheet("color: #9499aa; font-weight: 500;")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(2, 60)
        self.timeout_spin.setValue(DEFAULT_TIMEOUT_SEC)
        self.timeout_spin.setFixedWidth(75)
        t_box.addWidget(t_lbl)
        t_box.addWidget(self.timeout_spin)

        # Retries
        r_box = QHBoxLayout()
        r_lbl = QLabel("Max Retries:")
        r_lbl.setStyleSheet("color: #9499aa; font-weight: 500;")
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(DEFAULT_MAX_RETRIES)
        self.retries_spin.setFixedWidth(70)
        r_box.addWidget(r_lbl)
        r_box.addWidget(self.retries_spin)

        # Quick Proxy Scrape Button
        self.quick_scrape_btn = QPushButton("⚡ Auto-Fetch Fresh Proxies")
        self.quick_scrape_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_scrape_btn.clicked.connect(self.quick_scrape_requested.emit)

        params_row.addLayout(w_box)
        params_row.addLayout(t_box)
        params_row.addLayout(r_box)
        params_row.addStretch()
        params_row.addWidget(self.quick_scrape_btn)
        control_layout.addLayout(params_row)

        # Row C: Primary Action Controls
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        self.start_btn = QPushButton("▶ START ENGINE")
        self.start_btn.setObjectName("PrimaryActionButton")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_requested.emit)

        self.pause_btn = QPushButton("⏸ PAUSE")
        self.pause_btn.setObjectName("WarningActionButton")
        self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_requested.emit)

        self.stop_btn = QPushButton("⏹ STOP")
        self.stop_btn.setObjectName("DangerActionButton")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        self.export_btn = QPushButton("💾 EXPORT HITS")
        self.export_btn.setObjectName("ExportActionButton")
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_requested.emit)

        actions_row.addWidget(self.start_btn)
        actions_row.addWidget(self.pause_btn)
        actions_row.addWidget(self.stop_btn)
        actions_row.addStretch()
        actions_row.addWidget(self.export_btn)
        control_layout.addLayout(actions_row)

        layout.addWidget(control_card)

        # 3. KPI Metric Cards
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_hits = StatCard("Verified Hits", "0", COLOR_HIT)
        self.card_free = StatCard("Free Tier", "0", COLOR_FREE)
        self.card_invalid = StatCard("Invalid", "0", COLOR_INVALID)
        self.card_cpm = StatCard("Speed (CPM)", "0", COLOR_ACCENT)
        self.card_progress = StatCard("Checked Batch", "0 / 0", "#ffffff")

        metrics_layout.addWidget(self.card_hits)
        metrics_layout.addWidget(self.card_free)
        metrics_layout.addWidget(self.card_invalid)
        metrics_layout.addWidget(self.card_cpm)
        metrics_layout.addWidget(self.card_progress)
        layout.addLayout(metrics_layout)

        # 4. Execution Progress Bar
        progress_card = QFrame()
        progress_card.setObjectName("CyberCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(14, 10, 14, 10)
        progress_layout.setSpacing(6)

        progress_header = QHBoxLayout()
        progress_title = QLabel("VALIDATION PROGRESS")
        progress_title.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        progress_title.setStyleSheet("color: #727b91;")

        self.progress_percentage = QLabel("0.0%")
        self.progress_percentage.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.progress_percentage.setStyleSheet(f"color: {COLOR_ACCENT};")

        progress_header.addWidget(progress_title)
        progress_header.addStretch()
        progress_header.addWidget(self.progress_percentage)
        progress_layout.addLayout(progress_header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(progress_card)

        # 5. Live Telemetry Filter Bar with Category Pills & Instant Search
        filter_bar_layout = QHBoxLayout()
        filter_bar_layout.setSpacing(8)

        tbl_title = QLabel("TELEMETRY:")
        tbl_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        tbl_title.setStyleSheet("color: #727b91; letter-spacing: 0.5px;")
        filter_bar_layout.addWidget(tbl_title)

        # Category Buttons
        self.btn_cat_all = self._build_category_btn("ALL (0)", "ALL")
        self.btn_cat_hit = self._build_category_btn("HITS (0)", "HIT")
        self.btn_cat_free = self._build_category_btn("FREE (0)", "FREE")
        self.btn_cat_ban = self._build_category_btn("BANNED (0)", "BANNED")
        self.btn_cat_inv = self._build_category_btn("INVALID (0)", "INVALID")
        self.btn_cat_err = self._build_category_btn("ERRORS (0)", "ERROR")

        self.category_buttons = {
            "ALL": self.btn_cat_all,
            "HIT": self.btn_cat_hit,
            "FREE": self.btn_cat_free,
            "BANNED": self.btn_cat_ban,
            "INVALID": self.btn_cat_inv,
            "ERROR": self.btn_cat_err,
        }

        for btn in self.category_buttons.values():
            filter_bar_layout.addWidget(btn)

        filter_bar_layout.addStretch()

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter by username, game title (e.g. Rust), or details...")
        self.search_input.setFixedWidth(280)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1017;
                color: #f1f5f9;
                border: 1px solid #1e2536;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #ff1e38;
            }
        """)
        self.search_input.textChanged.connect(self._apply_table_filters)
        filter_bar_layout.addWidget(self.search_input)

        layout.addLayout(filter_bar_layout)

        # 6. Embedded Results Table
        self.table = ResultsTable()
        layout.addWidget(self.table)

        # Set initial active category styling
        self._update_category_buttons_ui()

    def _build_category_btn(self, text: str, cat_key: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._select_category(cat_key))
        return btn

    def _select_category(self, cat_key: str):
        self.current_category = cat_key
        self._update_category_buttons_ui()
        self._apply_table_filters()

    def _update_category_buttons_ui(self):
        style_active = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff2b44, stop:1 #c90e24);
                color: #ffffff;
                border: 1px solid #ff5266;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
        """
        style_inactive = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #151928, stop:1 #0f121d);
                color: #8f9bb3;
                border: 1px solid #20273c;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1c2236;
                color: #f8fafc;
                border-color: #384568;
            }
        """
        for k, btn in self.category_buttons.items():
            btn.setStyleSheet(style_active if k == self.current_category else style_inactive)
            btn.setText(f"{k} ({self.cat_counts[k]})")

    def _browse_combos(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Credentials Batch File", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.combo_input.setText(file_path)

    def _on_combo_path_changed(self, path: str):
        path = path.strip().strip('"').strip("'")
        if not path or not os.path.exists(path):
            self.account_counter_badge.setText("0 Accounts Loaded")
            self.account_counter_badge.setStyleSheet("color: #ff5252; background-color: rgba(255, 82, 82, 0.12);")
            self._loaded_accounts_count = 0
            return

        try:
            # Fast line count using 1MB binary chunks (instantaneous even for 900k+ accounts)
            with open(path, "rb") as bf:
                line_count = sum(buf.count(b"\n") for buf in iter(lambda: bf.read(1024 * 1024), b""))

            if line_count == 0:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    line_count = 1 if f.read().strip() else 0

            self._loaded_accounts_count = line_count
            if line_count > 0:
                self.account_counter_badge.setText(f"✓ ~{line_count:,} Accounts Detected (Streaming Engine)")
                self.account_counter_badge.setStyleSheet("color: #00e676; background-color: rgba(0, 230, 118, 0.12);")
            else:
                self.account_counter_badge.setText("Empty File")
                self.account_counter_badge.setStyleSheet("color: #ff5252; background-color: rgba(255, 82, 82, 0.12);")
        except Exception:
            self.account_counter_badge.setText("File Read Error")
            self.account_counter_badge.setStyleSheet("color: #ff5252; background-color: rgba(255, 82, 82, 0.12);")
            self._loaded_accounts_count = 0

    def _on_webhook_changed(self, text: str):
        save_user_config({"webhook_url": text.strip()})

    def _test_discord_webhook(self):
        url = self.webhook_input.text().strip()
        if not url:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Webhook URL", "Please enter a Discord Webhook URL to test.")
            return

        self.test_webhook_btn.setEnabled(False)
        self.test_webhook_btn.setText("⏳ Testing...")

        import threading
        import asyncio
        def _run_test():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = False
            try:
                success = loop.run_until_complete(send_discord_test_message(url))
            except Exception:
                success = False
            finally:
                loop.close()

            from PyQt6.QtCore import QTimer
            def _finish():
                self.test_webhook_btn.setEnabled(True)
                self.test_webhook_btn.setText("📡 Test Webhook")
                from PyQt6.QtWidgets import QMessageBox
                if success:
                    QMessageBox.information(self, "Discord Connected", "✅ Test message successfully delivered to your Discord channel!")
                else:
                    QMessageBox.critical(self, "Connection Failed", "❌ Failed to dispatch webhook. Verify the URL is valid and accessible.")

            QTimer.singleShot(0, _finish)

        threading.Thread(target=_run_test, daemon=True).start()

    def update_proxy_mode(self, active_proxies: int):
        if active_proxies > 0:
            self.mode_badge.setText(f"🌐 Rotating Relay Pool ({active_proxies} Nodes)")
            self.mode_badge.setStyleSheet("color: #00e676; background-color: rgba(0, 230, 118, 0.12); border: 1px solid rgba(0, 230, 118, 0.3);")
        else:
            self.mode_badge.setText("⚡ Direct Connection Mode")
            self.mode_badge.setStyleSheet("color: #00b0ff; background-color: rgba(0, 176, 255, 0.12); border: 1px solid rgba(0, 176, 255, 0.3);")

    def get_settings(self) -> Dict[str, Any]:
        return {
            "combo_file": self.combo_input.text().strip().strip('"').strip("'"),
            "webhook_url": self.webhook_input.text().strip(),
            "concurrency": self.concurrency_spin.value(),
            "timeout": self.timeout_spin.value(),
            "retries": self.retries_spin.value(),
            "total_count": self._loaded_accounts_count,
        }

    def add_result(self, item: Dict[str, Any]):
        self.table.add_result(item)
        
        # Update category counts
        self.cat_counts["ALL"] += 1
        status = item.get("status", "")
        paid_games = item.get("paid_games", 0)
        details = item.get("details", "").lower()
        is_banned = item.get("vac_banned", False) or item.get("trade_banned", False) or "ban" in details

        if is_banned:
            self.cat_counts["BANNED"] += 1

        if status in ("HIT", "2FA_HIT"):
            self.cat_counts["HIT"] += 1
        elif status == "FREE":
            self.cat_counts["FREE"] += 1
        elif status == "INVALID":
            self.cat_counts["INVALID"] += 1
        elif status in ("ERROR", "TIMEOUT", "PROXY_ERROR", "RATE_LIMIT"):
            self.cat_counts["ERROR"] += 1

        # Check if the newly added row matches active filter category
        new_row_idx = self.table.rowCount() - 1
        if new_row_idx >= 0 and self.current_category != "ALL":
            matches = True
            if self.current_category == "HIT":
                matches = (status in ("HIT", "2FA_HIT"))
            elif self.current_category == "FREE":
                matches = (status == "FREE")
            elif self.current_category == "BANNED":
                matches = is_banned
            elif self.current_category == "INVALID":
                matches = (status == "INVALID")
            elif self.current_category == "ERROR":
                matches = (status in ("ERROR", "TIMEOUT", "PROXY_ERROR", "RATE_LIMIT"))
            self.table.setRowHidden(new_row_idx, not matches)

        # Real-time category button counters update
        self._update_category_buttons_ui()

    def update_metrics(self, stats: dict):
        self.card_hits.set_value(stats.get("hits", 0))
        self.card_free.set_value(stats.get("free", 0))
        self.card_invalid.set_value(stats.get("invalid", 0))
        self.card_cpm.set_value(f"{stats.get('cpm', 0):,}")
        
        checked = stats.get("checked", 0)
        total = stats.get("total", 0)
        self.card_progress.set_value(f"{checked:,} / {total:,}")

        if total > 0:
            pct = (checked / total) * 100
            self.progress_bar.setValue(int(pct))
            self.progress_percentage.setText(f"{pct:.1f}%")

    def set_engine_state(self, running: bool, paused: bool = False):
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.stop_btn.setEnabled(running)
        self.combo_input.setEnabled(not running)
        self.browse_combo_btn.setEnabled(not running)
        self.concurrency_spin.setEnabled(not running)
        self.timeout_spin.setEnabled(not running)
        self.retries_spin.setEnabled(not running)
        self.quick_scrape_btn.setEnabled(not running)

        if not running:
            self._update_category_buttons_ui()
            self._apply_table_filters()

        if paused:
            self.pause_btn.setText("▶ RESUME")
        else:
            self.pause_btn.setText("⏸ PAUSE")

    def _apply_table_filters(self):
        query = self.search_input.text().lower().strip()
        cat = self.current_category

        for row in range(self.table.rowCount()):
            item_data = self.table.items_data[row] if row < len(self.table.items_data) else {}

            account_text = item_data.get("account", "").lower()
            details_text = item_data.get("details", "").lower()
            persona_text = item_data.get("persona_name", "").lower()
            game_names = " ".join([g.get("name", "").lower() for g in item_data.get("games", [])])

            matches_search = (not query) or (
                query in account_text or query in details_text or query in persona_text or query in game_names
            )

            status = item_data.get("status", "")
            paid_games = item_data.get("paid_games", 0)
            is_banned = item_data.get("vac_banned", False) or item_data.get("trade_banned", False) or "ban" in details_text

            matches_cat = True
            if cat == "HIT":
                matches_cat = (status in ("HIT", "2FA_HIT"))
            elif cat == "FREE":
                matches_cat = (status == "FREE")
            elif cat == "BANNED":
                matches_cat = is_banned
            elif cat == "INVALID":
                matches_cat = (status == "INVALID")
            elif cat == "ERROR":
                matches_cat = (status in ("ERROR", "TIMEOUT", "PROXY_ERROR", "RATE_LIMIT"))

            self.table.setRowHidden(row, not (matches_search and matches_cat))