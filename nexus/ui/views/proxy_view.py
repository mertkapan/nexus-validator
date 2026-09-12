"""
Network Relay Viability Probe View
Manages proxy lists, automated web scraping, protocol detection, custom proxy pasting,
concurrent latency benchmarking, and auto-persistence across sessions.
"""

import os
import time
import asyncio
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QFrame,
    QProgressBar, QApplication, QDialog, QPlainTextEdit, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from nexus.config import COLOR_ACCENT, COLOR_HIT, COLOR_INVALID, COLOR_BG_DARK, COLOR_BG_CARD, PROXIES_FILE
from nexus.core.proxy_pool import NetworkRelayPool, NetworkRelay, probe_relay_viability
from nexus.core.proxy_scraper import scrape_fresh_proxies, filter_operational_proxies


class RelayTesterThread(QThread):
    """Asynchronous background worker probing proxy viability."""
    relay_tested = pyqtSignal(int, dict)
    finished_testing = pyqtSignal()

    def __init__(self, relays: List[NetworkRelay], parent=None):
        super().__init__(parent)
        self.relays = relays
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_probes())
        finally:
            loop.close()
            self.finished_testing.emit()

    async def _run_probes(self):
        sem = asyncio.Semaphore(35)

        async def _probe_worker(idx: int, relay: NetworkRelay):
            if self._is_cancelled:
                return
            async with sem:
                res = await probe_relay_viability(relay)
                self.relay_tested.emit(idx, res)

        tasks = [_probe_worker(i, r) for i, r in enumerate(self.relays)]
        await asyncio.gather(*tasks, return_exceptions=True)


class RelayScraperThread(QThread):
    """Asynchronous worker scraping and testing fresh public proxies."""
    status_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int, int)
    scraping_completed = pyqtSignal(list)

    def __init__(self, schemes: List[str] = None, test_proxies: bool = True, parent=None):
        super().__init__(parent)
        self.schemes = schemes or ["http", "socks4", "socks5"]
        self.test_proxies = test_proxies

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_scraper())
        finally:
            loop.close()

    async def _run_scraper(self):
        self.status_updated.emit("Fetching fresh proxies from live sources...")
        raw_relays = await scrape_fresh_proxies(schemes=self.schemes)
        self.status_updated.emit(f"Scraped {len(raw_relays)} unique nodes. Verifying viability...")

        if not self.test_proxies:
            self.scraping_completed.emit(raw_relays)
            return

        def _on_progress(tested, total, working):
            self.progress_updated.emit(tested, total, working)

        tested_relays = await filter_operational_proxies(
            raw_relays,
            target_url="https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/",
            concurrency=50,
            timeout_sec=4,
            progress_callback=_on_progress,
            save_to_file=True
        )

        self.status_updated.emit(f"Viability testing finished: {len(tested_relays)} operational relays identified.")
        self.scraping_completed.emit(tested_relays)


class AddCustomProxiesDialog(QDialog):
    """Interactive modal for pasting, parsing, benchmarking, and persisting user proxies."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Proxies / Network Relays")
        self.setMinimumSize(580, 460)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
            }}
        """)

        self.added_relays: List[NetworkRelay] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Title
        t_box = QVBoxLayout()
        t_box.setSpacing(2)
        title = QLabel("Add Custom Proxies")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        sub = QLabel("Paste proxies below (one per line). Format: ip:port, http://ip:port, socks5://user:pass@ip:port")
        sub.setStyleSheet("color: #7b849b; font-size: 11px;")
        t_box.addWidget(title)
        t_box.addWidget(sub)
        layout.addLayout(t_box)

        # Text Area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("127.0.0.1:8080\nhttp://user:pass@192.168.1.50:3128\nsocks5://10.0.0.1:1080")
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0d1017;
                color: #00e676;
                font-family: Consolas, monospace;
                font-size: 12px;
                border: 1px solid #1e2536;
                border-radius: 6px;
                padding: 10px;
            }
            QPlainTextEdit:focus {
                border-color: #ff1e38;
            }
        """)
        layout.addWidget(self.text_edit)

        # Controls Row (Default Scheme + Audit Checkbox)
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(12)

        s_lbl = QLabel("Default Protocol:")
        s_lbl.setStyleSheet("color: #8b92a4; font-size: 11px;")
        self.scheme_combo = QComboBox()
        self.scheme_combo.addItems(["http", "socks5", "socks4"])
        self.scheme_combo.setFixedWidth(100)

        self.test_checkbox = QCheckBox("Benchmark against Steam endpoints before saving")
        self.test_checkbox.setChecked(True)
        self.test_checkbox.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 500;")

        ctrl_row.addWidget(s_lbl)
        ctrl_row.addWidget(self.scheme_combo)
        ctrl_row.addWidget(self.test_checkbox)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Progress Label
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #00b0ff; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.status_lbl)

        # Actions Row
        act_row = QHBoxLayout()
        act_row.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        self.add_btn = QPushButton("💾 Add & Save to Pool")
        self.add_btn.setObjectName("PrimaryButton")
        self.add_btn.clicked.connect(self._process_proxies)

        act_row.addStretch()
        act_row.addWidget(cancel_btn)
        act_row.addWidget(self.add_btn)
        layout.addLayout(act_row)

    def _process_proxies(self):
        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Empty Input", "Please enter at least one proxy line.")
            return

        lines = [l.strip() for l in raw_text.splitlines() if l.strip() and not l.strip().startswith("#")]
        default_scheme = self.scheme_combo.currentText().lower()

        parsed: List[NetworkRelay] = []
        for line in lines:
            try:
                r = NetworkRelay(line, default_scheme=default_scheme)
                parsed.append(r)
            except Exception:
                continue

        if not parsed:
            QMessageBox.warning(self, "Invalid Format", "No valid proxy formats could be recognized.")
            return

        if not self.test_checkbox.isChecked():
            self.added_relays = parsed
            self.accept()
            return

        # Run asynchronous viability audit
        self.add_btn.setEnabled(False)
        self.status_lbl.setText(f"Benchmarking {len(parsed)} proxies against Steam API...")
        QApplication.processEvents()

        # Run test in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            working = loop.run_until_complete(
                filter_operational_proxies(
                    parsed,
                    target_url="https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/",
                    concurrency=30,
                    timeout_sec=4,
                    save_to_file=False
                )
            )
            self.added_relays = working
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Benchmark Error", f"Failed during proxy testing: {e}")
        finally:
            loop.close()


class ProxyView(QWidget):
    """Dedicated management page for network relay nodes with permanent persistence."""

    relays_updated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.relay_pool = NetworkRelayPool()
        self.tester_thread = None
        self.scraper_thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header Title
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        view_title = QLabel("NETWORK RELAY VIABILITY PROBES")
        view_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        view_title.setStyleSheet("color: #ffffff;")

        view_desc = QLabel("Automated proxy scraper, custom proxy injection, latency benchmarking, and auto-persistence")
        view_desc.setStyleSheet("color: #7b8294; font-size: 12px;")

        title_box.addWidget(view_title)
        title_box.addWidget(view_desc)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Stats labels
        self.stats_lbl = QLabel("Pool: 0 Nodes | Active: 0")
        self.stats_lbl.setStyleSheet("color: #a0a6b5; font-weight: 500;")
        header_layout.addWidget(self.stats_lbl)

        layout.addLayout(header_layout)

        # Controls Bar
        controls_card = QFrame()
        controls_card.setObjectName("CardPanel")
        controls_layout = QHBoxLayout(controls_card)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(10)

        # Add Custom Proxies Button (Emerald Cyber)
        self.add_custom_btn = QPushButton("➕ Add Custom Proxies")
        self.add_custom_btn.setObjectName("AddProxyButton")
        self.add_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_custom_btn.clicked.connect(self._open_add_custom_dialog)

        proto_lbl = QLabel("Protocol:")
        proto_lbl.setStyleSheet("color: #8b92a4;")
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["ALL", "HTTP", "SOCKS5", "SOCKS4"])

        self.scrape_btn = QPushButton("⚡ Scrape Fresh Proxies")
        self.scrape_btn.setObjectName("PrimaryButton")
        self.scrape_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scrape_btn.clicked.connect(self._start_scrape)

        load_file_btn = QPushButton("📂 Import File")
        load_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_file_btn.clicked.connect(self._import_file)

        self.paste_clip_btn = QPushButton("📋 Paste")
        self.paste_clip_btn.setToolTip("Quickly import proxies from clipboard")
        self.paste_clip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_clip_btn.clicked.connect(self._paste_from_clipboard)

        self.test_btn = QPushButton("Probe All")
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.clicked.connect(self._start_probe)

        self.prune_btn = QPushButton("🧹 Prune Dead")
        self.prune_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prune_btn.setToolTip("Removes unreachable proxies and saves working nodes to disk")
        self.prune_btn.clicked.connect(self._prune_dead_nodes)

        self.save_btn = QPushButton("💾 Save to Disk")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_pool_to_disk)

        controls_layout.addWidget(self.add_custom_btn)
        controls_layout.addWidget(proto_lbl)
        controls_layout.addWidget(self.proto_combo)
        controls_layout.addWidget(self.scrape_btn)
        controls_layout.addWidget(load_file_btn)
        controls_layout.addWidget(self.paste_clip_btn)
        controls_layout.addWidget(self.test_btn)
        controls_layout.addWidget(self.prune_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(self.save_btn)

        layout.addWidget(controls_card)

        # Progress Bar and Status Label for scraping / probing
        self.progress_panel = QFrame()
        self.progress_panel.setVisible(False)
        p_layout = QVBoxLayout(self.progress_panel)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(4)

        self.progress_status_lbl = QLabel("Ready")
        self.progress_status_lbl.setStyleSheet("color: #00e676; font-weight: 500; font-size: 11px;")
        self.probe_bar = QProgressBar()
        p_layout.addWidget(self.progress_status_lbl)
        p_layout.addWidget(self.probe_bar)

        layout.addWidget(self.progress_panel)

        # Relay Table Grid
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "Relay Endpoint", "Protocol", "Latency (ms)", "Viability Status"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # Auto-load saved proxies from disk if present
        self._auto_load_default_proxies()

    def _auto_load_default_proxies(self):
        if os.path.exists(PROXIES_FILE):
            try:
                with open(PROXIES_FILE, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                if lines:
                    self.relay_pool.load_from_lines(lines, default_scheme="http")
                    self._populate_table()
                    self.relays_updated.emit(self.relay_pool)
            except Exception:
                pass

    def save_pool_to_disk(self) -> bool:
        """Persists current operational proxy pool to disk so it is never lost on exit."""
        try:
            with open(PROXIES_FILE, "w", encoding="utf-8") as f:
                for r in self.relay_pool.relays:
                    f.write(f"{r.url}\n")
            return True
        except Exception:
            return False

    def _save_pool_to_disk(self):
        if self.save_pool_to_disk():
            QMessageBox.information(
                self,
                "Saved Successfully",
                f"Saved {self.relay_pool.total} proxies to {PROXIES_FILE}.\nYour proxy pool is permanently stored!"
            )
        else:
            QMessageBox.critical(self, "Error", "Failed to save proxies to disk.")

    def _prune_dead_nodes(self):
        alive_relays = [r for r in self.relay_pool.relays if r.is_alive and r.ping_ms >= 0]
        pruned_count = len(self.relay_pool.relays) - len(alive_relays)
        self.relay_pool.relays = alive_relays
        self.relay_pool._index = 0
        self.save_pool_to_disk()
        self._populate_table()
        self.relays_updated.emit(self.relay_pool)
        QMessageBox.information(
            self,
            "Prune Completed",
            f"Removed {pruned_count} unreachable nodes.\nActive pool of {len(alive_relays)} working proxies saved to disk."
        )

    def _open_add_custom_dialog(self):
        dlg = AddCustomProxiesDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.added_relays:
            # Merge with existing relays (deduplicating by host:port)
            existing_keys = {f"{r.host}:{r.port}" for r in self.relay_pool.relays}
            new_count = 0
            for nr in dlg.added_relays:
                k = f"{nr.host}:{nr.port}"
                if k not in existing_keys:
                    self.relay_pool.relays.insert(0, nr) # Add to top of pool
                    existing_keys.add(k)
                    new_count += 1

            self.save_pool_to_disk()
            self._populate_table()
            self.relays_updated.emit(self.relay_pool)
            QMessageBox.information(
                self,
                "Proxies Added",
                f"Successfully added {new_count} custom verified proxies to pool.\nSaved to {PROXIES_FILE}!"
            )

    def _start_scrape(self):
        self.scrape_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.progress_panel.setVisible(True)
        self.probe_bar.setMaximum(0)
        self.probe_bar.setValue(0)
        self.progress_status_lbl.setText("Connecting to live open-source proxy repositories...")

        proto_sel = self.proto_combo.currentText().lower()
        schemes = ["http", "socks4", "socks5"] if proto_sel == "all" else [proto_sel]

        self.scraper_thread = RelayScraperThread(schemes=schemes, test_proxies=True, parent=self)
        self.scraper_thread.status_updated.connect(self._handle_scraper_status)
        self.scraper_thread.progress_updated.connect(self._handle_scraper_progress)
        self.scraper_thread.scraping_completed.connect(self._handle_scraper_completed)
        self.scraper_thread.start()

    def _handle_scraper_status(self, msg: str):
        self.progress_status_lbl.setText(msg)

    def _handle_scraper_progress(self, tested: int, total: int, working: int):
        self.probe_bar.setMaximum(total)
        self.probe_bar.setValue(tested)
        self.progress_status_lbl.setText(f"Auditing viability: {tested}/{total} probed | {working} operational")

    def _handle_scraper_completed(self, fresh_relays: List[NetworkRelay]):
        # Merge fresh relays into existing pool
        existing_keys = {f"{r.host}:{r.port}" for r in self.relay_pool.relays}
        for fr in fresh_relays:
            k = f"{fr.host}:{fr.port}"
            if k not in existing_keys:
                self.relay_pool.relays.append(fr)
                existing_keys.add(k)

        self.save_pool_to_disk()
        self._populate_table()
        self.progress_panel.setVisible(False)
        self.scrape_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
        self.relays_updated.emit(self.relay_pool)

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Proxies List File", "", "Text Files (*.txt);;All Files (*)")
        if not path:
            return

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        proto = self.proto_combo.currentText().lower()
        scheme = "http" if proto == "all" else proto

        existing_keys = {f"{r.host}:{r.port}" for r in self.relay_pool.relays}
        added = 0
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    r = NetworkRelay(line, default_scheme=scheme)
                    k = f"{r.host}:{r.port}"
                    if k not in existing_keys:
                        self.relay_pool.relays.append(r)
                        existing_keys.add(k)
                        added += 1
                except Exception:
                    continue

        self.save_pool_to_disk()
        self._populate_table()
        self.relays_updated.emit(self.relay_pool)
        QMessageBox.information(self, "Import Complete", f"Imported {added} proxies and saved to {PROXIES_FILE}!")

    def _paste_from_clipboard(self):
        text = QApplication.clipboard().text().strip()
        if not text:
            QMessageBox.warning(self, "Clipboard Empty", "Your clipboard contains no proxy text.")
            return

        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            QMessageBox.warning(self, "No Proxies Found", "No valid proxy lines found in clipboard.")
            return

        proto = self.proto_combo.currentText().lower()
        scheme = "http" if proto == "all" else proto

        existing_keys = {f"{r.host}:{r.port}" for r in self.relay_pool.relays}
        added = 0
        for line in lines:
            try:
                r = NetworkRelay(line, default_scheme=scheme)
                k = f"{r.host}:{r.port}"
                if k not in existing_keys:
                    self.relay_pool.relays.insert(0, r)
                    existing_keys.add(k)
                    added += 1
            except Exception:
                continue

        self.save_pool_to_disk()
        self._populate_table()
        self.relays_updated.emit(self.relay_pool)
        QMessageBox.information(
            self,
            "Clipboard Import Complete",
            f"Successfully imported {added} proxies from clipboard!\nActive pool saved to {PROXIES_FILE}."
        )

    def _populate_table(self):
        self.table.setRowCount(len(self.relay_pool.relays))
        for row, r in enumerate(self.relay_pool.relays):
            idx_item = QTableWidgetItem(str(row + 1))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            endpoint_item = QTableWidgetItem(r.display_str)
            proto_item = QTableWidgetItem(r.scheme.upper())
            proto_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            ping_str = f"{r.ping_ms} ms" if r.ping_ms > 0 else "--"
            ping_item = QTableWidgetItem(ping_str)
            ping_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            status_str = "Operational" if r.is_alive and r.ping_ms > 0 else ("Untested" if r.ping_ms < 0 else "Unreachable")
            status_item = QTableWidgetItem(status_str)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if status_str == "Operational":
                status_item.setForeground(QColor(COLOR_HIT))
            elif status_str == "Unreachable":
                status_item.setForeground(QColor(COLOR_INVALID))

            for col in (idx_item, endpoint_item, proto_item, ping_item, status_item):
                col.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self.table.setItem(row, 0, idx_item)
            self.table.setItem(row, 1, endpoint_item)
            self.table.setItem(row, 2, proto_item)
            self.table.setItem(row, 3, ping_item)
            self.table.setItem(row, 4, status_item)

        self._update_stats_label()

    def _start_probe(self):
        if not self.relay_pool.relays:
            return

        self.progress_panel.setVisible(True)
        self.probe_bar.setMaximum(len(self.relay_pool.relays))
        self.probe_bar.setValue(0)
        self.test_btn.setEnabled(False)

        self.tester_thread = RelayTesterThread(self.relay_pool.relays, self)
        self.tester_thread.relay_tested.connect(self._handle_probe_result)
        self.tester_thread.finished_testing.connect(self._handle_probe_finished)
        self.tester_thread.start()

    def _handle_probe_result(self, row: int, res: dict):
        if 0 <= row < self.table.rowCount():
            ping_val = res.get("ping", -1)
            ping_str = f"{ping_val} ms" if ping_val >= 0 else "--"
            self.table.setItem(row, 3, QTableWidgetItem(ping_str))

            status_str = "Operational" if res.get("success") else "Unreachable"
            status_item = QTableWidgetItem(status_str)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(QColor(COLOR_HIT if res.get("success") else COLOR_INVALID))
            self.table.setItem(row, 4, status_item)

        self.probe_bar.setValue(self.probe_bar.value() + 1)
        self._update_stats_label()

    def _handle_probe_finished(self):
        self.test_btn.setEnabled(True)
        self.progress_panel.setVisible(False)
        self.save_pool_to_disk()
        self._update_stats_label()
        self.relays_updated.emit(self.relay_pool)

    def _update_stats_label(self):
        total = self.relay_pool.total
        active = self.relay_pool.active_count
        cooling = self.relay_pool.cooling_count
        self.stats_lbl.setText(f"Pool: {total} Nodes | Active: {active} | Cooling: {cooling}")