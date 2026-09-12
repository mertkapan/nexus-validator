"""
Geographic Telemetry and Flag Glyph Formatter
Translates ISO country codes and location metadata into flag glyph representations.
"""

from typing import Optional


def country_code_to_flag(code: Optional[str]) -> str:
    """
    Converts 2-letter ISO country code (e.g., 'US', 'TR', 'DE') into a Unicode flag emoji.
    Returns empty or generic marker if code is invalid or missing.
    """
    if not code or len(code.strip()) != 2:
        return "🌐"

    code = code.strip().upper()
    try:
        # Unicode Regional Indicator Symbol sequence
        flag_chars = [chr(0x1F1E6 + ord(c) - ord('A')) for c in code]
        return f"{''.join(flag_chars)} {code}"
    except Exception:
        return f"🌐 {code}"


# Common known country string aliases from profile data
COUNTRY_NAME_TO_CODE = {
    "united states": "US", "usa": "US", "turkey": "TR", "türkiye": "TR",
    "germany": "DE", "deutschland": "DE", "russia": "RU", "russian federation": "RU",
    "united kingdom": "GB", "great britain": "GB", "uk": "GB", "england": "GB",
    "canada": "CA", "france": "FR", "brazil": "BR", "brasil": "BR",
    "china": "CN", "poland": "PL", "polska": "PL", "ukraine": "UA",
    "spain": "ES", "italy": "IT", "australia": "AU", "japan": "JP",
    "sweden": "SE", "norway": "NO", "finland": "FI", "netherlands": "NL",
    "argentina": "AR", "mexico": "MX", "india": "IN", "indonesia": "ID",
}


def resolve_country_display(country_raw: Optional[str], fallback_ip: Optional[str] = None) -> str:
    """
    Resolves country string or code into formatted '🇺🇸 US' or '🌐 Global' label.
    """
    if not country_raw:
        return "🌐 Unknown"

    clean = country_raw.strip().lower()
    if len(clean) == 2 and clean.isalpha():
        return country_code_to_flag(clean.upper())

    # Check known country names
    for name, code in COUNTRY_NAME_TO_CODE.items():
        if name in clean:
            return country_code_to_flag(code)

    return f"🌐 {country_raw.title()}"
