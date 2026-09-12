"""
Library Inspection Modal Dialog
Renders an interactive high-tech cyber interface detailing extracted platform account telemetry,
VAC status, country info, and visual owned game cards with playtime and banners.
"""

import os
import urllib.request
from datetime import datetime
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QApplication, QScrollArea, QWidget, QGridLayout, QComboBox
)
from PyQt6.QtCore import Qt, QRunnable, QThreadPool, pyqtSignal, QObject, QRect
from PyQt6.QtGui import QFont, QPixmap, QPainter, QPainterPath, QColor, QLinearGradient
import webbrowser

from nexus.config import (
    COLOR_HIT, COLOR_FREE, COLOR_INVALID, COLOR_BG_DARK,
    CACHE_IMAGES_DIR, CACHE_AVATARS_DIR
)


class ImageDownloadSignals(QObject):
    loaded = pyqtSignal(str, str)  # key, file_path


class ImageDownloadTask(QRunnable):
    def __init__(self, key: str, urls: Any, dest_path: str, signals: ImageDownloadSignals):
        super().__init__()
        self.key = key
        self.urls = urls if isinstance(urls, list) else [urls]
        self.dest_path = dest_path
        self.signals = signals

    def run(self):
        try:
            if os.path.exists(self.dest_path) and os.path.getsize(self.dest_path) > 300:
                self.signals.loaded.emit(self.key, self.dest_path)
                return

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Referer": "https://store.steampowered.com/"
            }

            for url in self.urls:
                if not url:
                    continue
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        if resp.status == 200:
                            data = resp.read()
                            if len(data) > 300:
                                os.makedirs(os.path.dirname(self.dest_path), exist_ok=True)
                                with open(self.dest_path, "wb") as f:
                                    f.write(data)
                                self.signals.loaded.emit(self.key, self.dest_path)
                                return
                except Exception:
                    continue

            # Signal empty string to trigger clean fallback rendering
            self.signals.loaded.emit(self.key, "")
        except Exception:
            self.signals.loaded.emit(self.key, "")


class GameCardWidget(QFrame):
    def __init__(self, game_info: Dict[str, Any], signals: ImageDownloadSignals, parent=None):
        super().__init__(parent)
        self.game_info = game_info
        self.appid = str(game_info.get("appid", ""))
        self.name = game_info.get("name", f"AppID {self.appid}")
        self.is_free = game_info.get("is_free", False)
        
        raw_hours = str(game_info.get("hours", "0")).replace(",", "").strip()
        try:
            h_float = float(raw_hours)
            if h_float >= 10:
                self.hours_num = int(round(h_float))
                self.hours_str = f"{self.hours_num:,} hrs"
            elif h_float > 0:
                self.hours_num = h_float
                self.hours_str = f"{h_float:.1f} hrs"
            else:
                self.hours_num = 0
                self.hours_str = "0 hrs"
        except Exception:
            self.hours_num = 0
            self.hours_str = "0 hrs"

        self.setObjectName("GameCard")
        self.setFixedSize(228, 205)
        self.setStyleSheet("""
            QFrame#GameCard {
                background-color: #121522;
                border: 1px solid #1c2235;
                border-radius: 8px;
            }
            QFrame#GameCard:hover {
                background-color: #181d2e;
                border: 1px solid #ff1e38;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.banner_label = QLabel()
        self.banner_label.setFixedSize(212, 98)
        self.banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_label.setStyleSheet("""
            background: transparent;
            border-radius: 6px;
        """)
        self._set_fallback_banner()
        layout.addWidget(self.banner_label)

        self.title_label = QLabel(self.name)
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #f1f5f9; padding-left: 2px;")
        self.title_label.setToolTip(self.name)
        metrics = self.title_label.fontMetrics()
        elided = metrics.elidedText(self.name, Qt.TextElideMode.ElideRight, 206)
        self.title_label.setText(elided)
        layout.addWidget(self.title_label)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        meta_row.setContentsMargins(2, 0, 2, 0)

        clock_lbl = QLabel(f"🕒 {self.hours_str}")
        clock_lbl.setFont(QFont("Segoe UI", 9))
        clock_lbl.setStyleSheet("color: #8b95a8; font-weight: 500;")
        meta_row.addWidget(clock_lbl)
        meta_row.addStretch()

        if self.hours_num > 0:
            status_tag = QLabel("● Played")
            status_tag.setStyleSheet("color: #00e676; font-size: 10px; font-weight: 600;")
        else:
            status_tag = QLabel("☁ Cloud Only")
            status_tag.setStyleSheet("color: #448aff; font-size: 10px; font-weight: 600;")
        meta_row.addWidget(status_tag)
        layout.addLayout(meta_row)

        tier_row = QHBoxLayout()
        tier_row.setContentsMargins(2, 0, 2, 0)
        
        tier_lbl = QLabel("💎 Paid License" if not self.is_free else "Free to Play")
        tier_color = COLOR_HIT if not self.is_free else COLOR_FREE
        tier_bg = "rgba(0, 230, 118, 0.12)" if not self.is_free else "rgba(0, 176, 255, 0.12)"
        tier_lbl.setStyleSheet(f"""
            color: {tier_color};
            background-color: {tier_bg};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)
        tier_row.addWidget(tier_lbl)
        tier_row.addStretch()

        if self.appid and self.appid != "0":
            store_btn = QPushButton("Store ↗")
            store_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            store_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #448aff;
                    border: none;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 0px 4px;
                }
                QPushButton:hover {
                    color: #82b1ff;
                    text-decoration: underline;
                }
            """)
            store_btn.clicked.connect(lambda: webbrowser.open(f"https://store.steampowered.com/app/{self.appid}"))
            tier_row.addWidget(store_btn)

        layout.addLayout(tier_row)

        self._load_banner(signals)

    def _load_banner(self, signals: ImageDownloadSignals):
        if not self.appid or self.appid == "0":
            self._set_fallback_banner()
            return

        dest_file = os.path.join(str(CACHE_IMAGES_DIR), f"{self.appid}.jpg")
        if os.path.exists(dest_file) and os.path.getsize(dest_file) > 300:
            self._set_pixmap(dest_file)
        else:
            candidate_urls = [
                f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{self.appid}/header.jpg",
                f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.appid}/header.jpg",
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.appid}/header.jpg",
                f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{self.appid}/capsule_616x353.jpg",
                f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.appid}/capsule_616x353.jpg",
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.appid}/capsule_231x87.jpg",
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.appid}/library_600x900.jpg"
            ]
            if self.game_info.get("banner_url"):
                candidate_urls.insert(0, self.game_info["banner_url"])

            task = ImageDownloadTask(f"game_{self.appid}", candidate_urls, dest_file, signals)
            QThreadPool.globalInstance().start(task)

    def _set_pixmap(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            self._set_fallback_banner()
            return

        pix = QPixmap(file_path)
        if pix.isNull() or pix.width() < 10:
            self._set_fallback_banner()
            return

        w, h = 212, 98
        scaled = pix.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )

        out_pix = QPixmap(w, h)
        out_pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out_pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 6, 6)
        painter.setClipPath(path)

        cx = max(0, (scaled.width() - w) // 2)
        cy = max(0, (scaled.height() - h) // 2)
        painter.drawPixmap(0, 0, scaled, cx, cy, w, h)
        painter.end()

        self.banner_label.setPixmap(out_pix)
        self.banner_label.setText("")

    def _set_fallback_banner(self):
        w, h = 212, 98
        out_pix = QPixmap(w, h)
        out_pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out_pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0, QColor("#1e2538"))
        gradient.setColorAt(1, QColor("#101420"))

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 6, 6)
        painter.fillPath(path, gradient)

        painter.setPen(QColor("#7b849b"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(self.name, Qt.TextElideMode.ElideRight, w - 24)
        painter.drawText(QRect(12, 34, w - 24, 30), Qt.AlignmentFlag.AlignCenter, f"🎮 {elided}")
        painter.end()

        self.banner_label.setPixmap(out_pix)
        self.banner_label.setText("")


class LibraryInspectionModal(QDialog):
    def __init__(self, item_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.all_games: List[Dict[str, Any]] = list(item_data.get("games", []))
        self.current_filtered_games = list(self.all_games)
        self.signals = ImageDownloadSignals()
        self.signals.loaded.connect(self._on_image_loaded)

        user = item_data.get("persona_name") or item_data.get("username", "Account")
        self.setWindowTitle(f"Steam Account Details — {user}")
        self.setMinimumSize(1080, 680)
        self.resize(1120, 720)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_BG_DARK};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: #0d1017;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #1e2638;
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #ff1e38;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(14)

        main_layout.addLayout(self._build_top_header())

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)
        content_layout.addWidget(self._build_profile_card(), stretch=0)
        content_layout.addWidget(self._build_games_section(), stretch=1)
        main_layout.addLayout(content_layout)

    def _build_top_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(16)

        back_btn = QPushButton("← Back to Results")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #141824;
                color: #f1f5f9;
                border: 1px solid #232d42;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1e2538;
                border-color: #ff1e38;
                color: #ffffff;
            }
        """)
        back_btn.clicked.connect(self.accept)
        header.addWidget(back_btn)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("Steam Account Details")
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff; letter-spacing: 0.3px;")

        sub_lbl = QLabel("View account information and owned games library.")
        sub_lbl.setStyleSheet("color: #7b849b; font-size: 11px;")

        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header.addLayout(title_box)

        header.addStretch()

        op_card = QFrame()
        op_card.setStyleSheet("""
            QFrame {
                background-color: #121522;
                border: 1px solid #1c2235;
                border-radius: 20px;
                padding: 3px 12px;
            }
        """)
        op_layout = QHBoxLayout(op_card)
        op_layout.setContentsMargins(6, 4, 10, 4)
        op_layout.setSpacing(8)

        op_avatar = QLabel("●")
        op_avatar.setStyleSheet("color: #00e676; font-size: 10px;")
        op_layout.addWidget(op_avatar)

        op_name = QLabel("Operator 👑 Premium")
        op_name.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 700;")
        op_layout.addWidget(op_name)

        header.addWidget(op_card)
        return header

    def _build_profile_card(self) -> QFrame:
        card = QFrame()
        card.setFixedWidth(290)
        card.setObjectName("ProfileCard")
        card.setStyleSheet("""
            QFrame#ProfileCard {
                background-color: #11141e;
                border: 1px solid #1c2233;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 20, 18, 20)
        layout.setSpacing(14)

        avatar_box = QHBoxLayout()
        avatar_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(96, 96)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("""
            QLabel {
                background-color: #1a2030;
                border: 2px solid #ff1e38;
                border-radius: 48px;
                color: #ffffff;
                font-size: 32px;
                font-weight: bold;
            }
        """)
        persona = self.item_data.get("persona_name") or self.item_data.get("username", "A")
        self.avatar_label.setText(persona[:1].upper() if persona else "U")
        avatar_box.addWidget(self.avatar_label)
        layout.addLayout(avatar_box)

        name_lbl = QLabel(persona)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #ffffff;")
        layout.addWidget(name_lbl)

        country = self.item_data.get("country", "🌐 Global")
        loc_str = self.item_data.get("location", "")
        loc_display = f"{country} ({loc_str})" if loc_str else country
        country_lbl = QLabel(loc_display)
        country_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        country_lbl.setStyleSheet("color: #8b95a8; font-size: 11px;")
        layout.addWidget(country_lbl)

        steamid = self.item_data.get("steamid", "")
        if steamid:
            profile_link_lbl = QLabel(f"<a href='https://steamcommunity.com/profiles/{steamid}' style='color: #448aff; text-decoration: none; font-size: 11px; font-weight: 600;'>Steam Profile ↗</a>")
            profile_link_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            profile_link_lbl.setOpenExternalLinks(True)
            layout.addWidget(profile_link_lbl)

        layout.addSpacing(6)

        total_g = self.item_data.get("total_games", 0)
        paid_g = self.item_data.get("paid_games", 0)
        layout.addWidget(self._create_info_row("🎮", "Games Owned", f"{total_g} Total ({paid_g} Paid)"))

        vac_banned = self.item_data.get("vac_banned", False)
        vac_text = "Banned (1 VAC Ban)" if vac_banned else "No Bans"
        vac_color = COLOR_INVALID if vac_banned else COLOR_HIT
        layout.addWidget(self._create_info_row("🛡️", "VAC Status", vac_text, vac_color))

        is_limited = self.item_data.get("is_limited", False)
        if is_limited:
            acc_type = "Limited Account ($5 Locked)"
            type_color = COLOR_INVALID
        elif paid_g > 0:
            acc_type = "Paid (Full Access)"
            type_color = COLOR_HIT
        else:
            acc_type = "Free Tier"
            type_color = COLOR_FREE
        layout.addWidget(self._create_info_row("👤", "Account Type", acc_type, type_color))

        wallet = self.item_data.get("wallet", "")
        if wallet:
            layout.addWidget(self._create_info_row("💰", "Wallet Balance", wallet, "#00e676"))

        now_str = datetime.now().strftime("%b %d, %Y %H:%M")
        layout.addWidget(self._create_info_row("📅", "Last Check", now_str))

        layout.addStretch()

        acc_str = self.item_data.get("account", "")
        copy_btn = QPushButton("📋 Copy Credentials")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #171c2b;
                color: #e2e8f0;
                border: 1px solid #232d42;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #22293d;
                border-color: #ff1e38;
                color: #ffffff;
            }
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(acc_str))
        layout.addWidget(copy_btn)

        if steamid:
            view_steam_btn = QPushButton("🌐 View on Steam ↗")
            view_steam_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            view_steam_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2233, stop:1 #111722);
                    color: #448aff;
                    border: 1px solid #2a3952;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #232f47, stop:1 #171f2e);
                    border-color: #448aff;
                    color: #82b1ff;
                }
            """)
            view_steam_btn.clicked.connect(lambda: webbrowser.open(f"https://steamcommunity.com/profiles/{steamid}"))
            layout.addWidget(view_steam_btn)

        self._load_avatar()
        return card

    def _create_info_row(self, icon: str, label: str, value: str, val_color: str = "#ffffff") -> QFrame:
        box = QFrame()
        box.setStyleSheet("""
            QFrame {
                background-color: #151926;
                border: 1px solid #1c2233;
                border-radius: 6px;
            }
        """)
        row = QHBoxLayout(box)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont("Segoe UI", 12))
        row.addWidget(icon_lbl)

        txt_box = QVBoxLayout()
        txt_box.setSpacing(1)

        t_lbl = QLabel(label)
        t_lbl.setStyleSheet("color: #727b91; font-size: 10px; font-weight: 600;")
        
        v_lbl = QLabel(value)
        v_lbl.setStyleSheet(f"color: {val_color}; font-size: 11px; font-weight: 700;")
        
        txt_box.addWidget(t_lbl)
        txt_box.addWidget(v_lbl)
        row.addLayout(txt_box)
        row.addStretch()

        return box

    def _load_avatar(self):
        steamid = self.item_data.get("steamid", "")
        avatar_url = self.item_data.get("avatar_url", "")
        if not steamid:
            return

        dest_file = os.path.join(str(CACHE_AVATARS_DIR), f"{steamid}.jpg")
        if os.path.exists(dest_file):
            self._set_avatar_pixmap(dest_file)
        elif avatar_url:
            task = ImageDownloadTask(f"avatar_{steamid}", avatar_url, dest_file, self.signals)
            QThreadPool.globalInstance().start(task)

    def _set_avatar_pixmap(self, file_path: str):
        pix = QPixmap(file_path)
        if not pix.isNull():
            size = 96
            scaled = pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            out_img = QPixmap(size, size)
            out_img.fill(Qt.GlobalColor.transparent)

            painter = QPainter(out_img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addEllipse(0, 0, size, size)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()

            self.avatar_label.setPixmap(out_img)
            self.avatar_label.setText("")

    def _build_games_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header_bar = QHBoxLayout()
        header_bar.setSpacing(10)

        self.games_header_title = QLabel(f"🎮 Owned Games ({len(self.all_games)})")
        self.games_header_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.games_header_title.setStyleSheet("color: #ffffff;")
        header_bar.addWidget(self.games_header_title)

        header_bar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter games by title or AppID...")
        self.search_input.setFixedWidth(240)
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
        self.search_input.textChanged.connect(self._on_search_or_sort_changed)
        header_bar.addWidget(self.search_input)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([
            "Playtime (High → Low)",
            "Playtime (Low → High)",
            "Game Title (A → Z)",
            "Paid Licenses First"
        ])
        self.sort_combo.setFixedWidth(180)
        self.sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #141824;
                color: #e2e8f0;
                border: 1px solid #1e2536;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: #2a354c;
            }
            QComboBox QAbstractItemView {
                background-color: #121520;
                color: #f1f5f9;
                selection-background-color: #242c3d;
            }
        """)
        self.sort_combo.currentIndexChanged.connect(self._on_search_or_sort_changed)
        header_bar.addWidget(self.sort_combo)

        layout.addLayout(header_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.grid_container)
        layout.addWidget(self.scroll_area)

        self._render_games_grid()
        return container

    def _render_games_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        columns = 3
        for idx, game in enumerate(self.current_filtered_games):
            card = GameCardWidget(game, self.signals)
            row = idx // columns
            col = idx % columns
            self.grid_layout.addWidget(card, row, col)

        self.games_header_title.setText(f"🎮 Owned Games ({len(self.current_filtered_games)})")

    def _on_search_or_sort_changed(self):
        query = self.search_input.text().lower().strip()
        sort_mode = self.sort_combo.currentIndex()

        filtered = []
        for g in self.all_games:
            name = str(g.get("name", "")).lower()
            aid = str(g.get("appid", "")).lower()
            if not query or (query in name or query in aid):
                filtered.append(g)

        def get_hours_val(item):
            raw = str(item.get("hours", "0")).replace(",", "").strip()
            try:
                return float(raw)
            except Exception:
                return 0.0

        if sort_mode == 0:
            filtered.sort(key=lambda g: get_hours_val(g), reverse=True)
        elif sort_mode == 1:
            filtered.sort(key=lambda g: get_hours_val(g))
        elif sort_mode == 2:
            filtered.sort(key=lambda g: str(g.get("name", "")).lower())
        elif sort_mode == 3:
            filtered.sort(key=lambda g: (1 if g.get("is_free") else 0, -get_hours_val(g)))

        self.current_filtered_games = filtered
        self._render_games_grid()

    def _on_image_loaded(self, key: str, file_path: str):
        if key.startswith("avatar_"):
            self._set_avatar_pixmap(file_path)
        elif key.startswith("game_"):
            aid = key.replace("game_", "")
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                if isinstance(widget, GameCardWidget) and widget.appid == aid:
                    if file_path and os.path.exists(file_path):
                        widget._set_pixmap(file_path)
                    else:
                        widget._set_fallback_banner()
                    break