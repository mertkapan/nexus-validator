"""
NEXUS v1.0.0 Configuration and Constants
"""

import os
from pathlib import Path

# Application Metadata
APP_NAME = "NEXUS v1.0.0"
APP_SUBTITLE = "Platform Authentication State Validator & Telemetry Suite"
VERSION = "1.0.0"

# Directories and Paths (Supports PyInstaller frozen executable and standard development)
import sys

if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(sys._MEIPASS).resolve()
else:
    EXE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = EXE_DIR

BASE_DIR = EXE_DIR
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)
CACHE_DIR = BASE_DIR / "cache"
CACHE_IMAGES_DIR = CACHE_DIR / "images"
CACHE_AVATARS_DIR = CACHE_DIR / "avatars"
CACHE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
CACHE_AVATARS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = BUNDLE_DIR / "nexus" / "ui" / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"
LOGO_PATH = ASSETS_DIR / "logo.png"
PROXIES_FILE = BASE_DIR / "proxies.txt"
CONFIG_FILE = BASE_DIR / "config.json"
CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"

import json

def load_user_config() -> dict:
    """Loads saved preferences from config.json with env variable fallbacks."""
    cfg = {
        "webhook_url": os.getenv("DISCORD_WEBHOOK_URL", ""),
        "notify_hits": True,
        "notify_2fa": True,
        "threads": 25,
        "timeout": 12,
        "retries": 2,
        "auto_scrape": True
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_user_config(data: dict):
    """Saves preferences to config.json."""
    try:
        cur = load_user_config()
        cur.update(data)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=2)
    except Exception:
        pass

# Initialize runtime configuration
_RUNTIME_CONFIG = load_user_config()
DISCORD_WEBHOOK_URL = _RUNTIME_CONFIG.get("webhook_url", "")
DISCORD_NOTIFY_HITS = _RUNTIME_CONFIG.get("notify_hits", True)
DISCORD_NOTIFY_2FA = _RUNTIME_CONFIG.get("notify_2fa", True)

# Bulletproof DNS fallback resolution for platform hosts
STEAM_DNS_MAP = {
    "api.steampowered.com": ["2.21.69.170", "2.21.69.83", "23.48.243.201", "23.7.85.176"],
    "steamcommunity.com": ["104.122.213.9", "23.217.50.125", "23.48.243.201", "23.7.85.176"],
    "store.steampowered.com": ["23.217.50.125", "104.122.213.9", "23.48.243.201", "23.7.85.176"],
    "login.steampowered.com": ["88.221.92.43", "88.221.92.61", "23.48.243.201", "23.7.85.176"],
    "raw.githubusercontent.com": ["185.199.109.133", "185.199.110.133", "185.199.111.133", "185.199.108.133"],
    "api.proxyscrape.com": ["104.18.11.5", "104.18.10.5"],
}

def install_resilient_dns():
    """Installs resilient DNS fallback resolution into standard socket library."""
    import socket
    if getattr(socket, "_nexus_dns_installed", False):
        return
    orig_getaddrinfo = socket.getaddrinfo

    def resilient_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        try:
            return orig_getaddrinfo(host, port, family, type, proto, flags)
        except Exception:
            if host in STEAM_DNS_MAP:
                for ip in STEAM_DNS_MAP[host]:
                    try:
                        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
                    except Exception:
                        continue
            raise

    socket.getaddrinfo = resilient_getaddrinfo
    socket._nexus_dns_installed = True

# Install resilient DNS upon config load
install_resilient_dns()

# Steam Image CDN Endpoints
STEAM_CDN_SHARED = "https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps"
STEAM_CDN_LEGACY = "https://cdn.cloudflare.steamstatic.com/steam/apps"

# UI Theme Color Palette (Matte Dark Gray & Neon Crimson Red)
COLOR_BG_DARK = "#0b0d14"
COLOR_BG_CARD = "#121520"
COLOR_BG_CARD_HOVER = "#1a1f2e"
COLOR_BG_INPUT = "#0d1017"
COLOR_BORDER = "#1c2233"
COLOR_BORDER_FOCUS = "#ff1e38"

COLOR_ACCENT = "#ff1e38"
COLOR_ACCENT_HOVER = "#ff3b52"
COLOR_ACCENT_PRESSED = "#d9122a"
COLOR_ACCENT_DIM = "rgba(255, 30, 56, 0.12)"

COLOR_HIT = "#00e676"
COLOR_FREE = "#00b0ff"
COLOR_INVALID = "#ff5252"
COLOR_2FA = "#ffab00"
COLOR_WARN = "#ff9100"
COLOR_INFO = "#448aff"

COLOR_TEXT_PRIMARY = "#f4f6fa"
COLOR_TEXT_SECONDARY = "#9499a6"
COLOR_TEXT_MUTED = "#5a6070"

# Service Endpoints
ENDPOINT_COMMUNITY = "https://steamcommunity.com"
ENDPOINT_GET_RSA = "https://api.steampowered.com/IAuthenticationService/GetPasswordRSAPublicKey/v1"
ENDPOINT_BEGIN_AUTH = "https://api.steampowered.com/IAuthenticationService/BeginAuthSessionViaCredentials/v1"
ENDPOINT_POLL_AUTH = "https://api.steampowered.com/IAuthenticationService/PollAuthSessionStatus/v1"
ENDPOINT_FINALIZE_LOGIN = "https://login.steampowered.com/jwt/finalizelogin"
ENDPOINT_USERDATA = "https://store.steampowered.com/dynamicstore/userdata/"
ENDPOINT_GET_RSA_FALLBACK = "https://steamcommunity.com/login/getrsakey/"
ENDPOINT_DO_LOGIN = "https://steamcommunity.com/login/dologin/"
ENDPOINT_STORE = "https://store.steampowered.com"
ENDPOINT_PING_TEST = "https://steamcommunity.com"

# Network Defaults
DEFAULT_CONCURRENCY = 15
DEFAULT_TIMEOUT_SEC = 12
DEFAULT_MAX_RETRIES = 2
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

HTTP_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": ENDPOINT_COMMUNITY,
    "Referer": f"{ENDPOINT_COMMUNITY}/",
}
