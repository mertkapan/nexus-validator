"""
Result Persistence and Telemetry Exporter
Supports instant hit streaming, filtered target hits, clean combo lists,
and multi-format final reports (TXT, JSON, CSV).
"""

import os
import csv
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from nexus.config import RESULTS_DIR


def extract_clean_game_names(games: List[Dict[str, Any]]) -> str:
    """Extracts comma-separated list of real game titles from games array."""
    if not games:
        return "None"
    names = [
        g.get("name", "").replace("\ufffd", "").strip()
        for g in games
        if g.get("name") and not g.get("name", "").startswith("AppID ")
    ]
    if not names:
        names = [g.get("name", "").strip() for g in games if g.get("name")]
    return ", ".join(names) if names else "None"


class ResultExporter:
    """Manages writing validation records into disk storage with strict filtering."""

    def __init__(self, output_dir: Path = RESULTS_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Primary clean hits files: ONLY verified direct logins with paid target games
        self.hits_file = self.output_dir / "hits.txt"
        self.hits_combos_file = self.output_dir / "hits_combos_only.txt"
        self.hits_detailed_file = self.output_dir / "hits_detailed.txt"
        
        # Auxiliary files
        self.hits_all_paid_file = self.output_dir / "hits_all_paid.txt"
        self.free_file = self.output_dir / "free.txt"
        self.guarded_file = self.output_dir / "guarded_2fa.txt"
        self.invalid_file = self.output_dir / "invalid.txt"

        self.recorded_target_hits = 0
        self.recorded_total_hits = 0

    def record_target_hit(self, item: Dict[str, Any], matched_targets: List[Dict[str, Any]]):
        """
        Records a confirmed high-value target HIT immediately to hits.txt and hits_combos_only.txt.
        Strictly applies only to verified direct logins with paid target games.
        """
        account = item.get("account", "")
        username = item.get("username", "")
        password = item.get("password", "")
        total_games = item.get("total_games", 0)
        paid_games = item.get("paid_games", 0)
        vac = "BANNED" if item.get("vac_banned") else "CLEAN"
        country = item.get("country", "🌐 Global")
        location = item.get("location", "")
        wallet = item.get("wallet", "")
        wallet_tag = f" | Wallet: {wallet}" if wallet else ""
        loc_tag = f" ({location})" if location else ""

        target_names = [tg.get("name", "") for tg in matched_targets if tg.get("name")]
        targets_str = ", ".join(target_names) if target_names else "Target Game"

        all_games = item.get("games", [])
        all_games_str = extract_clean_game_names(all_games)

        # 1. Primary Clean Hits File: formatted line
        clean_line = (
            f"{account} | TARGETS: [{targets_str}] | "
            f"Paid Games: {paid_games}/{total_games} | "
            f"VAC: {vac}{wallet_tag} | Country: {country}{loc_tag}\n"
        )
        with open(self.hits_file, "a", encoding="utf-8") as f:
            f.write(clean_line)

        # 2. Combo-only File: user:pass only
        with open(self.hits_combos_file, "a", encoding="utf-8") as f:
            f.write(f"{account}\n")

        # 3. Detailed Dossier File
        with open(self.hits_detailed_file, "a", encoding="utf-8") as f:
            f.write("=" * 65 + "\n")
            f.write(f"Account: {account}\n")
            f.write(f"Status: CONFIRMED DIRECT HIT (High-Value Target)\n")
            f.write(f"SteamID: {item.get('steamid', 'N/A')}\n")
            f.write(f"Persona: {item.get('persona_name', 'N/A')}\n")
            f.write(f"Country: {country}{loc_tag}\n")
            if wallet:
                f.write(f"Wallet Balance: {wallet}\n")
            f.write(f"Total Games: {total_games} (Paid: {paid_games})\n")
            f.write(f"VAC Status: {vac}\n")
            f.write(f"Matched Target Games:\n")
            for tg in matched_targets:
                h = tg.get("hours", "0")
                f.write(f"  ⭐ {tg.get('name')} ({h} hrs) [Paid]\n")
            if all_games:
                f.write(f"All Owned Games ({len(all_games)}):\n")
                for idx, g in enumerate(all_games, 1):
                    tier = "Free" if g.get("is_free") else "Paid"
                    h = g.get("hours", "0")
                    f.write(f"  [{idx:02d}] {g.get('name')} ({h} hrs) [{tier}]\n")
            f.write("=" * 65 + "\n\n")

        self.recorded_target_hits += 1

    def record_item_live(self, item: Dict[str, Any]):
        """
        Logs secondary and categorized outcomes (general paid hits, 2FA, Free, Invalid).
        Note: hits.txt is reserved exclusively for record_target_hit.
        """
        status = item.get("status", "")
        account = item.get("account", "")
        total_games = item.get("total_games", 0)
        paid_games = item.get("paid_games", 0)
        vac = "BANNED" if item.get("vac_banned") else "CLEAN"
        country = item.get("country", "🌐 Global")
        location = item.get("location", "")
        wallet = item.get("wallet", "")
        wallet_tag = f" | Wallet: {wallet}" if wallet else ""
        loc_tag = f" ({location})" if location else ""

        games = item.get("games", [])
        games_list_str = extract_clean_game_names(games)

        if status == "HIT":
            self.recorded_total_hits += 1
            # Record into hits_all_paid.txt
            line = f"{account} | Total Games: {total_games} (Paid: {paid_games}) | Games: [{games_list_str}] | Country: {country}{loc_tag} | VAC: {vac}{wallet_tag}\n"
            with open(self.hits_all_paid_file, "a", encoding="utf-8") as f:
                f.write(line)

        elif status == "2FA_HIT":
            # Record into guarded_2fa.txt only - DO NOT pollute hits.txt
            line = f"{account} | Status: 2FA / Steam Guard | Total Games: {total_games} (Paid: {paid_games}) | Games: [{games_list_str}] | Country: {country}{loc_tag} | VAC: {vac}{wallet_tag}\n"
            with open(self.guarded_file, "a", encoding="utf-8") as f:
                f.write(line)

        elif status == "FREE":
            # Record into free.txt only - DO NOT pollute hits.txt
            line = f"{account} | Status: Free Tier / 0 Games | Total Games: {total_games} | Games: [{games_list_str}] | Country: {country}{loc_tag}{wallet_tag}\n"
            with open(self.free_file, "a", encoding="utf-8") as f:
                f.write(line)

    def finalize_validation_batch(
        self,
        total_checked: int,
        total_hits: int,
        target_hits: int,
        two_fa_count: int,
        invalid_count: int,
        elapsed_sec: float
    ) -> Path:
        """
        Generates final consolidated summary report and syncs hits.txt to root directory.
        Called when account queue completes.
        """
        summary_file = self.output_dir / "FINAL_HITS_SUMMARY.txt"
        cpm = int((total_checked / max(0.001, elapsed_sec)) * 60)

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("      NEXUS PLATFORM AUTHENTICATION VALIDATION - FINAL REPORT\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"Total Accounts Processed : {total_checked:,}\n")
            f.write(f"Direct Login Target Hits : {target_hits:,} (High-Value Paid Target Games)\n")
            f.write(f"All Paid Login Hits      : {total_hits:,}\n")
            f.write(f"Steam Guard (2FA) Locked : {two_fa_count:,}\n")
            f.write(f"Invalid Credentials      : {invalid_count:,}\n")
            f.write(f"Average Throughput       : {cpm:,} CPM\n")
            f.write(f"Total Elapsed Time       : {int(elapsed_sec)} seconds\n\n")
            f.write("Generated Output Files:\n")
            f.write(f"  • Target Hits TXT      : {self.hits_file.name}\n")
            f.write(f"  • User:Pass Combos TXT : {self.hits_combos_file.name}\n")
            f.write(f"  • Detailed Dossiers    : {self.hits_detailed_file.name}\n")
            f.write(f"  • All Paid Hits TXT    : {self.hits_all_paid_file.name}\n")
            f.write(f"  • Steam Guard Locked   : {self.guarded_file.name}\n")
            f.write(f"  • Free/Zero Library    : {self.free_file.name}\n\n")
            f.write("=" * 70 + "\n")

        # Copy hits.txt to workspace root for instant accessibility
        root_hits = Path("hits.txt")
        try:
            if self.hits_file.exists():
                shutil.copyfile(self.hits_file, root_hits)
        except Exception as e:
            print(f"[EXPORTER] Notice copying root hits.txt: {e}")

        return summary_file

    def export_hits_custom(self, items: List[Dict[str, Any]], target_path: Path):
        """Exports verified HIT accounts with games count and all games written out."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            for it in items:
                if it.get("status") == "HIT":
                    acc = it.get("account", "")
                    tg = it.get("total_games", 0)
                    pg = it.get("paid_games", 0)
                    vac = "BANNED" if it.get("vac_banned") else "CLEAN"
                    country = it.get("country", "🌐 Global")
                    wallet = it.get("wallet", "")
                    w_str = f" | Wallet: {wallet}" if wallet else ""
                    g_names = extract_clean_game_names(it.get("games", []))
                    f.write(f"{acc} | Total Games: {tg} (Paid: {pg}) | Games: [{g_names}] | Country: {country} | VAC: {vac}{w_str}\n")

    def export_all_csv(self, items: List[Dict[str, Any]], target_path: Path):
        """Exports tabular summary into CSV format with full games list."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "account", "status", "total_games", "paid_games", "games_list",
            "wallet", "country", "location", "vac_banned", "ping_ms", "proxy", "details"
        ]
        with open(target_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for it in items:
                row_copy = dict(it)
                row_copy["games_list"] = extract_clean_game_names(it.get("games", []))
                writer.writerow(row_copy)

    def export_all_json(self, items: List[Dict[str, Any]], target_path: Path):
        """Exports all items as structured JSON."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
