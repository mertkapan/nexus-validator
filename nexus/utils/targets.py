"""
High-Value Target Game Matching Engine
Audits account inventory against user-specified target games and franchises
(FIFA, EA FC, GTA, RDR, CoD, Mortal Kombat, Street Fighter, Cyberpunk,
Witcher, Baldur's Gate, Elden Ring, Wallpaper Engine, F1, NBA 2K, etc.).
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set

# Regex to strip symbols, edition tags, and normalize spaces
RE_CLEAN = re.compile(r"[^a-zA-Z0-9 ]+")

def normalize_title(text: str) -> str:
    """Normalizes game title for high-precision, accent-insensitive matching."""
    if not text:
        return ""
    # Strip trademark, registered, copyright symbols & punctuation
    clean = RE_CLEAN.sub(" ", text).lower()
    return " ".join(clean.split())


class TargetGameMatcher:
    """Singleton matcher pre-caching 3,000+ high-value target titles and franchise keywords."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TargetGameMatcher, cls).__new__(cls)
            cls._instance._init_database()
        return cls._instance

    def _init_database(self):
        self.titles_set: Set[str] = set()
        self.words_index: Set[str] = set()
        self.sorted_targets: List[str] = []

        # High-priority core franchise roots for fuzzy/prefix/subtitle matching
        self.core_franchises: List[str] = [
            "wallpaper engine", "fifa", "ea sports fc", "ea sports",
            "pro evolution soccer", "pes", "winning eleven",
            "grand theft auto", "gta", "red dead", "rdr",
            "mortal kombat", "street fighter", "tekken",
            "elden ring", "dark souls", "bloodborne", "sekiro",
            "baldur s gate", "baldurs gate", "cyberpunk 2077", "the witcher", "witcher",
            "call of duty", "black ops", "modern warfare", "warzone",
            "battlefield", "assassin s creed", "assassins creed",
            "far cry", "god of war", "marvel s spider man", "spider man",
            "horizon zero dawn", "horizon forbidden west", "uncharted",
            "resident evil", "silent hill", "dead space",
            "fallout", "the elder scrolls", "elder scrolls", "skyrim", "oblivion", "morrowind",
            "star wars", "mass effect", "dragon age", "kotor",
            "forza", "gran turismo", "need for speed", "f1", "wrc", "motogp",
            "nba 2k", "wwe 2k", "madden nfl", "nhl",
            "half life", "portal", "left 4 dead",
            "dishonored", "bioshock", "deus ex", "borderlands",
            "diablo", "warcraft", "starcraft", "doom", "wolfenstein",
            "metro 2033", "metro last light", "metro exodus",
            "divinity original sin", "pillars of eternity", "wasteland",
            "deponia", "syberia", "machinarium", "command conquer"
        ]

        # Candidate paths for target_games.json
        candidate_paths = [
            Path(__file__).parent / "target_games.json",
            Path(getattr(sys, "_MEIPASS", ".")) / "nexus" / "utils" / "target_games.json",
            Path.cwd() / "nexus" / "utils" / "target_games.json",
            Path.cwd() / "target_games.json",
        ]

        loaded = False
        for p in candidate_paths:
            if p.is_file():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    raw_titles = data.get("titles", [])
                    for t in raw_titles:
                        norm = normalize_title(t)
                        if norm and len(norm) >= 2:
                            self.titles_set.add(norm)
                            for w in norm.split():
                                if len(w) >= 3 and not w.isdigit():
                                    self.words_index.add(w)

                    loaded = True
                    break
                except Exception as e:
                    print(f"[TARGETS] Notice loading {p}: {e}")

        # Fallback to core franchises if JSON unavailable
        for cf in self.core_franchises:
            self.titles_set.add(cf)
            for w in cf.split():
                if len(w) >= 3 and not w.isdigit():
                    self.words_index.add(w)

        # Pre-sort targets by descending length for longest-match substring matching
        self.sorted_targets = sorted(list(self.titles_set), key=lambda x: -len(x))

    def is_target_game(self, game_name: str, is_free: bool = False) -> bool:
        """
        Determines if a single game title matches the target whitelist.
        Free-to-play games are automatically rejected.
        """
        if is_free:
            return False

        norm_name = normalize_title(game_name)
        if not norm_name or len(norm_name) < 2:
            return False

        # 1. Instant O(1) exact match
        if norm_name in self.titles_set:
            return True

        # 2. Fast check for core franchise keywords
        for cf in self.core_franchises:
            if cf in norm_name or norm_name in cf:
                return True

        # 3. Word intersection quick-filter before substring scan
        game_words = set(norm_name.split())
        if not game_words.intersection(self.words_index):
            return False

        # 4. Substring containment check against full target list
        for t in self.sorted_targets:
            if len(t) >= 4 and (t in norm_name or norm_name in t):
                return True

        return False

    def evaluate_account(self, record: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Evaluates a verified account record.
        Criteria:
        - Status must be 'HIT' (verified direct password login, non-2FA)
        - Must have at least one paid game (paid_games > 0)
        - At least one paid game must match the requested target whitelist
        Returns: (is_qualified, list_of_matching_games)
        """
        status = record.get("status", "")
        # Strictly direct login hits only (exclude 2FA, FREE, INVALID, ERROR)
        if status != "HIT":
            return False, []

        paid_count = record.get("paid_games", 0)
        if paid_count <= 0:
            return False, []

        games = record.get("games", [])
        if not games:
            return False, []

        matched_games = []
        for g in games:
            g_name = g.get("name", "")
            is_free = g.get("is_free", False)
            if self.is_target_game(g_name, is_free=is_free):
                matched_games.append(g)

        return (len(matched_games) > 0), matched_games


# Singleton accessor functions
_matcher: TargetGameMatcher = TargetGameMatcher()

def evaluate_target_account(record: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Helper wrapper for evaluating whether an account meets the target criteria."""
    return _matcher.evaluate_account(record)

def is_target_game(game_name: str, is_free: bool = False) -> bool:
    """Helper wrapper for checking a single game title."""
    return _matcher.is_target_game(game_name, is_free=is_free)
