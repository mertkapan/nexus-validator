"""
104Society — Live Checker Dashboard
====================================
Real-time monitoring widget for the Steam account checker.
Reads checkpoint.json and result files every 2 seconds.

Run:     python dashboard.py
Build EXE: pyinstaller --onefile --windowed dashboard.py
"""

import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, font
except ImportError:
    print("tkinter not available. Install Python with tkinter support.")
    sys.exit(1)

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
CHECKPOINT  = RESULTS_DIR / "checkpoint.json"
HITSDC      = RESULTS_DIR / "hitsdc.txt"
HITS_ALL    = RESULTS_DIR / "hits_all_paid.txt"
HITS_TARGET = RESULTS_DIR / "hits.txt"
GUARDED     = RESULTS_DIR / "guarded_2fa.txt"

REFRESH_MS  = 2000  # 2 seconds

# ── Color palette ────────────────────────────────────────────────────────────
BG          = "#0d1117"   # Very dark background
BG2         = "#161b22"   # Card background
BG3         = "#21262d"   # Input / darker card
ACCENT      = "#58a6ff"   # Blue accent
GREEN       = "#3fb950"   # Hit green
ORANGE      = "#d29922"   # Warning / 2FA
RED         = "#f85149"   # Error / VAC
PURPLE      = "#bc8cff"   # Target
TEXT        = "#e6edf3"   # Primary text
TEXT2       = "#8b949e"   # Secondary text
WHITE       = "#ffffff"
GOLD        = "#ffd700"   # Football / special

# ────────────────────────────────────────────────────────────────────────────

def read_checkpoint() -> dict:
    try:
        if CHECKPOINT.exists():
            return json.loads(CHECKPOINT.read_text("utf-8"))
    except Exception:
        pass
    return {}

def count_lines(path: Path) -> int:
    try:
        if path.exists():
            return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return 0

def read_recent_hits(n: int = 10) -> list:
    try:
        if HITSDC.exists():
            lines = HITSDC.read_text("utf-8", errors="ignore").splitlines()
            return [l for l in lines if l.strip()][-n:]
    except Exception:
        pass
    return []


class StatCard(tk.Frame):
    """A single metric card."""
    def __init__(self, parent, label: str, value: str = "0", color: str = ACCENT, **kw):
        super().__init__(parent, bg=BG2, relief="flat", **kw)
        self.configure(padx=16, pady=12)

        tk.Label(self, text=label, bg=BG2, fg=TEXT2,
                 font=("Consolas", 9, "bold")).pack(anchor="w")
        self._val_var = tk.StringVar(value=value)
        self._val_label = tk.Label(self, textvariable=self._val_var,
                                   bg=BG2, fg=color, font=("Consolas", 22, "bold"))
        self._val_label.pack(anchor="w")

    def update_value(self, v: str, color: str = None):
        self._val_var.set(v)
        if color:
            self._val_label.configure(fg=color)


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("104Society — Live Checker Dashboard")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(820, 600)

        # Start maximised
        try:
            self.state("zoomed")
        except Exception:
            self.geometry("960x700")

        self._start_real_time = time.time()
        self._prev_checked = 0
        self._last_refresh  = time.time()
        self._build_ui()
        self._schedule_refresh()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=BG, pady=12)
        header.pack(fill="x", padx=20)

        tk.Label(header, text="104Society", bg=BG, fg=ACCENT,
                 font=("Consolas", 20, "bold")).pack(side="left")
        tk.Label(header, text=" — Steam Account Validator Dashboard", bg=BG, fg=TEXT2,
                 font=("Consolas", 12)).pack(side="left")

        self._clock_var = tk.StringVar(value="--:--:--")
        tk.Label(header, textvariable=self._clock_var, bg=BG, fg=TEXT2,
                 font=("Consolas", 11)).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=4)

        # ── Stat cards ───────────────────────────────────────────────────────
        cards_frame = tk.Frame(self, bg=BG, padx=16, pady=8)
        cards_frame.pack(fill="x")

        metrics = [
            ("KONTROL EDİLEN",  "0",  ACCENT),
            ("TOPLAM HESAP",     "0",  TEXT2),
            ("HIT",              "0",  GREEN),
            ("TARGET HIT",      "0",  PURPLE),
            ("2FA KİLİTLİ",     "0",  ORANGE),
            ("DC GÖNDERİLEN",   "0",  GOLD),
            ("HIZ (CPM)",        "—",  ACCENT),
            ("İLERLEME",        "0%",  ACCENT),
        ]
        self._cards: dict[str, StatCard] = {}
        for i, (label, val, color) in enumerate(metrics):
            card = StatCard(cards_frame, label=label, value=val, color=color)
            card.grid(row=0, column=i, padx=6, pady=4, sticky="nsew")
            cards_frame.columnconfigure(i, weight=1)
            self._cards[label] = card

        # ── Progress bar ─────────────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg=BG, padx=20)
        prog_frame.pack(fill="x", pady=4)
        tk.Label(prog_frame, text="İLERLEME", bg=BG, fg=TEXT2,
                 font=("Consolas", 9)).pack(anchor="w")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("104.Horizontal.TProgressbar",
                        background=GREEN, troughcolor=BG3, borderwidth=0, thickness=14)
        self._pbar = ttk.Progressbar(prog_frame, style="104.Horizontal.TProgressbar",
                                     maximum=100, value=0, length=400)
        self._pbar.pack(fill="x", pady=2)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=20, pady=6)

        # ── Recent hits log ──────────────────────────────────────────────────
        log_frame = tk.Frame(self, bg=BG, padx=20)
        log_frame.pack(fill="both", expand=True)
        tk.Label(log_frame, text="SON DISCORD HİTLERİ (hitsdc.txt)", bg=BG, fg=TEXT2,
                 font=("Consolas", 9, "bold")).pack(anchor="w")

        text_frame = tk.Frame(log_frame, bg=BG3)
        text_frame.pack(fill="both", expand=True, pady=4)

        self._log = tk.Text(
            text_frame, bg=BG3, fg=GREEN, insertbackground=ACCENT,
            font=("Consolas", 9), relief="flat", padx=8, pady=6,
            wrap="word", state="disabled"
        )
        scrollbar = tk.Scrollbar(text_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        # ── Status bar ───────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Başlatılıyor...")
        status_bar = tk.Frame(self, bg=BG3, pady=4)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self._status_var, bg=BG3, fg=TEXT2,
                 font=("Consolas", 9), padx=10).pack(side="left")

    def _refresh(self):
        now = time.time()
        self._clock_var.set(datetime.now().strftime("%H:%M:%S"))

        cp = read_checkpoint()
        checked     = cp.get("checked", 0)
        total       = cp.get("total", 0)
        target_hits = cp.get("target_hits", 0)
        hits        = cp.get("hits", 0)
        two_fa      = cp.get("two_fa", 0)
        dc_hits     = count_lines(HITSDC)

        # CPM
        elapsed = now - self._start_real_time
        delta_checked = checked - self._prev_checked
        cpm = int((delta_checked / max(0.001, now - self._last_refresh)) * 60) if delta_checked > 0 else 0
        self._prev_checked  = checked
        self._last_refresh  = now

        pct = (checked / total * 100) if total > 0 else 0

        # Update cards
        self._cards["KONTROL EDİLEN"].update_value(f"{checked:,}")
        self._cards["TOPLAM HESAP"].update_value(f"{total:,}" if total else "—")
        self._cards["HIT"].update_value(f"{hits:,}", GREEN)
        self._cards["TARGET HIT"].update_value(f"{target_hits:,}", PURPLE)
        self._cards["2FA KİLİTLİ"].update_value(f"{two_fa:,}", ORANGE)
        self._cards["DC GÖNDERİLEN"].update_value(f"{dc_hits:,}", GOLD)
        self._cards["HIZ (CPM)"].update_value(f"{cpm:,}" if cpm else "—")
        self._cards["İLERLEME"].update_value(f"{pct:.1f}%" if total else "—")

        # Progress bar
        self._pbar["value"] = pct

        # Recent hits log
        recent = read_recent_hits(15)
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        if recent:
            for line in recent:
                self._log.insert("end", line + "\n")
        else:
            self._log.insert("end", "Henüz Discord'a gönderilmiş hit yok...\n")
        self._log.see("end")
        self._log.configure(state="disabled")

        # Status bar
        ts = datetime.now().strftime("%H:%M:%S")
        self._status_var.set(
            f"[{ts}]  Checker çalışıyor  |  "
            f"Hit oranı: {(hits/max(1,checked)*100):.2f}%  |  "
            f"Çalışma süresi: {int(elapsed//3600):02d}:{int((elapsed%3600)//60):02d}:{int(elapsed%60):02d}"
        )

    def _schedule_refresh(self):
        self._refresh()
        self.after(REFRESH_MS, self._schedule_refresh)


if __name__ == "__main__":
    app = Dashboard()
    app.mainloop()
