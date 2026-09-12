"""
Persistent Asynchronous Transport and Session Connection Pool
Maintains high-performance TCP/TLS connection reuse across rotating proxy endpoints.
Prevents Windows socket exhaustion ([WinError 10048] WSAEADDRINUSE) and eliminates handshake latency.
"""

import asyncio
from typing import Dict, Optional
import aiohttp

try:
    from aiohttp_socks import ProxyConnector
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False

from nexus.core.proxy_pool import NetworkRelay


class SessionTransportPool:
    """
    Manages persistent ClientSession instances with connection pooling and keep-alive.
    Recycles HTTP/HTTPS sessions dynamically and caches SOCKS connectors per proxy endpoint.
    """

    def __init__(self, pool_limit: int = 150):
        self.pool_limit = pool_limit
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._socks_sessions: Dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()
        self._is_closed = False

    def _get_http_session(self) -> aiohttp.ClientSession:
        if self._http_session is None or self._http_session.closed:
            connector = aiohttp.TCPConnector(
                ssl=False,
                limit=400,
                limit_per_host=50,
                ttl_dns_cache=300,
                keepalive_timeout=30.0,
                enable_cleanup_closed=True
            )
            self._http_session = aiohttp.ClientSession(
                connector=connector
            )
        return self._http_session

    async def get_session(self, relay: Optional[NetworkRelay]) -> aiohttp.ClientSession:
        """Returns optimal persistent session with connection reuse for the given relay."""
        if not relay or not relay.scheme.startswith("socks") or not SOCKS_AVAILABLE:
            return self._get_http_session()

        # For SOCKS relays, cache session by relay URL to reuse SOCKS tunnel
        key = relay.url
        async with self._lock:
            if key in self._socks_sessions and not self._socks_sessions[key].closed:
                return self._socks_sessions[key]

            # Prune if exceeded pool limit
            if len(self._socks_sessions) >= self.pool_limit:
                # Remove first item
                keys = list(self._socks_sessions.keys())
                if keys:
                    old_k = keys[0]
                    old_sess = self._socks_sessions.pop(old_k, None)
                    if old_sess and not old_sess.closed:
                        try:
                            await old_sess.close()
                        except Exception:
                            pass

            try:
                connector = ProxyConnector.from_url(relay.url)
                sess = aiohttp.ClientSession(connector=connector)
                self._socks_sessions[key] = sess
                return sess
            except Exception:
                # Fallback to standard HTTP session if SOCKS connector instantiation fails
                return self._get_http_session()

    async def close_all(self):
        """Closes all cached sessions cleanly upon engine shutdown."""
        self._is_closed = True
        if self._http_session and not self._http_session.closed:
            try:
                await self._http_session.close()
            except Exception:
                pass

        async with self._lock:
            for sess in list(self._socks_sessions.values()):
                if not sess.closed:
                    try:
                        await sess.close()
                    except Exception:
                        pass
            self._socks_sessions.clear()
