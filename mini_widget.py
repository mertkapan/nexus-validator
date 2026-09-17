"""
104Society — Ultra-Lightweight Native Desktop Widget
===================================================
Zero-lag, sleek HUD-style compact floating widget.
Displays live Checked, Remaining, Hits, Targets, 2FA, CPM, and latest Steam hit.
Has Always-on-Top toggle, draggable window, zero CPU footprint (<0.5%).
"""

import os
import sys
import json
import time
import threading
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

# Base Paths
BASE_DIR = Path(r"D:\Steam Checker")
RESULTS_DIR = BASE_DIR / "results"
CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"
HITSDC_FILE = RESULTS_DIR / "hitsdc.txt"

TOTAL_ACCOUNTS = 910027

# Colors
BG_MAIN     = "#0a0e17"
BG_CARD     = "#111726"
BG_CARD_ALT = "#161f33"
BORDER_COL  = "#1e293b"
TEXT_WHITE  = "#f8fafc"
TEXT_MUTED  = "#94a3b8"
TEXT_DIM    = "#64748b"

COLOR_CHECKED = "#38bdf8"
COLOR_TARGET  = "#ec4899"
COLOR_HIT     = "#10b981"
COLOR_2FA     = "#f59e0b"
COLOR_BAD     = "#ef4444"
COLOR_PURPLE  = "#8b5cf6"


class MiniWidget(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("104Society Monitor")
        self.geometry("450x380")
        self.resizable(False, False)
        self.configure(bg=BG_MAIN)
        self.attributes("-topmost", True)

        self.overrideredirect(True)

        self._offset_x = 0
        self._offset_y = 0

        self.last_checked = 0
        self.last_time = time.time()
        self.cpm = 0
        self.always_on_top = True

        self._build_ui()
        self._bind_drag_events()

        self.running = True
        self.poll_thread = threading.Thread(target=self._telemetry_worker, daemon=True)
        self.poll_thread.start()

    def _bind_drag_events(self):
        self.title_bar.bind("<ButtonPress-1>", self._start_move)
        self.title_bar.bind("<B1-Motion>", self._on_move)
        self.brand_title.bind("<ButtonPress-1>", self._start_move)
        self.brand_title.bind("<B1-Motion>", self._on_move)

    def _start_move(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_move(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        outer = tk.Frame(self, bg=BORDER_COL, padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=BG_MAIN, padx=14, pady=10)
        inner.pack(fill="both", expand=True)

        # 1. Custom Title Bar
        self.title_bar = tk.Frame(inner, bg=BG_MAIN, cursor="fleur")
        self.title_bar.pack(fill="x", pady=(0, 8))

        left_box = tk.Frame(self.title_bar, bg=BG_MAIN)
        left_box.pack(side="left")

        badge = tk.Label(left_box, text="104", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg=COLOR_PURPLE, padx=5, pady=1)
        badge.pack(side="left", padx=(0, 6))

        self.brand_title = tk.Label(left_box, text="104Society  ·  HUD Monitor", font=("Segoe UI", 10, "bold"), fg=TEXT_WHITE, bg=BG_MAIN)
        self.brand_title.pack(side="left")

        right_box = tk.Frame(self.title_bar, bg=BG_MAIN)
        right_box.pack(side="right")

        self.btn_pin = tk.Label(right_box, text="📌", font=("Segoe UI", 9), fg=COLOR_CHECKED, bg=BG_MAIN, cursor="hand2")
        self.btn_pin.pack(side="left", padx=5)
        self.btn_pin.bind("<Button-1>", lambda e: self._toggle_topmost())

        btn_min = tk.Label(right_box, text="—", font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=BG_MAIN, cursor="hand2")
        btn_min.pack(side="left", padx=5)
        btn_min.bind("<Button-1>", lambda e: self.iconify())

        btn_close = tk.Label(right_box, text="✕", font=("Segoe UI", 10, "bold"), fg=TEXT_MUTED, bg=BG_MAIN, cursor="hand2")
        btn_close.pack(side="left", padx=(5, 0))
        btn_close.bind("<Button-1>", lambda e: self._on_exit())

        # 2. Metric Cards
        metrics_frame = tk.Frame(inner, bg=BG_MAIN)
        metrics_frame.pack(fill="x", pady=(0, 8))

        self.card_checked_val, self.card_checked_pct = self._create_mini_card(
            metrics_frame, row=0, col=0, title="KONTROL EDİLEN", val="0", color=COLOR_CHECKED, sub="%0.00 / 910K"
        )
        self.card_target_val, self.card_target_sub = self._create_mini_card(
            metrics_frame, row=0, col=1, title="TARGET (FC/GTA)", val="0", color=COLOR_TARGET, sub="Özel Oyunlar"
        )
        self.card_hit_val, self.card_hit_sub = self._create_mini_card(
            metrics_frame, row=1, col=0, title="ÜCRETLİ HİT", val="0", color=COLOR_HIT, sub="Doğrudan Giriş"
        )
        self.card_2fa_val, self.card_speed_sub = self._create_mini_card(
            metrics_frame, row=1, col=1, title="2FA / HIZ", val="0", color=COLOR_2FA, sub="0 CPM"
        )

        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.columnconfigure(1, weight=1)

        # 3. Progress Bar
        p_box = tk.Frame(inner, bg=BG_CARD, highlightbackground=BORDER_COL, highlightthickness=1, padx=10, pady=6)
        p_box.pack(fill="x", pady=(0, 8))

        p_head = tk.Frame(p_box, bg=BG_CARD)
        p_head.pack(fill="x")
        tk.Label(p_head, text="TARAMA İLERLEMESİ", font=("Segoe UI", 7, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.lbl_pct = tk.Label(p_head, text="%0.00", font=("Segoe UI", 8, "bold"), fg=COLOR_HIT, bg=BG_CARD)
        self.lbl_pct.pack(side="right")

        self.pbar_canvas = tk.Canvas(p_box, height=6, bg="#0f172a", highlightthickness=0)
        self.pbar_canvas.pack(fill="x", pady=(4, 0))

        # 4. Live Hit Stream Box
        stream_box = tk.Frame(inner, bg=BG_CARD, highlightbackground=BORDER_COL, highlightthickness=1, padx=10, pady=8)
        stream_box.pack(fill="both", expand=True, pady=(0, 8))

        stream_head = tk.Frame(stream_box, bg=BG_CARD)
        stream_head.pack(fill="x", pady=(0, 4))
        tk.Label(stream_head, text="⚡ CANLI HİT AKIŞI", font=("Segoe UI", 7, "bold"), fg=COLOR_HIT, bg=BG_CARD).pack(side="left")
        
        self.btn_copy_hit = tk.Label(stream_head, text="📋 Kopyala", font=("Segoe UI", 8, "bold"), fg=COLOR_CHECKED, bg=BG_CARD, cursor="hand2")
        self.btn_copy_hit.pack(side="right")
        self.btn_copy_hit.bind("<Button-1>", lambda e: self._copy_latest_hit())

        self.lbl_hit_user = tk.Label(stream_box, text="Bekleniyor...", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=BG_CARD, anchor="w")
        self.lbl_hit_user.pack(fill="x")

        self.lbl_hit_games = tk.Label(stream_box, text="Kütüphane taranıyor...", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_CARD, anchor="w", wraplength=400, justify="left")
        self.lbl_hit_games.pack(fill="x", pady=(2, 0))

        self.lbl_hit_details = tk.Label(stream_box, text="Bakiye: 0.00 TL  |  VAC: Clean", font=("Segoe UI", 7), fg=TEXT_DIM, bg=BG_CARD, anchor="w")
        self.lbl_hit_details.pack(fill="x")

        # 5. Footer
        footer = tk.Frame(inner, bg=BG_MAIN)
        footer.pack(fill="x")

        self.lbl_engine_status = tk.Label(footer, text="● Motor: Aktif (35T)", font=("Segoe UI", 8, "bold"), fg=COLOR_HIT, bg=BG_MAIN)
        self.lbl_engine_status.pack(side="left")

        btn_folder = tk.Label(footer, text="📂 Kütük", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_MAIN, cursor="hand2")
        btn_folder.pack(side="right", padx=(6, 0))
        btn_folder.bind("<Button-1>", lambda e: self._open_results())

        btn_dc = tk.Label(footer, text="💬 Discord", font=("Segoe UI", 8, "bold"), fg=COLOR_PURPLE, bg=BG_MAIN, cursor="hand2")
        btn_dc.pack(side="right", padx=(6, 0))
        btn_dc.bind("<Button-1>", lambda e: self._open_discord_hits())

        self.latest_raw_hit = ""

    def _create_mini_card(self, parent, row, col, title, val, color, sub):
        card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER_COL, highlightthickness=1, padx=8, pady=6)
        card.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)

        tk.Label(card, text=title, font=("Segoe UI", 7, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
        val_lbl = tk.Label(card, text=val, font=("Segoe UI", 13, "bold"), fg=color, bg=BG_CARD)
        val_lbl.pack(anchor="w", pady=(1, 0))
        sub_lbl = tk.Label(card, text=sub, font=("Segoe UI", 7), fg=TEXT_DIM, bg=BG_CARD)
        sub_lbl.pack(anchor="w")
        return val_lbl, sub_lbl

    def _toggle_topmost(self):
        self.always_on_top = not self.always_on_top
        self.attributes("-topmost", self.always_on_top)
        self.btn_pin.configure(fg=COLOR_CHECKED if self.always_on_top else TEXT_DIM)

    def _copy_latest_hit(self):
        if self.latest_raw_hit:
            self.clipboard_clear()
            self.clipboard_append(self.latest_raw_hit)
            self.btn_copy_hit.configure(text="✓ Kopyalandı!", fg=COLOR_HIT)
            self.after(1500, lambda: self.btn_copy_hit.configure(text="📋 Kopyala", fg=COLOR_CHECKED))

    def _open_results(self):
        if RESULTS_DIR.exists():
            os.startfile(str(RESULTS_DIR))

    def _open_discord_hits(self):
        if HITSDC_FILE.exists():
            os.startfile(str(HITSDC_FILE))

    def _telemetry_worker(self):
        while self.running:
            cp_data = {}
            if CHECKPOINT_FILE.exists():
                try:
                    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                        cp_data = json.load(f)
                except Exception:
                    pass

            latest_hit = None
            if HITSDC_FILE.exists():
                try:
                    with open(HITSDC_FILE, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [l.strip() for l in f if l.strip()]
                        if lines:
                            latest_hit = lines[-1]
                except Exception:
                    pass

            self.after(0, self._apply_data, cp_data, latest_hit)
            time.sleep(1.5)

    def _apply_data(self, cp_data, latest_hit):
        checked = cp_data.get("checked", 0)
        target_hits = cp_data.get("target_hits", 0)
        hits = cp_data.get("hits", 0)
        two_fa = cp_data.get("two_fa", 0)

        now = time.time()
        dt = now - self.last_time
        if dt >= 3.0 and self.last_checked > 0:
            diff = checked - self.last_checked
            if diff >= 0:
                self.cpm = int((diff / dt) * 60)
            self.last_checked = checked
            self.last_time = now
        elif self.last_checked == 0 and checked > 0:
            self.last_checked = checked
            self.last_time = now

        pct = (checked / TOTAL_ACCOUNTS) * 100
        self.card_checked_val.configure(text=f"{checked:,}")
        self.card_checked_pct.configure(text=f"%{pct:.2f} / 910K")

        self.card_target_val.configure(text=f"{target_hits:,}")
        self.card_hit_val.configure(text=f"{hits:,}")
        self.card_2fa_val.configure(text=f"{two_fa:,}")
        self.card_speed_sub.configure(text=f"{self.cpm} CPM")

        self.lbl_pct.configure(text=f"%{pct:.2f}")

        self.pbar_canvas.delete("all")
        w = self.pbar_canvas.winfo_width()
        if w > 1:
            fill_w = max(2, int((pct / 100.0) * w))
            self.pbar_canvas.create_rectangle(0, 0, fill_w, 6, fill=COLOR_HIT, outline="")

        if latest_hit:
            parts = latest_hit.split(" | ")
            acct = parts[0] if parts else ""
            self.latest_raw_hit = acct
            u, _ = acct.split(":", 1) if ":" in acct else (acct, "")
            
            games_part = next((p for p in parts if "PaidGames" in p), "")
            games_text = "Oyun bilgisi yok"
            if ":[" in games_part:
                raw_g = games_part.split(":[", 1)[1].rsplit("]", 1)[0].strip()
                g_list = [g.strip() for g in raw_g.split(" | ") if g.strip()]
                if g_list:
                    shown = ", ".join(g_list[:3])
                    if len(g_list) > 3:
                        shown += f" +{len(g_list)-3} oyun daha"
                    games_text = f"🎮 ({len(g_list)} Ücretli): {shown}"

            wallet = next((p.replace("Wallet:", "").strip() for p in parts if "Wallet:" in p), "0.00 TL")
            vac = next((p.replace("VAC:", "").strip() for p in parts if "VAC:" in p), "CLEAN")

            self.lbl_hit_user.configure(text=f"👤 {u}")
            self.lbl_hit_games.configure(text=games_text)
            self.lbl_hit_details.configure(text=f"💰 {wallet}  |  🛡️ VAC: {vac}")

    def _on_exit(self):
        self.running = False
        self.destroy()


if __name__ == "__main__":
    app = MiniWidget()
    app.mainloop()
