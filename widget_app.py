"""
104Society — Cloud & Local Steam Validator Dashboard Widget
============================================================
Ultra-modern real-time monitoring widget.
Tracks both GitHub Actions 24/7 cloud runner and local validator runs.
"""

import os
import sys
import json
import time
import urllib.request
import threading
import webbrowser
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

# ── Paths & Config ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else SCRIPT_DIR

# Check standard installation path first so running from Desktop works seamlessly
POTENTIAL_DIRS = [
    Path(r"D:\Steam Checker\results"),
    APP_DIR / "results",
    SCRIPT_DIR / "results",
    Path.cwd() / "results"
]
RESULTS_DIR = next((d for d in POTENTIAL_DIRS if d.exists()), Path(r"D:\Steam Checker\results"))

CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"
HITSDC_FILE     = RESULTS_DIR / "hitsdc.txt"
HITS_ALL_FILE   = RESULTS_DIR / "hits_all_paid.txt"

TOTAL_ACCOUNTS_DEFAULT = 910027
GITHUB_REPO = "mertkapan/nexus-validator"
GITHUB_RUNS_API = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=5"
GITHUB_ARTIFACTS_API = f"https://api.github.com/repos/{GITHUB_REPO}/actions/artifacts?per_page=5"

# ── Dark Glass Theme Colors ─────────────────────────────────────────────────
C_BG_DARK    = "#0b0f19"   # Root background
C_CARD_BG    = "#111827"   # Container cards
C_CARD_ALT   = "#172033"   # Hover / active card
C_BORDER     = "#1f293d"   # Crisp borders
C_TEXT_PRI   = "#f9fafb"   # Primary text
C_TEXT_SEC   = "#9ca3af"   # Muted labels
C_TEXT_MUTED = "#6b7280"   # Faint info

C_ACCENT     = "#6366f1"   # Indigo
C_GREEN      = "#10b981"   # Emerald (Hit)
C_PURPLE     = "#a855f7"   # Violet (Target)
C_ORANGE     = "#f59e0b"   # Amber (2FA)
C_RED        = "#ef4444"   # Red (Bad / Invalid)
C_CYAN       = "#06b6d4"   # Cyan (Rate)
C_GOLD       = "#fbbf24"   # Gold (Football)


class ModernCard(tk.Frame):
    """Sleek metric display card."""
    def __init__(self, parent, title: str, initial_val: str, accent_color: str, subtitle: str = ""):
        super().__init__(parent, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1, padx=14, pady=10)
        self.accent_color = accent_color
        
        # Title
        tk.Label(self, text=title.upper(), font=("Segoe UI", 8, "bold"), fg=C_TEXT_SEC, bg=C_CARD_BG).pack(anchor="w")
        
        # Big Value
        self.val_var = tk.StringVar(value=initial_val)
        self.val_label = tk.Label(self, textvariable=self.val_var, font=("Segoe UI", 18, "bold"), fg=accent_color, bg=C_CARD_BG)
        self.val_label.pack(anchor="w", pady=(2, 0))
        
        # Subtitle / hint
        self.sub_var = tk.StringVar(value=subtitle)
        self.sub_label = tk.Label(self, textvariable=self.sub_var, font=("Segoe UI", 8), fg=C_TEXT_MUTED, bg=C_CARD_BG)
        if subtitle:
            self.sub_label.pack(anchor="w")

    def update_data(self, val: str, subtitle: str = None, color: str = None):
        self.val_var.set(val)
        if subtitle is not None:
            self.sub_var.set(subtitle)
            if not self.sub_label.winfo_ismapped() and subtitle:
                self.sub_label.pack(anchor="w")
        if color:
            self.val_label.configure(fg=color)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("104Society — Steam Validator Cloud & Local Monitor")
        self.geometry("1100x740")
        self.minsize(980, 650)
        self.configure(bg=C_BG_DARK)

        # App state
        self.total_accounts = TOTAL_ACCOUNTS_DEFAULT
        self.last_checked = 0
        self.last_sync_time = 0
        self.github_run_info = {"status": "Sorgulanıyor...", "id": "—", "duration": "—", "active": False}
        self.cloud_runs_list = []
        
        # Build UI
        self._setup_styles()
        self._create_header()
        self._create_metrics_grid()
        self._create_progress_section()
        self._create_tabs_section()
        self._create_status_bar()

        # Start background polling threads
        self.running = True
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.poll_thread = threading.Thread(target=self._background_poller, daemon=True)
        self.poll_thread.start()

    def _setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Configure notebook tabs
        self.style.configure("TNotebook", background=C_BG_DARK, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=C_CARD_BG, foreground=C_TEXT_SEC, font=("Segoe UI", 9, "bold"), padding=[16, 6], borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", C_CARD_ALT)], foreground=[("selected", C_TEXT_PRI)])

        # Configure Progressbar
        self.style.configure("Cyber.Horizontal.TProgressbar", background=C_GREEN, troughcolor=C_CARD_BG, borderwidth=0, thickness=12)

        # Configure Treeview (Hits table)
        self.style.configure("Treeview", background=C_CARD_BG, foreground=C_TEXT_PRI, fieldbackground=C_CARD_BG, rowheight=26, font=("Segoe UI", 9), borderwidth=0)
        self.style.configure("Treeview.Heading", background=C_CARD_ALT, foreground=C_TEXT_SEC, font=("Segoe UI", 9, "bold"), borderwidth=0)
        self.style.map("Treeview", background=[("selected", C_ACCENT)], foreground=[("selected", C_TEXT_PRI)])

    def _create_header(self):
        header = tk.Frame(self, bg=C_BG_DARK, padx=20, pady=12)
        header.pack(fill="x")

        # Left: Branding
        left_box = tk.Frame(header, bg=C_BG_DARK)
        left_box.pack(side="left")

        title_lbl = tk.Label(left_box, text="104Society", font=("Segoe UI", 20, "bold"), fg=C_ACCENT, bg=C_BG_DARK)
        title_lbl.pack(side="left")

        sub_lbl = tk.Label(left_box, text="  CLOUD & LOCAL VALIDATOR WIDGET", font=("Segoe UI", 10, "bold"), fg=C_TEXT_SEC, bg=C_BG_DARK)
        sub_lbl.pack(side="left", padx=(4, 0), pady=(6, 0))

        # Right: GitHub status & Actions
        right_box = tk.Frame(header, bg=C_BG_DARK)
        right_box.pack(side="right")

        # Cloud Status Badge
        self.badge_frame = tk.Frame(right_box, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1, padx=10, pady=5)
        self.badge_frame.pack(side="left", padx=(0, 10))

        self.badge_dot = tk.Label(self.badge_frame, text="●", font=("Segoe UI", 10), fg=C_ORANGE, bg=C_CARD_BG)
        self.badge_dot.pack(side="left", padx=(0, 5))

        self.badge_text = tk.Label(self.badge_frame, text="GITHUB ACTIONS: KONTROL EDİLİYOR", font=("Segoe UI", 9, "bold"), fg=C_TEXT_PRI, bg=C_CARD_BG)
        self.badge_text.pack(side="left")

        # Action Buttons
        btn_refresh = tk.Button(right_box, text="🔄 Yenile", font=("Segoe UI", 9, "bold"), bg=C_CARD_BG, fg=C_GREEN, activebackground=C_CARD_ALT, activeforeground=C_GREEN, relief="flat", highlightbackground=C_BORDER, highlightthickness=1, padx=10, pady=4, cursor="hand2", command=self._force_manual_refresh)
        btn_refresh.pack(side="left", padx=4)

        btn_github = tk.Button(right_box, text="🌐 GitHub Aç", font=("Segoe UI", 9, "bold"), bg=C_CARD_BG, fg=C_TEXT_PRI, activebackground=C_CARD_ALT, activeforeground=C_TEXT_PRI, relief="flat", highlightbackground=C_BORDER, highlightthickness=1, padx=10, pady=4, cursor="hand2", command=self._open_github)
        btn_github.pack(side="left", padx=4)

        btn_folder = tk.Button(right_box, text="📂 Sonuç Klasörü", font=("Segoe UI", 9, "bold"), bg=C_CARD_BG, fg=C_TEXT_PRI, activebackground=C_CARD_ALT, activeforeground=C_TEXT_PRI, relief="flat", highlightbackground=C_BORDER, highlightthickness=1, padx=10, pady=4, cursor="hand2", command=self._open_results_folder)
        btn_folder.pack(side="left", padx=4)


    def _create_metrics_grid(self):
        grid_container = tk.Frame(self, bg=C_BG_DARK, padx=20, pady=2)
        grid_container.pack(fill="x")

        # Row 1
        r1 = tk.Frame(grid_container, bg=C_BG_DARK)
        r1.pack(fill="x", pady=4)

        self.card_checked   = ModernCard(r1, "Kontrol Edilen", "0", C_CYAN, "İşlenen hesap sayısı")
        self.card_remaining = ModernCard(r1, "Kalan Hesap", f"{self.total_accounts:,}", C_TEXT_PRI, "Kuyrukta bekleyen")
        self.card_total     = ModernCard(r1, "Toplam Hesap", f"{self.total_accounts:,}", C_TEXT_SEC, "1_combined.txt listesi")
        self.card_speed     = ModernCard(r1, "Hız / Verim", "0 CPM", C_ACCENT, "Dakika başına hesap")

        for c in (self.card_checked, self.card_remaining, self.card_total, self.card_speed):
            c.pack(side="left", fill="both", expand=True, padx=4)

        # Row 2
        r2 = tk.Frame(grid_container, bg=C_BG_DARK)
        r2.pack(fill="x", pady=4)

        self.card_hits      = ModernCard(r2, "Geçerli Hit", "0", C_GREEN, "Doğrudan giriş yapılan")
        self.card_targets   = ModernCard(r2, "Target Hit (FC/GTA)", "0", C_PURPLE, "Yüksek değerli oyunlar")
        self.card_2fa       = ModernCard(r2, "Steam Guard (2FA)", "0", C_ORANGE, "Şifre doğru, kodlu")
        self.card_bad       = ModernCard(r2, "Geçersiz / Bad", "0", C_RED, "Hatalı şifre / banlı")

        for c in (self.card_hits, self.card_targets, self.card_2fa, self.card_bad):
            c.pack(side="left", fill="both", expand=True, padx=4)

    def _create_progress_section(self):
        container = tk.Frame(self, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1, padx=16, pady=10)
        container.pack(fill="x", padx=24, pady=6)

        header_box = tk.Frame(container, bg=C_CARD_BG)
        header_box.pack(fill="x", pady=(0, 6))

        tk.Label(header_box, text="GENEL TARAMA İLERLEMESİ", font=("Segoe UI", 9, "bold"), fg=C_TEXT_SEC, bg=C_CARD_BG).pack(side="left")
        
        self.lbl_progress_pct = tk.Label(header_box, text="%0.00", font=("Segoe UI", 10, "bold"), fg=C_GREEN, bg=C_CARD_BG)
        self.lbl_progress_pct.pack(side="right")

        self.pbar = ttk.Progressbar(container, style="Cyber.Horizontal.TProgressbar", maximum=100, value=0)
        self.pbar.pack(fill="x")

    def _create_tabs_section(self):
        tabs_container = tk.Frame(self, bg=C_BG_DARK, padx=20, pady=4)
        tabs_container.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(tabs_container)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Live Hits Stream
        self.tab_hits = tk.Frame(self.notebook, bg=C_CARD_BG, padx=12, pady=10)
        self.notebook.add(self.tab_hits, text="  🎯 Canlı Hit Akışı (Discord & TXT)  ")
        self._build_hits_tab()

        # Tab 2: Cloud / GitHub Actions
        self.tab_cloud = tk.Frame(self.notebook, bg=C_CARD_BG, padx=14, pady=12)
        self.notebook.add(self.tab_cloud, text="  ☁️ GitHub Actions 24/7 Bulut Durumu  ")
        self._build_cloud_tab()

    def _build_hits_tab(self):
        # Action bar above tree
        top_bar = tk.Frame(self.tab_hits, bg=C_CARD_BG)
        top_bar.pack(fill="x", pady=(0, 6))

        # Search & Filter bar
        filter_box = tk.Frame(top_bar, bg=C_CARD_BG)
        filter_box.pack(side="left", padx=(15, 0))
        tk.Label(filter_box, text="Filtrele:", font=("Segoe UI", 9, "bold"), fg=C_ACCENT, bg=C_CARD_BG).pack(side="left")
        self.entry_filter = tk.Entry(filter_box, font=("Segoe UI", 9), bg=C_CARD_ALT, fg=C_TEXT_PRI, insertbackground=C_TEXT_PRI, relief="flat", highlightbackground=C_BORDER, highlightthickness=1, width=18)
        self.entry_filter.pack(side="left", padx=4)
        self.entry_filter.bind("<KeyRelease>", lambda e: self._filter_hits_table())

        btn_copy = tk.Button(top_bar, text="📋 Seçili Hesabı Kopyala", font=("Segoe UI", 8, "bold"), bg=C_CARD_ALT, fg=C_TEXT_PRI, activebackground=C_BORDER, relief="flat", highlightbackground=C_BORDER, highlightthickness=1, padx=8, pady=2, cursor="hand2", command=self._copy_selected_hit)
        btn_copy.pack(side="right", padx=4)

        btn_open_txt = tk.Button(top_bar, text="📄 hitsdc.txt Aç", font=("Segoe UI", 8, "bold"), bg=C_CARD_ALT, fg=C_TEXT_PRI, activebackground=C_BORDER, relief="flat", highlightbackground=C_BORDER, highlightthickness=1, padx=8, pady=2, cursor="hand2", command=lambda: self._open_file(HITSDC_FILE))
        btn_open_txt.pack(side="right", padx=4)


        # Treeview
        columns = ("time", "account", "status", "country", "wallet", "paid_count", "games")
        self.tree = ttk.Treeview(self.tab_hits, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("time", text="Kayıt")
        self.tree.heading("account", text="Hesap (User:Pass)")
        self.tree.heading("status", text="Durum")
        self.tree.heading("country", text="Ülke")
        self.tree.heading("wallet", text="Bakiye")
        self.tree.heading("paid_count", text="Ücretli")
        self.tree.heading("games", text="Oyun Kütüphanesi")

        self.tree.column("time", width=70, anchor="center")
        self.tree.column("account", width=180)
        self.tree.column("status", width=70, anchor="center")
        self.tree.column("country", width=100)
        self.tree.column("wallet", width=90)
        self.tree.column("paid_count", width=60, anchor="center")
        self.tree.column("games", width=420)

        # Scrollbar
        sb = ttk.Scrollbar(self.tab_hits, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

    def _build_cloud_tab(self):
        # Cloud status card
        cloud_card = tk.Frame(self.tab_cloud, bg=C_CARD_ALT, highlightbackground=C_BORDER, highlightthickness=1, padx=16, pady=12)
        cloud_card.pack(fill="x", pady=(0, 12))

        tk.Label(cloud_card, text="GITHUB ACTIONS BULUT ÇALIŞTIRICI BİLGİSİ", font=("Segoe UI", 10, "bold"), fg=C_ACCENT, bg=C_CARD_ALT).pack(anchor="w")

        self.lbl_cloud_details = tk.Label(
            cloud_card,
            text="GitHub API ile bağlanılıyor...",
            font=("Consolas", 9),
            fg=C_TEXT_PRI,
            bg=C_CARD_ALT,
            justify="left"
        )
        self.lbl_cloud_details.pack(anchor="w", pady=(6, 0))

        # Cloud actions history
        tk.Label(self.tab_cloud, text="Son GitHub Actions Koşuları (Runs):", font=("Segoe UI", 9, "bold"), fg=C_TEXT_SEC, bg=C_CARD_BG).pack(anchor="w", pady=(6, 4))

        self.txt_cloud_runs = tk.Text(self.tab_cloud, bg=C_CARD_BG, fg=C_TEXT_PRI, font=("Consolas", 9), relief="flat", highlightbackground=C_BORDER, highlightthickness=1, padx=10, pady=8, height=10)
        self.txt_cloud_runs.pack(fill="both", expand=True)

    def _create_status_bar(self):
        bar = tk.Frame(self, bg=C_CARD_BG, highlightbackground=C_BORDER, highlightthickness=1, padx=16, pady=4)
        bar.pack(fill="x", side="bottom")

        self.lbl_status = tk.Label(bar, text="Sistem başlatıldı. Canlı senkronizasyon aktif.", font=("Segoe UI", 8), fg=C_TEXT_SEC, bg=C_CARD_BG)
        self.lbl_status.pack(side="left")

        self.lbl_last_update = tk.Label(bar, text="Son Güncelleme: —", font=("Segoe UI", 8), fg=C_TEXT_MUTED, bg=C_CARD_BG)
        self.lbl_last_update.pack(side="right")

    # ── Background Worker ───────────────────────────────────────────────────
    def _background_poller(self):
        """Polls local files and GitHub Actions API periodically."""
        github_poll_counter = 0

        while self.running:
            try:
                # 1. Read local checkpoint
                cp_data = {}
                if CHECKPOINT_FILE.exists():
                    try:
                        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                            cp_data = json.load(f)
                    except Exception:
                        pass

                # 2. Read hitsdc.txt for live hits table
                recent_hits = []
                if HITSDC_FILE.exists():
                    try:
                        with open(HITSDC_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            lines = [l.strip() for l in f if l.strip()]
                            recent_hits = lines[-50:]  # last 50
                    except Exception:
                        pass

                # 3. Query GitHub Actions every 10 seconds
                cloud_data = None
                if github_poll_counter % 5 == 0:
                    cloud_data = self._fetch_github_status()

                # Update UI on main thread
                self.after(0, self._apply_update, cp_data, recent_hits, cloud_data)

            except Exception as e:
                pass

            github_poll_counter += 1
            time.sleep(2.0)

    def _fetch_github_status(self) -> dict:
        """Queries GitHub Actions API for current workflow run status."""
        result = {"active": False, "status_text": "Bağlantı bekleniyor", "details": "", "runs": []}
        try:
            req = urllib.request.Request(
                GITHUB_RUNS_API,
                headers={"User-Agent": "104Society-Monitor"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                runs = data.get("workflow_runs", [])
                result["runs"] = runs

                if runs:
                    latest = runs[0]
                    st = latest.get("status", "")
                    conclusion = latest.get("conclusion")
                    run_id = latest.get("id")
                    created_at = latest.get("created_at", "")
                    event = latest.get("event", "")

                    if st == "in_progress":
                        result["active"] = True
                        result["status_text"] = f"🟢 BULUT KOŞUSU AKTİF (#{run_id})"
                    elif conclusion == "success":
                        result["active"] = False
                        result["status_text"] = f"⚪ BULUT TAMAMLANDI (#{run_id})"
                    else:
                        result["active"] = False
                        result["status_text"] = f"⚪ DURUM: {st.upper()} ({conclusion or 'beklemede'})"

                    result["details"] = (
                        f"Aktif Run ID   : {run_id}\n"
                        f"Koşu Durumu    : {st.upper()} ({conclusion or 'çalışıyor'})\n"
                        f"Tetikleyici    : {event}\n"
                        f"Başlama Zamanı : {created_at}\n"
                        f"Repo           : https://github.com/{GITHUB_REPO}\n"
                        f"Workflow URL   : https://github.com/{GITHUB_REPO}/actions/runs/{run_id}"
                    )
        except Exception as e:
            result["status_text"] = "GitHub API: Limit/Çevrimdışı"
            result["details"] = f"GitHub API Hatası: {e}"

        return result

    def _apply_update(self, cp: dict, recent_hits: list, cloud: dict):
        now_str = datetime.now().strftime("%H:%M:%S")

        checked     = cp.get("checked", 0)
        target_hits = cp.get("target_hits", 0)
        hits        = cp.get("hits", 0)
        two_fa      = cp.get("two_fa", 0)
        total       = cp.get("total", self.total_accounts) or self.total_accounts
        bad_count   = max(0, checked - (hits + two_fa))
        remaining   = max(0, total - checked)

        # Progress calculation
        pct = (checked / max(1, total)) * 100
        self.pbar["value"] = pct
        self.lbl_progress_pct.configure(text=f"%{pct:.2f} ({checked:,} / {total:,})")

        # Update metric cards
        self.card_checked.update_data(f"{checked:,}", f"{pct:.1f}% tamamlandı")
        self.card_remaining.update_data(f"{remaining:,}", "Kalan hesap")
        self.card_total.update_data(f"{total:,}", "Hedef liste")
        self.card_hits.update_data(f"{hits:,}", f"{(hits/max(1,checked)*100):.2f}% hit oranı")
        self.card_targets.update_data(f"{target_hits:,}", "Yüksek değerli oyun")
        self.card_2fa.update_data(f"{two_fa:,}", "Steam Guard kilitli")
        self.card_bad.update_data(f"{bad_count:,}", "Hatalı / geçersiz")

        # Speed calculation
        if self.last_checked > 0 and self.last_sync_time > 0:
            delta_n = checked - self.last_checked
            delta_t = time.time() - self.last_sync_time
            if delta_t > 0 and delta_n >= 0:
                cpm = int((delta_n / delta_t) * 60)
                self.card_speed.update_data(f"{cpm:,} CPM", "Canlı hız")
        self.last_checked = checked
        self.last_sync_time = time.time()

        # Update GitHub Actions Status Badge
        if cloud:
            if cloud.get("active"):
                self.badge_dot.configure(fg=C_GREEN)
                self.badge_text.configure(text=cloud.get("status_text", "GITHUB: AKTİF"))
            else:
                self.badge_dot.configure(fg=C_TEXT_SEC)
                self.badge_text.configure(text=cloud.get("status_text", "GITHUB: BEKLEMEDE"))

            if cloud.get("details"):
                self.lbl_cloud_details.configure(text=cloud["details"])

            # Cloud runs list
            runs = cloud.get("runs", [])
            if runs:
                self.txt_cloud_runs.delete("1.0", "end")
                for r in runs[:6]:
                    rid = r.get("id")
                    st = r.get("status", "")
                    con = r.get("conclusion") or "running"
                    dt = r.get("created_at", "")[:19].replace("T", " ")
                    evt = r.get("event", "")
                    self.txt_cloud_runs.insert("end", f"#{rid:<12} | {st:<12} | {con:<10} | {dt} | {evt}\n")

        # Update Live Hits Treeview
        if recent_hits:
            existing_count = len(self.tree.get_children())
            if len(recent_hits) != existing_count:
                new_rows = []
                for i, line in enumerate(reversed(recent_hits)):
                    # Line format: user:pass | SteamID:... | Status:HIT | VAC:... | Country:... | Wallet:... | PaidGames(N):[...]
                    parts = [p.strip() for p in line.split("|")]
                    acct = parts[0] if len(parts) > 0 else "—"
                    status = "HIT"
                    country = "—"
                    wallet = "—"
                    paid_str = "0"
                    games_str = "—"

                    for p in parts[1:]:
                        if p.startswith("Status:"):
                            status = p.split(":", 1)[1]
                        elif p.startswith("Country:"):
                            country = p.split(":", 1)[1]
                        elif p.startswith("Wallet:"):
                            wallet = p.split(":", 1)[1]
                        elif "PaidGames(" in p:
                            try:
                                paid_str = p.split("PaidGames(")[1].split(")")[0]
                                games_str = p.split("):[")[1].rstrip("]")
                            except Exception:
                                pass

                    new_rows.append((
                        f"#{len(recent_hits)-i}",
                        acct,
                        status,
                        country,
                        wallet,
                        paid_str,
                        games_str
                    ))
                self._cached_rows = new_rows
                self._filter_hits_table()


        self.lbl_last_update.configure(text=f"Son Senkronizasyon: {now_str}")
        self.lbl_status.configure(text=f"Checklenen: {checked:,} | Hit: {hits:,} | Bad: {bad_count:,} | Kalan: {remaining:,}")

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _open_github(self):
        webbrowser.open(f"https://github.com/{GITHUB_REPO}/actions")

    def _open_results_folder(self):
        try:
            if RESULTS_DIR.exists():
                os.startfile(str(RESULTS_DIR))
            else:
                os.startfile(str(SCRIPT_DIR))
        except Exception as e:
            messagebox.showinfo("Bilgi", f"Klasör yolu: {RESULTS_DIR}")

    def _force_manual_refresh(self):
        def _bg_run():
            try:
                cp_data = {}
                if CHECKPOINT_FILE.exists():
                    try:
                        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                            cp_data = json.load(f)
                    except Exception:
                        pass
                recent_hits = []
                if HITSDC_FILE.exists():
                    try:
                        with open(HITSDC_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            lines = [l.strip() for l in f if l.strip()]
                            recent_hits = lines[-50:]
                    except Exception:
                        pass
                cloud_data = self._fetch_github_status()
                self.after(0, self._apply_update, cp_data, recent_hits, cloud_data)
            except Exception:
                pass
        threading.Thread(target=_bg_run, daemon=True).start()

    def _open_file(self, path: Path):

        try:
            if path.exists():
                os.startfile(str(path))
            else:
                messagebox.showwarning("Uyarı", f"Dosya henüz oluşmadı: {path.name}")
        except Exception as e:
            messagebox.showerror("Hata", str(e))

    def _copy_selected_hit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Seçim Yapılmadı", "Lütfen listeden bir hesap seçin.")
            return
        vals = self.tree.item(sel[0], "values")
        if len(vals) > 1:
            acct = vals[1]
            self.clipboard_clear()
            self.clipboard_append(acct)
            messagebox.showinfo("Kopyalandı", f"Hesap panoya kopyalandı:\n{acct}")

    def _filter_hits_table(self):
        query = self.entry_filter.get().strip().lower() if hasattr(self, "entry_filter") else ""
        if not hasattr(self, "_cached_rows"):
            return
        self.tree.delete(*self.tree.get_children())
        for row in self._cached_rows:
            if not query or any(query in str(v).lower() for v in row):
                self.tree.insert("", "end", values=row)

    def _on_close(self):
        self.running = False
        self.destroy()



if __name__ == "__main__":
    app = App()
    app.mainloop()
