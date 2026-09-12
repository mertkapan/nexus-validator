"""
Automated Multi-Source Network Relay Scraper and Live Pool Builder
Fetches fresh, public HTTP, SOCKS4, and SOCKS5 proxies from verified open-source endpoints,
deduplicates them, benchmarks viability against target service endpoints, and populates the active pool.
"""

import re
import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional
import aiohttp

from nexus.core.proxy_pool import NetworkRelay, NetworkRelayPool, probe_relay_viability

logger = logging.getLogger(__name__)

# High-reliability live public proxy feed endpoints (HTTP, SOCKS4, SOCKS5)
PUBLIC_PROXY_SOURCES = [
    # Proxyscrape APIs
    {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=8000&country=all&ssl=all&anonymity=all", "scheme": "http"},
    {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=8000&country=all", "scheme": "socks4"},
    {"url": "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=8000&country=all", "scheme": "socks5"},
    # TheSpeedX Live Lists
    {"url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt", "scheme": "socks5"},
    # Monosans Repository
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt", "scheme": "socks5"},
    {"url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt", "scheme": "http"},
    # Hookzof SOCKS5
    {"url": "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt", "scheme": "socks5"},
    # ClarkeTM Proxy List
    {"url": "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", "scheme": "http"},
    # Jetkai Comprehensive Feeds
    {"url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt", "scheme": "socks5"},
    # Roosterkid OpenProxyList
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt", "scheme": "socks5"},
    # ShiftyTR Proxy Repository
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt", "scheme": "socks5"},
    # Sunny9577 Automated Scraper Feeds
    {"url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt", "scheme": "socks5"},
    # MuRongPIG Proxy-Master
    {"url": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt", "scheme": "socks5"},
    # Officialputuid KangProxy
    {"url": "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5.txt", "scheme": "socks5"},
    # Vakhov Fresh Proxy List
    {"url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt", "scheme": "socks5"},
    # Zloi-user hideip.me lists
    {"url": "https://raw.githubusercontent.com/Zloi-user/hideip.me/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/Zloi-user/hideip.me/main/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/Zloi-user/hideip.me/main/socks5.txt", "scheme": "socks5"},
    # ErcinDedeoglu Public Lists
    {"url": "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt", "scheme": "socks5"},
    # Proxifly Free Proxy List
    {"url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt", "scheme": "http"},
    # Anonym8 Proxy Lists
    {"url": "https://raw.githubusercontent.com/Anonym8/proxy-list/master/proxy-list-raw.txt", "scheme": "http"},
    # Im-Rann Proxy Lists
    {"url": "https://raw.githubusercontent.com/im-rann/latest-proxy-list/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/im-rann/latest-proxy-list/main/socks5.txt", "scheme": "socks5"},
    # Obscureproxies Daily
    {"url": "https://raw.githubusercontent.com/ObscureCode/proxy-list/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/ObscureCode/proxy-list/main/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/ObscureCode/proxy-list/main/socks5.txt", "scheme": "socks5"},
    # Uplink Proxy Live Lists
    {"url": "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/socks5.txt", "scheme": "socks5"},
    # Alien-Z Proxy
    {"url": "https://raw.githubusercontent.com/alien-z/proxy-list/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/alien-z/proxy-list/main/socks5.txt", "scheme": "socks5"},
    # Balamut Proxy Feed
    {"url": "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks5.txt", "scheme": "socks5"},
    # OpenProxy Space Live
    {"url": "https://openproxy.space/list/http", "scheme": "http"},
    {"url": "https://openproxy.space/list/socks4", "scheme": "socks4"},
    {"url": "https://openproxy.space/list/socks5", "scheme": "socks5"},
    # Prx-Checker
    {"url": "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt", "scheme": "socks4"},
    {"url": "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt", "scheme": "socks5"},
    # EndOfTheInternet
    {"url": "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt", "scheme": "http"},
    # Mertguvencli Proxy
    {"url": "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt", "scheme": "http"},
    # HyperBeast
    {"url": "https://raw.githubusercontent.com/HyperBeats/proxy-list/main/http.txt", "scheme": "http"},
    {"url": "https://raw.githubusercontent.com/HyperBeats/proxy-list/main/socks5.txt", "scheme": "socks5"},
]


IP_PORT_PATTERN = re.compile(r"(?:(?:https?|socks[45])://)?\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}\b")


async def _fetch_source(session: aiohttp.ClientSession, source: Dict[str, str], timeout_sec: int = 8) -> List[NetworkRelay]:
    """Fetches and extracts proxies from an individual source endpoint."""
    url = source["url"]
    default_scheme = source["scheme"]
    relays: List[NetworkRelay] = []

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as response:
            if response.status == 200:
                text = await response.text(errors="ignore")
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = IP_PORT_PATTERN.search(line)
                    if m:
                        candidate = m.group(0)
                        if "://" not in candidate:
                            candidate = f"{default_scheme}://{candidate}"
                        try:
                            relays.append(NetworkRelay(candidate, default_scheme=default_scheme))
                        except Exception:
                            continue
    except Exception as e:
        logger.debug(f"Source fetch failure for {url}: {e}")

    return relays


async def scrape_fresh_proxies(
    schemes: Optional[List[str]] = None,
    max_sources: Optional[int] = None,
    timeout_sec: int = 8,
    max_relays: Optional[int] = 2500
) -> List[NetworkRelay]:
    """
    Scrapes fresh proxies across all configured open-source repositories concurrently.
    Deduplicates nodes based on host:port tuple and returns top fresh nodes.
    """
    active_sources = PUBLIC_PROXY_SOURCES
    if schemes:
        schemes_lower = [s.lower() for s in schemes]
        active_sources = [s for s in active_sources if s["scheme"] in schemes_lower]

    if max_sources:
        active_sources = active_sources[:max_sources]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }

    connector = aiohttp.TCPConnector(ssl=False, limit=50)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        tasks = [_fetch_source(session, src, timeout_sec=timeout_sec) for src in active_sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    dedup: Dict[str, NetworkRelay] = {}
    for batch in results:
        if isinstance(batch, list):
            for relay in batch:
                key = f"{relay.host}:{relay.port}"
                if key not in dedup:
                    dedup[key] = relay

    all_relays = list(dedup.values())
    if max_relays and len(all_relays) > max_relays:
        return all_relays[:max_relays]
    return all_relays


async def filter_operational_proxies(
    relays: List[NetworkRelay],
    target_url: str = "https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v1/",
    concurrency: int = 80,
    timeout_sec: int = 4,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
    save_to_file: bool = True
) -> List[NetworkRelay]:
    """
    Rapidly benchmarks scraped proxies against the service endpoint to filter out dead relays.
    Returns a verified operational relay pool and automatically persists live nodes to disk.
    """
    operational: List[NetworkRelay] = []
    total = len(relays)
    tested = 0
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(concurrency)

    async def _test_relay(r: NetworkRelay):
        nonlocal tested
        async with sem:
            res = await probe_relay_viability(r, target_url=target_url, timeout=timeout_sec)
            async with lock:
                tested += 1
                if res.get("success"):
                    operational.append(r)
                if progress_callback:
                    progress_callback(tested, total, len(operational))

    tasks = [_test_relay(r) for r in relays]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Sort operational proxies by latency (lowest ping first)
    operational.sort(key=lambda r: (r.ping_ms if r.ping_ms > 0 else 9999))

    # Auto-save operational proxies to disk
    if save_to_file and operational:
        try:
            from nexus.config import PROXIES_FILE
            with open(PROXIES_FILE, "w", encoding="utf-8") as f:
                for r in operational:
                    f.write(f"{r.url}\n")
        except Exception:
            pass

    return operational
