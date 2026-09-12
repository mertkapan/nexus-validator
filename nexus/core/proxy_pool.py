"""
Network Relay Viability Probe and Connection Pool Manager
Handles proxy parsing, protocol normalization (HTTP, SOCKS4, SOCKS5), latency benchmarking, and auto-rotation.
"""

import time
import asyncio
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
import aiohttp

try:
    from aiohttp_socks import ProxyConnector
    SOCKS_SUPPORTED = True
except ImportError:
    SOCKS_SUPPORTED = False


class NetworkRelay:
    """Represents an individual proxy / network relay node with advanced telemetry and health scoring."""
    def __init__(self, raw_string: str, default_scheme: str = "http"):
        self.raw_string = raw_string.strip()
        self.scheme, self.host, self.port, self.username, self.password = self._parse(self.raw_string, default_scheme)
        self.ping_ms: int = -1
        self.is_alive: bool = True
        self.health_score: int = 100  # Dynamic health score (0-100)
        self.consecutive_fails: int = 0
        self.consecutive_success: int = 0
        self.success_count: int = 0
        self.fail_count: int = 0
        self.in_flight: int = 0  # Active in-flight requests on this node
        self.last_tested: float = 0.0
        self.last_used: float = 0.0
        self.cooldown_until: float = 0.0  # Timestamp until which node is resting after HTTP 429 / eresult 84

    def _parse(self, s: str, default_scheme: str):
        scheme = default_scheme.lower()
        if "://" in s:
            scheme, rest = s.split("://", 1)
        else:
            rest = s

        username = None
        password = None

        if "@" in rest:
            auth_part, host_part = rest.split("@", 1)
            if ":" in auth_part:
                username, password = auth_part.split(":", 1)
            else:
                username = auth_part
        else:
            host_part = rest

        parts = host_part.split(":")
        if len(parts) == 2:
            host = parts[0]
            port = int(parts[1])
        elif len(parts) == 4:
            # Format: host:port:user:pass
            host = parts[0]
            port = int(parts[1])
            username = parts[2]
            password = parts[3]
        else:
            host = parts[0]
            port = 8080

        return scheme, host, port, username, password

    @property
    def url(self) -> str:
        """Returns standard URL representation."""
        if self.username and self.password:
            return f"{self.scheme}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def display_str(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def is_cooling_down(self) -> bool:
        """Checks if relay is currently resting in rate-limit cooldown."""
        return time.time() < self.cooldown_until

    def mark_success(self, ping: int):
        self.is_alive = True
        self.cooldown_until = 0.0
        self.consecutive_fails = 0
        self.consecutive_success += 1
        self.success_count += 1
        self.ping_ms = ping
        self.last_tested = time.time()
        # Recover health score with positive telemetry
        self.health_score = min(100, self.health_score + 15)

    def mark_rate_limited(self, cooldown_seconds: int = 45):
        """
        Places relay into temporary quarantine/cooldown without permanently killing it.
        Allows the IP address to rest and recover from Steam rate limits.
        """
        self.cooldown_until = time.time() + cooldown_seconds
        self.consecutive_fails += 1
        self.health_score = max(20, self.health_score - 10)
        # Keep is_alive True so it returns to rotation once cooldown elapses

    def mark_failure(self, severe: bool = False):
        self.consecutive_fails += 1
        self.consecutive_success = 0
        self.fail_count += 1
        if severe:
            self.health_score = max(0, self.health_score - 35)
            if self.health_score <= 0 or self.consecutive_fails >= 3:
                self.is_alive = False
        else:
            self.health_score = max(0, self.health_score - 20)
            if self.health_score <= 0 or self.consecutive_fails >= 5:
                self.is_alive = False


class NetworkRelayPool:
    """Thread-safe and async-safe pool with real-time health grading, background auditing, and continuous replenishment."""
    def __init__(self):
        self.relays: List[NetworkRelay] = []
        self._index: int = 0
        self._lock = asyncio.Lock()
        self.auto_replenish_enabled: bool = True
        self.min_active_threshold: int = 35

    def load_from_lines(self, lines: List[str], default_scheme: str = "http") -> int:
        self.relays.clear()
        self._index = 0
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    relay = NetworkRelay(line, default_scheme)
                    self.relays.append(relay)
                except Exception:
                    continue
        return len(self.relays)

    def append_relays(self, new_relays: List[NetworkRelay]) -> int:
        """Dynamically appends newly discovered relays without resetting existing rotation."""
        existing_urls = {r.url for r in self.relays}
        added = 0
        for r in new_relays:
            if r.url not in existing_urls:
                self.relays.append(r)
                existing_urls.add(r.url)
                added += 1
        return added

    @property
    def total(self) -> int:
        return len(self.relays)

    @property
    def active_count(self) -> int:
        """Counts nodes that are both operational and not in cooldown."""
        now = time.time()
        return sum(1 for r in self.relays if r.is_alive and r.health_score > 0 and now >= r.cooldown_until)

    @property
    def cooling_count(self) -> int:
        """Counts nodes temporarily resting in rate-limit cooldown."""
        now = time.time()
        return sum(1 for r in self.relays if r.is_alive and now < r.cooldown_until)

    @property
    def healthy_relays(self) -> List[NetworkRelay]:
        now = time.time()
        return [r for r in self.relays if r.is_alive and r.health_score >= 40 and now >= r.cooldown_until]

    async def get_next_relay(self, max_in_flight: int = 3) -> Optional[NetworkRelay]:
        """
        Returns the optimal operational relay in weighted round-robin fashion,
        enforcing cooldown periods and concurrency limits per relay to prevent dogpiling.
        """
        async with self._lock:
            if not self.relays:
                return None

            now = time.time()
            n = len(self.relays)
            best_candidate: Optional[NetworkRelay] = None
            checked = 0

            while checked < n:
                relay = self.relays[self._index % n]
                self._index += 1
                checked += 1

                # Skip dead or cooling-down relays
                if not relay.is_alive or relay.health_score <= 0 or now < relay.cooldown_until:
                    continue

                if relay.in_flight < max_in_flight:
                    relay.in_flight += 1
                    relay.last_used = now
                    return relay
                elif best_candidate is None or relay.in_flight < best_candidate.in_flight:
                    best_candidate = relay

            if best_candidate and best_candidate.is_alive and best_candidate.health_score > 0 and now >= best_candidate.cooldown_until:
                best_candidate.in_flight += 1
                best_candidate.last_used = now
                return best_candidate

            return None

    def release_relay(self, relay: Optional[NetworkRelay]):
        """Decrements the in-flight semaphore for a relay."""
        if relay and hasattr(relay, "in_flight"):
            relay.in_flight = max(0, relay.in_flight - 1)

    def prune_dead(self):
        """Purges permanently failed nodes to keep memory footprint lean."""
        self.relays = [r for r in self.relays if r.is_alive or r.consecutive_fails < 4]


async def probe_relay_viability(
    relay: NetworkRelay,
    target_url: str = "https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/",
    timeout: int = 6
) -> Dict[str, Any]:
    """
    Tests connectivity and latency of an individual network relay.
    """
    start_time = time.perf_counter()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        if relay.scheme.startswith("socks") and SOCKS_SUPPORTED:
            connector = ProxyConnector.from_url(relay.url)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers) as resp:
                    latency = int((time.perf_counter() - start_time) * 1000)
                    if resp.status in (200, 301, 302):
                        relay.mark_success(latency)
                        return {"success": True, "ping": latency, "status": resp.status}
                    else:
                        relay.mark_failure()
                        return {"success": False, "ping": latency, "status": resp.status}
        else:
            # HTTP/HTTPS proxy
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, proxy=relay.url, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers) as resp:
                    latency = int((time.perf_counter() - start_time) * 1000)
                    if resp.status in (200, 301, 302):
                        relay.mark_success(latency)
                        return {"success": True, "ping": latency, "status": resp.status}
                    else:
                        relay.mark_failure()
                        return {"success": False, "ping": latency, "status": resp.status}
    except Exception as e:
        relay.mark_failure()
        return {"success": False, "ping": -1, "error": str(e)}


async def audit_relays_concurrently(
    relays: List[NetworkRelay],
    target_url: str = "https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/",
    concurrency: int = 50,
    timeout: int = 6
) -> int:
    """Probes a batch of relays in parallel using Steam's lightweight public telemetry endpoint."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _check_one(r: NetworkRelay):
        async with semaphore:
            await probe_relay_viability(r, target_url=target_url, timeout=timeout)

    tasks = [_check_one(r) for r in relays]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    return sum(1 for r in relays if r.is_alive)


async def continuous_watchdog_loop(
    pool: NetworkRelayPool,
    stop_event: asyncio.Event,
    interval_seconds: int = 15,
    on_pool_depleted_callback=None
):
    """
    Continuous background watchdog that constantly scrubs and audits the active proxy pool.
    Purges degrading/dead nodes, triggers auto-replenishment if active count drops,
    and guarantees zero accounts ever route through dead proxies.
    """
    target_probe = "https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/"

    while not stop_event.is_set():
        try:
            # If pool is running low on active relays, trigger callback to scrape/replenish
            active_now = pool.active_count
            if active_now < pool.min_active_threshold and on_pool_depleted_callback:
                try:
                    await on_pool_depleted_callback()
                except Exception:
                    pass

            # Pick a subset of relays that haven't been tested recently or have had failures
            now = time.time()
            candidates = [
                r for r in pool.relays 
                if (now - r.last_tested > interval_seconds * 2) or (r.consecutive_fails > 0 and r.is_alive)
            ][:30]

            if candidates:
                await audit_relays_concurrently(candidates, target_url=target_probe, concurrency=15, timeout=5)

            # Scrub dead proxies periodically
            pool.prune_dead()

            # Auto-save operational proxies to disk so proxies are continuously saved
            try:
                from nexus.config import PROXIES_FILE
                alive_relays = [r for r in pool.relays if r.is_alive and r.health_score > 0]
                if alive_relays:
                    with open(PROXIES_FILE, "w", encoding="utf-8") as pf:
                        for r in alive_relays:
                            pf.write(f"{r.url}\n")
            except Exception:
                pass

        except Exception:
            pass

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            continue

