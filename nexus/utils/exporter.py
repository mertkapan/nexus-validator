"""
Result Persistence and Telemetry Exporter
Supports instant hit streaming and multi-format batch exports (TXT, JSON, CSV).
"""

import os
import csv
import json
from pathlib import Path
from typing import List, Dict, Any

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
    """Manages writing validation records into disk storage."""

    def __init__(self, output_dir: Path = RESULTS_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hits_file = self.output_dir / "hits.txt"
        self.hits_detailed_file = self.output_dir / "hits_detailed.txt"
        self.free_file = self.output_dir / "free.txt"
        self.guarded_file = self.output_dir / "guarded.txt"
        self.invalid_file = self.output_dir / "invalid.txt"

    def record_item_live(self, item: Dict[str, Any]):
        """Appends verified items to disk immediately upon verification with full game lists."""
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
            # Exact format requested: credentials | total games count | written games list
            line = f"{account} | Total Games: {total_games} (Paid: {paid_games}) | Games: [{games_list_str}] | Country: {country}{loc_tag} | VAC: {vac}{wallet_tag}\n"
            with open(self.hits_file, "a", encoding="utf-8") as f:
                f.write(line)

            # Detailed dossier format
            with open(self.hits_detailed_file, "a", encoding="utf-8") as f:
                f.write("=" * 65 + "\n")
                f.write(f"Account: {account}\n")
                f.write(f"Status: HIT (Paid Access)\n")
                f.write(f"SteamID: {item.get('steamid', 'N/A')}\n")
                f.write(f"Persona: {item.get('persona_name', 'N/A')}\n")
                f.write(f"Country: {country}{loc_tag}\n")
                if wallet:
                    f.write(f"Wallet: {wallet}\n")
                f.write(f"Total Games: {total_games} (Paid: {paid_games})\n")
                f.write(f"VAC Status: {vac}\n")
                if games:
                    f.write("Games List:\n")
                    for idx, g in enumerate(games, 1):
                        g_type = "Free" if g.get("is_free") else "Paid"
                        h = g.get("hours", "0")
                        f.write(f"  [{idx}] {g.get('name')} ({h} hrs) [{g_type}]\n")
                f.write("=" * 65 + "\n\n")

        elif status == "2FA_HIT":
            line = f"{account} | Status: 2FA / Steam Guard | Total Games: {total_games} (Paid: {paid_games}) | Games: [{games_list_str}] | Country: {country}{loc_tag} | VAC: {vac}{wallet_tag}\n"
            with open(self.guarded_file, "a", encoding="utf-8") as f:
                f.write(line)
            # Also register in general hits file
            with open(self.hits_file, "a", encoding="utf-8") as f:
                f.write(line)

            # Detailed dossier format for 2FA hit
            with open(self.hits_detailed_file, "a", encoding="utf-8") as f:
                f.write("=" * 65 + "\n")
                f.write(f"Account: {account}\n")
                f.write(f"Status: 2FA / Steam Guard Active (Valid Password)\n")
                f.write(f"SteamID: {item.get('steamid', 'N/A')}\n")
                f.write(f"Persona: {item.get('persona_name', 'N/A')}\n")
                f.write(f"Country: {country}{loc_tag}\n")
                if wallet:
                    f.write(f"Wallet: {wallet}\n")
                f.write(f"Total Games: {total_games} (Paid: {paid_games})\n")
                f.write(f"VAC Status: {vac}\n")
                if games:
                    f.write("Games List:\n")
                    for idx, g in enumerate(games, 1):
                        g_type = "Free" if g.get("is_free") else "Paid"
                        h = g.get("hours", "0")
                        f.write(f"  [{idx}] {g.get('name')} ({h} hrs) [{g_type}]\n")
                f.write("=" * 65 + "\n\n")

        elif status == "FREE":
            line = f"{account} | Status: Free Tier / 0 Games | Total Games: {total_games} | Games: [{games_list_str}] | Country: {country}{loc_tag}{wallet_tag}\n"
            with open(self.free_file, "a", encoding="utf-8") as f:
                f.write(line)
            with open(self.hits_file, "a", encoding="utf-8") as f:
                f.write(line)

    def export_hits_custom(self, items: List[Dict[str, Any]], target_path: Path):
        """Exports verified HIT accounts with games count and all games written out."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            for it in items:
                if it.get("status") in ("HIT", "2FA_HIT"):
                    acc = it.get("account", "")
                    tg = it.get("total_games", 0)
                    pg = it.get("paid_games", 0)
                    vac = "BANNED" if it.get("vac_banned") else "CLEAN"
                    country = it.get("country", "🌐 Global")
                    wallet = it.get("wallet", "")
                    w_str = f" | Wallet: {wallet}" if wallet else ""
                    g_names = extract_clean_game_names(it.get("games", []))
                    f.write(f"{acc} | Total Games: {tg} (Paid: {pg}) | Games: [{g_names}] | Country: {country} | VAC: {vac}{w_str}\n")

    def export_hits_detailed(self, items: List[Dict[str, Any]], target_path: Path):
        """Exports verified HIT accounts into full structured dossiers."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("=================================================================\n")
            f.write("         NEXUS PLATFORM TELEMETRY - VERIFIED ACCOUNTS DOSSIER    \n")
            f.write("=================================================================\n\n")
            for it in items:
                if it.get("status") in ("HIT", "2FA_HIT"):
                    f.write(f"Account: {it.get('account')}\n")
                    f.write(f"Status: {it.get('status')}\n")
                    f.write(f"SteamID: {it.get('steamid', 'N/A')}\n")
                    f.write(f"Persona: {it.get('persona_name', 'N/A')}\n")
                    f.write(f"Country: {it.get('country', '🌐 Global')} | Location: {it.get('location', 'N/A')}\n")
                    if it.get("wallet"):
                        f.write(f"Wallet Balance: {it.get('wallet')}\n")
                    f.write(f"Total Games: {it.get('total_games', 0)} (Paid: {it.get('paid_games', 0)})\n")
                    f.write(f"VAC Status: {'BANNED' if it.get('vac_banned') else 'CLEAN'}\n")
                    games = it.get("games", [])
                    if games:
                        f.write("Owned Games:\n")
                        for idx, g in enumerate(games, 1):
                            tier = "Free" if g.get("is_free") else "Paid"
                            f.write(f"  {idx:02d}. {g.get('name')} ({g.get('hours', 0)} hrs) [{tier}]\n")
                    f.write("-" * 65 + "\n\n")

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
