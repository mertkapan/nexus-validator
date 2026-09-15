"""
Platform Telemetry and Library Extraction Module
Extracts owned game inventories, playtime records, VAC ban flags, profile states, and geographic location.
"""

import re
import json
import asyncio
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
import aiohttp
from bs4 import BeautifulSoup

from nexus.utils.geo import resolve_country_display

# Common free-to-play titles (definitive list - only add if confirmed F2P on Steam)
COMMON_FREE_TITLES = {
    "counter-strike 2", "cs:go", "dota 2", "team fortress 2", "pubg: battlegrounds",
    "pubg: battlegrounds - test server", "apex legends", "warframe", "destiny 2",
    "unturned", "brawlhalla", "path of exile", "path of exile 2",
    "yu-gi-oh! master duel", "fall guys", "overwatch 2", "the sims 4", "lost ark",
    "halo infinite", "smite", "paladins", "world of tanks blitz", "crusader kings ii",
    "brawl stars", "war thunder", "stumble guys", "dead frontier 2",
    "naraka: bladepoint", "naraka bladepoint", "dark and darker", "once human",
    "delta force", "marvel rivals", "arena breakout: infinite", "arena breakout infinite",
    "deadlock", "once human", "super people", "ring of elysium", "combat master",
    "enlisted", "cuisine royale", "crsed: cuisine royale", "battlebit remastered",
    "conqueror's blade", "rogue company", "realm royale reforged",
    "eve online", "star trek online", "dc universe online", "champions online",
    "global agenda: free agent", "tribes: ascend", "bloodline champions",
    "grand theft auto v legacy", "grand theft auto v enhanced",
    "metin2", "genshin impact", "honkai: star rail", "zenless zone zero",
    "black desert", "aion", "tera", "neverwinter", "dungeons dragons online",
    "world of warships", "world of warplanes", "world of tanks",
    "krunker", "fortnite", "valorant",
    # Valve free tools and non-games
    "steam linux runtime", "proton", "steamvr", "steam vr", "are you ready for valve index",
}

COMMON_FREE_APPIDS = {
    730, 570, 440, 578080, 1172470, 230410, 1085660, 304930, 291550, 238960,
    1449850, 1097150, 2357570, 1222670, 1599340, 1240440, 444090, 444200,
    203770, 236390, 1675200, 216170, 221100, 1203220,
    # PUBG test server
    622590, 624822,
    # Grand Theft Auto V Legacy and Enhanced (these are confirmed F2P re-releases)
    2905829, 2905830,
}

# These paid games are sometimes falsely detected as free via keyword matching - protect them
PAID_GAME_EXCEPTIONS = {
    "efootball pes 2021 season update", "efootball pes 2021", "pro evolution soccer 2021",
    "pro evolution soccer 2020", "pro evolution soccer 2019", "pro evolution soccer 2018",
    "pro evolution soccer 2017", "pro evolution soccer 2016",
    "the sims 4 cats & dogs", "the sims 4 get famous",  # DLCs are paid
    "battlefield 4", "battlefield 1", "battlefield v", "battlefield 2042",
    "pes 2021", "pes 2020", "pes 2019",
}

def clean_title(raw: str) -> str:
    """Cleans title string from Unicode replacement and encoding artifacts."""
    if not raw:
        return ""
    t = raw.replace("\ufffd", "").replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
    t = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", t)
    return t.strip()

def is_item_free(appid: int, name: str) -> bool:
    """Accurately classifies free games, demos, prologues, betas, and servers."""
    if appid in COMMON_FREE_APPIDS:
        return True
    if not name:
        return False
    nl = name.lower().strip()
    
    # Protect known paid titles that could match free keywords
    if nl in PAID_GAME_EXCEPTIONS:
        return False
    
    # Exact match against known free titles
    if nl in COMMON_FREE_TITLES:
        return True
    
    # Strict keyword matching - only at word boundaries or in specific positions
    # to avoid marking paid games like "PUBG: BATTLEGROUNDS" as free when checking for "beta"
    free_exact_suffixes = [
        " demo", " prologue", " beta", " playtest", " test server",
        " public test", " experimental server", " dedicated server",
        " trial edition", " trial", " teaser", " bonus content",
        " free to play edition", " free edition",
    ]
    for kw in free_exact_suffixes:
        if nl.endswith(kw):
            return True
    
    # Must be at start or contain in specific positions
    if nl.startswith("demo ") or nl.startswith("prologue ") or nl.startswith("beta "):
        return True
    if ": prologue" in nl or ": demo" in nl or ": beta" in nl or "- prologue" in nl or "- demo" in nl:
        return True
    if "playtest" in nl:
        return True
    
    return False

# Preloaded popular game cache to instantly resolve names without API latency
APP_NAME_CACHE: Dict[int, str] = {
    730: "Counter-Strike 2",
    570: "Dota 2",
    440: "Team Fortress 2",
    1086940: "Baldur's Gate 3",
    271590: "Grand Theft Auto V",
    242760: "The Forest",
    1326470: "Sons Of The Forest",
    1172470: "Apex Legends",
    1091500: "Cyberpunk 2077",
    2138330: "Cyberpunk 2077: Phantom Liberty",
    252490: "Rust",
    431960: "Wallpaper Engine",
    578080: "PUBG: BATTLEGROUNDS",
    622590: "PUBG: BATTLEGROUNDS - Test Server",
    624822: "PUBG: BATTLEGROUNDS - Experimental Server",
    230410: "Warframe",
    105600: "Terraria",
    892970: "Valheim",
    1245620: "ELDEN RING",
    2778580: "ELDEN RING Shadow of the Erdtree",
    236390: "War Thunder",
    359550: "Tom Clancy's Rainbow Six Siege",
    1938090: "Call of Duty",
    1962660: "Call of Duty: Warzone",
    311210: "Call of Duty: Black Ops III",
    366840: "Call of Duty: Black Ops III - Awakening DLC",
    366841: "Call of Duty: Black Ops III - Eclipse DLC",
    366842: "Call of Duty: Black Ops III - Descent DLC",
    366843: "Call of Duty: Black Ops III - Salvation DLC",
    251570: "7 Days to Die",
    292030: "The Witcher 3: Wild Hunt",
    1172620: "Sea of Thieves",
    1145360: "Hades",
    1145350: "Hades II",
    1966720: "Lethal Company",
    553850: "HELLDIVERS 2",
    2357570: "Overwatch 2",
    1675200: "Stumble Guys",
    252950: "Rocket League",
    218620: "PAYDAY 2",
    1272080: "PAYDAY 3",
    381210: "Dead by Daylight",
    1085660: "Destiny 2",
    289070: "Sid Meier's Civilization VI",
    346110: "ARK: Survival Evolved",
    2399830: "ARK: Survival Ascended",
    275850: "No Man's Sky",
    582010: "Monster Hunter: World",
    1446780: "Monster Hunter Rise",
    1151640: "Horizon Zero Dawn",
    990080: "Hogwarts Legacy",
    1203220: "NARAKA: BLADEPOINT",
    1238810: "Battlefield V",
    1238840: "Battlefield 1",
    1517290: "Battlefield 2042",
    1817070: "Marvel's Spider-Man Remastered",
    1817190: "Marvel's Spider-Man: Miles Morales",
    1174180: "Red Dead Redemption 2",
    812140: "Assassin's Creed Odyssey",
    15100: "Assassin's Creed",
    33230: "Assassin's Creed II",
    33360: "Assassin's Creed: Brotherhood",
    33361: "Assassin's Creed: Brotherhood DLC",
    201870: "Assassin's Creed Revelations",
    242050: "Assassin's Creed IV Black Flag",
    289650: "Assassin's Creed Unity",
    368500: "Assassin's Creed Syndicate",
    582160: "Assassin's Creed Origins",
    2208920: "Assassin's Creed Mirage",
    1222670: "The Sims 4",
    2195250: "EA SPORTS FC 24",
    2669320: "EA SPORTS FC 25",
    1599340: "Lost Ark",
    960090: "Bloons TD 6",
    39210: "FINAL FANTASY XIV Online",
    1426210: "It Takes Two",
    1284210: "Guild Wars 2",
    550: "Left 4 Dead 2",
    4000: "Garry's Mod",
    220: "Half-Life 2",
    10: "Counter-Strike",
    620: "Portal 2",
    70: "Half-Life",
    400: "Portal",
    80: "Counter-Strike: Condition Zero",
    300: "Day of Defeat: Source",
    240: "Counter-Strike: Source",
    280: "Half-Life: Source",
    320: "Half-Life 2: Deathmatch",
    340: "Half-Life 2: Lost Coast",
    360: "Half-Life Deathmatch: Source",
    380: "Half-Life 2: Episode One",
    420: "Half-Life 2: Episode Two",
    413150: "Stardew Valley",
    281990: "Stellaris",
    394360: "Hearts of Iron IV",
    236850: "Europa Universalis IV",
    1158310: "Crusader Kings III",
    286160: "Tabletop Simulator",
    255710: "Cities: Skylines",
    949230: "Cities: Skylines II",
    489830: "The Elder Scrolls V: Skyrim Special Edition",
    72850: "The Elder Scrolls V: Skyrim",
    22330: "The Elder Scrolls IV: Oblivion",
    377160: "Fallout 4",
    22370: "Fallout: New Vegas",
    22380: "Fallout 3: Game of the Year Edition",
    227300: "Euro Truck Simulator 2",
    270880: "American Truck Simulator",
    646570: "Slay the Spire",
    264710: "Subnautica",
    848450: "Subnautica: Below Zero",
    1364780: "Street Fighter 6",
    1778820: "TEKKEN 8",
    1382330: "Persona 5 Royal",
    524220: "NieR:Automata",
    601150: "Devil May Cry 5",
    582660: "Black Desert",
    1623730: "Palworld",
    2050650: "Resident Evil 4",
    1196590: "Resident Evil Village",
    883710: "Resident Evil 2",
    952060: "Resident Evil 3",
    218230: "Planet Coaster",
    703080: "Planet Zoo",
    367520: "Hollow Knight",
    1057090: "Ori and the Will of the Wisps",
    261550: "Mount & Blade II: Bannerlord",
    48700: "Mount & Blade: Warband",
    108600: "Project Zomboid",
    1868140: "DAVE THE DIVER",
    2358720: "Black Myth: Wukong",
    976310: "Mortal Kombat 11",
    362003: "Mortal Kombat 11 Kombat Pack 1",
    307780: "Mortal Kombat X",
    700580: "Simple Sight - Crosshair Overlay",
    313250: "SpeedRunners",
    318940: "Toribash",
    240720: "Getting Over It with Bennett Foddy",
    250900: "The Binding of Isaac: Rebirth",
    322330: "Don't Starve Together",
    219740: "Don't Starve",
    2279720: "Metin2",
    2279721: "Metin2 Steam Pack",
    3840: "Deathtrap Dungeon",
    1794680: "Vampire Survivors",
    1671600: "Captain Bones: Prologue",
    1677150: "The Survivalists",
    2149010: "Kingdom Two Crowns",
    976730: "Halo: The Master Chief Collection",
    976731: "Halo: Reach",
    976732: "Halo: Combat Evolved Anniversary",
    976733: "Halo 2: Anniversary",
    976734: "Halo 3",
    976735: "Halo 3: ODST",
    976736: "Halo 4",
    1225330: "NBA 2K21",
    1644960: "NBA 2K22",
    1919590: "NBA 2K23",
    2338770: "NBA 2K24",
    2878980: "NBA 2K25",
    1174180: "Red Dead Redemption 2",
    2669320: "EA SPORTS FC 25",
    2195250: "EA SPORTS FC 24",
    1811260: "EA SPORTS FIFA 23",
    1506830: "FIFA 22",
    1313860: "EA SPORTS FC Mobile",
    1551360: "Forza Horizon 5",
    1293830: "Forza Horizon 4",
    244210: "Assetto Corsa",
    805550: "Assetto Corsa Competizione",
    284160: "BeamNG.drive",
    227300: "Euro Truck Simulator 2",
    270880: "American Truck Simulator",
    1063730: "New World",
    2215430: "Ghost of Tsushima DIRECTOR'S CUT",
    1888930: "Armored Core VI FIRES OF RUBICON",
    814380: "Sekiro: Shadows Die Twice",
    374320: "DARK SOULS III",
    335300: "DARK SOULS II: Scholar of the First Sin",
    570940: "DARK SOULS: REMASTERED",
    1593500: "God of War",
    2322010: "God of War Ragnarok",
    1659420: "UNCHARTED: Legacy of Thieves Collection",
    1817070: "Marvel's Spider-Man Remastered",
    1817190: "Marvel's Spider-Man: Miles Morales",
    1817070: "Marvel's Spider-Man 2",
    2050650: "Resident Evil 4",
    1196590: "Resident Evil Village",
    883710: "Resident Evil 2",
    952060: "Resident Evil 3",
    418370: "Resident Evil 7 Biohazard",
    1245620: "ELDEN RING",
    2778580: "ELDEN RING Shadow of the Erdtree",
    2358720: "Black Myth: Wukong",
    1623730: "Palworld",
    1145350: "Hades II",
    1145360: "Hades",
    1966720: "Lethal Company",
    2881650: "Content Warning",
    739630: "Phasmophobia",
    221100: "DayZ",
    252490: "Rust",
    1326470: "Sons Of The Forest",
    242760: "The Forest",
    648800: "Raft",
    815370: "Green Hell",
    526870: "Satisfactory",
    427520: "Factorio",
    1149460: "Icarus",
    1364780: "Street Fighter 6",
    1778820: "TEKKEN 8",
    1971870: "Mortal Kombat 1",
    976310: "Mortal Kombat 11",
    1086940: "Baldur's Gate 3",
    435150: "Divinity: Original Sin 2",
    553850: "HELLDIVERS 2",
    2183900: "Warhammer 40,000: Space Marine 2",
    1361210: "Warhammer 40,000: Darktide",
    552500: "Warhammer: Vermintide 2",
    1238810: "Battlefield V",
    1238840: "Battlefield 1",
    1517290: "Battlefield 2042",
    24860: "Battlefield: Bad Company 2",
    1938090: "Call of Duty",
    1962660: "Call of Duty: Warzone",
    2519060: "Call of Duty: Black Ops 6",
    1938090: "Call of Duty: Modern Warfare III",
    1938090: "Call of Duty: Modern Warfare II",
    311210: "Call of Duty: Black Ops III",
    202970: "Call of Duty: Black Ops II",
    42700: "Call of Duty: Black Ops",
    10180: "Call of Duty: Modern Warfare 2 (2009)",
    7940: "Call of Duty 4: Modern Warfare (2007)",
    359550: "Tom Clancy's Rainbow Six Siege",
    271590: "Grand Theft Auto V",
    12120: "Grand Theft Auto: San Andreas",
    12110: "Grand Theft Auto: Vice City",
    12100: "Grand Theft Auto III",
    12210: "Grand Theft Auto IV: The Complete Edition",
    1547000: "Grand Theft Auto: The Trilogy - The Definitive Edition",
    1091500: "Cyberpunk 2077",
    2138330: "Cyberpunk 2077: Phantom Liberty",
    292030: "The Witcher 3: Wild Hunt",
    20920: "The Witcher 2: Assassins of Kings Enhanced Edition",
    20900: "The Witcher: Enhanced Edition Director's Cut",
    1172620: "Sea of Thieves",
    261550: "Mount & Blade II: Bannerlord",
    48700: "Mount & Blade: Warband",
    108600: "Project Zomboid",
    1868140: "DAVE THE DIVER",
    1366540: "Dyson Sphere Program",
    1158310: "Crusader Kings III",
    394360: "Hearts of Iron IV",
    236850: "Europa Universalis IV",
    281990: "Stellaris",
    529340: "Victoria 3",
    289070: "Sid Meier's Civilization VI",
    8930: "Sid Meier's Civilization V",
    1363080: "Manor Lords",
    294100: "RimWorld",
    1172470: "Apex Legends",
    578080: "PUBG: BATTLEGROUNDS",
    230410: "Warframe",
    1085660: "Destiny 2",
    2357570: "Overwatch 2",
    1203220: "NARAKA: BLADEPOINT",
    1599340: "Lost Ark",
    582660: "Black Desert",
    431960: "Wallpaper Engine",
    252950: "Rocket League",
    218620: "PAYDAY 2",
    1272080: "PAYDAY 3",
    381210: "Dead by Daylight",
    346110: "ARK: Survival Evolved",
    2399830: "ARK: Survival Ascended",
    275850: "No Man's Sky",
    582010: "Monster Hunter: World",
    1446780: "Monster Hunter Rise",
    2054970: "Dragon's Dogma 2",
    1151640: "Horizon Zero Dawn",
    2420110: "Horizon Forbidden West Complete Edition",
    990080: "Hogwarts Legacy",
    1774580: "STAR WARS Jedi: Survivor",
    1172380: "STAR WARS Jedi: Fallen Order",
    1382330: "Persona 5 Royal",
    2161700: "Persona 3 Reload",
    1113000: "Persona 4 Golden",
    524220: "NieR:Automata",
    601150: "Devil May Cry 5",
    413150: "Stardew Valley",
    105600: "Terraria",
    250900: "The Binding of Isaac: Rebirth",
    367520: "Hollow Knight",
    1057090: "Ori and the Will of the Wisps",
    387290: "Ori and the Blind Forest: Definitive Edition",
    646570: "Slay the Spire",
    264710: "Subnautica",
    848450: "Subnautica: Below Zero",
    1794680: "Vampire Survivors",
    1675200: "Stumble Guys",
    1222670: "The Sims 4",
    960090: "Bloons TD 6",
    1426210: "It Takes Two",
    1284210: "Guild Wars 2",
    550: "Left 4 Dead 2",
    500: "Left 4 Dead",
    4000: "Garry's Mod",
    220: "Half-Life 2",
    10: "Counter-Strike",
    620: "Portal 2",
    70: "Half-Life",
    400: "Portal",
    80: "Counter-Strike: Condition Zero",
    240: "Counter-Strike: Source",
    300: "Day of Defeat: Source",
    489830: "The Elder Scrolls V: Skyrim Special Edition",
    72850: "The Elder Scrolls V: Skyrim",
    22330: "The Elder Scrolls IV: Oblivion",
    377160: "Fallout 4",
    22370: "Fallout: New Vegas",
    22380: "Fallout 3: Game of the Year Edition",
    1151340: "Fallout 76",
    255710: "Cities: Skylines",
    949230: "Cities: Skylines II",
    218230: "Planet Coaster",
    703080: "Planet Zoo",
    1240440: "Halo Infinite",
    1621690: "Core Keeper",
    1604030: "V Rising",
    1332010: "Stray",
    1178830: "We Were Here Together",
    1466860: "Age of Empires IV: Anniversary Edition",
    813780: "Age of Empires II: Definitive Edition",
    107410: "Arma 3",
    1874880: "Arma Reforger",
    252950: "Rocket League",
    1144200: "Ready or Not",
    393380: "Squad",
    581320: "Insurgency: Sandstorm",
    686810: "Hell Let Loose",
    594650: "Hunt: Showdown 1896",
    240720: "Getting Over It with Bennett Foddy",
    322330: "Don't Starve Together",
    219740: "Don't Starve",
    2279720: "Metin2",
    236390: "War Thunder",
    203770: "Crusader Kings II",
    1097150: "Fall Guys",
    304930: "Unturned",
    291550: "Brawlhalla",
    238960: "Path of Exile",
    1449850: "Yu-Gi-Oh! Master Duel",
    1506830: "FIFA 22",
    221680: "Rocksmith 2014 Edition - Remastered",
    250760: "Shovel Knight: Treasure Trove",
    268910: "Cuphead",
    312520: "Rain World",
    504230: "Celeste",
    108710: "Alan Wake",
    1307550: "Craftopia",
    1046930: "Dota Underlords",
    588650: "Dead Cells",
    860510: "Little Nightmares II",
    424840: "Little Nightmares",
    1097350: "Weird West",
    1444440: "The Coffin of Andy and Leyley",
}



async def resolve_app_name(session: aiohttp.ClientSession, appid: int, proxy: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolves an appid or package/sub id to a real game title and high-resolution header banner.
    Supports both Steam Apps and Steam Store Packages/Subs.
    """
    if appid in APP_NAME_CACHE:
        cached_val = APP_NAME_CACHE[appid]
        if isinstance(cached_val, dict):
            return cached_val
        return {"name": cached_val, "banner_url": f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg", "real_appid": str(appid)}

    # Step A: App Details Query
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic"
    try:
        async with session.get(url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                app_info = data.get(str(appid), {})
                if app_info.get("success"):
                    d = app_info.get("data", {})
                    name = d.get("name", "")
                    header_img = d.get("header_image", "")
                    if name:
                        res = {"name": name, "banner_url": header_img, "real_appid": str(appid)}
                        APP_NAME_CACHE[appid] = res
                        return res
    except Exception:
        pass

    # Step B: Package / Sub Details Query (for bundle/subscription licenses in dynamicstore)
    pkg_url = f"https://store.steampowered.com/api/packagedetails?packageids={appid}"
    try:
        async with session.get(pkg_url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                pkg_data = await resp.json(content_type=None)
                pkg_info = pkg_data.get(str(appid), {})
                if pkg_info.get("success"):
                    pdata = pkg_info.get("data", {})
                    pname = pdata.get("name", "")
                    apps = pdata.get("apps", [])
                    real_id = str(apps[0].get("id")) if apps else str(appid)
                    banner = f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{real_id}/header.jpg"
                    if pname:
                        res = {"name": pname, "banner_url": banner, "real_appid": real_id}
                        APP_NAME_CACHE[appid] = res
                        return res
    except Exception:
        pass

    fallback_name = f"AppID {appid}"
    res = {"name": fallback_name, "banner_url": "", "real_appid": str(appid)}
    APP_NAME_CACHE[appid] = res
    return res


async def extract_library_inventory(
    session: aiohttp.ClientSession,
    steamid: str,
    timeout: int = 12,
    proxy: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extracts game library metrics and profile metadata across comprehensive layers:
    0. Community profile games XML list (https://steamcommunity.com/profiles/{steamid}/games?xml=1) - direct complete library
    1. Community profile games tab (data-profile-gameslist, rgGames)
    2. Community Profile XML feed (mostPlayedGames, personaName, VAC, trade bans, location)
    3. Authenticated Store Userdata (rgOwnedApps, rgWalletInfo - wallet balance & currency)
    Resolves missing titles instantly and properly classifies Free vs Paid licenses.
    """
    inventory_data = {
        "steamid": steamid,
        "total_games": 0,
        "paid_games_count": 0,
        "games": [],
        "is_private": False,
        "vac_banned": False,
        "trade_banned": False,
        "is_limited": False,
        "persona_name": "",
        "avatar_url": "",
        "location": "",
        "country_display": "🌐 Global",
        "wallet": "",
        "profile_url": f"https://steamcommunity.com/profiles/{steamid}",
    }

    if not steamid:
        return inventory_data

    client_timeout = aiohttp.ClientTimeout(total=timeout)
    games_map: Dict[str, Dict[str, Any]] = {}

    # Layer 0: Direct Steam Community Games XML List (Fastest & most comprehensive for public libraries)
    try:
        xml_games_url = f"https://steamcommunity.com/profiles/{steamid}/games?xml=1"
        async with session.get(xml_games_url, proxy=proxy, timeout=client_timeout) as resp:
            if resp.status == 200:
                xml_text = await resp.text(errors="ignore")
                if "<gamesList>" in xml_text or "<games>" in xml_text:
                    try:
                        g_root = ET.fromstring(xml_text)
                        for g_node in g_root.findall(".//game"):
                            aid_node = g_node.find("appID")
                            name_node = g_node.find("name")
                            hours_node = g_node.find("hoursOnRecord")
                            
                            if aid_node is not None and aid_node.text:
                                aid_str = aid_node.text.strip()
                                raw_n = name_node.text.strip() if (name_node is not None and name_node.text) else ""
                                name = clean_title(raw_n) or f"AppID {aid_str}"
                                hours = hours_node.text.strip() if (hours_node is not None and hours_node.text) else "0"
                                aid_int = int(aid_str) if aid_str.isdigit() else 0
                                is_f = is_item_free(aid_int, name)
                                banner_url = f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{aid_str}/header.jpg"
                                games_map[aid_str] = {
                                    "appid": aid_str,
                                    "name": name,
                                    "hours": hours,
                                    "is_free": is_f,
                                    "banner_url": banner_url
                                }
                                if aid_int and name and not name.startswith("AppID "):
                                    APP_NAME_CACHE[aid_int] = name
                    except Exception:
                        pass
    except Exception:
        pass

    # Layer 1: Community Games Tab (Has full human-readable titles)
    if len(games_map) < 5:
        try:
            for tab_url in [
                f"https://steamcommunity.com/profiles/{steamid}/games/?tab=all",
                f"https://steamcommunity.com/profiles/{steamid}/games/",
                "https://steamcommunity.com/my/games/?tab=all"
            ]:
                try:
                    async with session.get(tab_url, proxy=proxy, timeout=client_timeout) as resp:
                        if resp.status == 200:
                            html_text = await resp.text(errors="ignore")
                            
                            # Try data-profile-gameslist
                            m_data = re.search(r'data-profile-gameslist="([^"]+)"', html_text)
                            if m_data:
                                try:
                                    raw_str = m_data.group(1).replace("&quot;", '"')
                                    data_list = json.loads(raw_str)
                                    for dg in data_list:
                                        aid_str = str(dg.get("appid", ""))
                                        raw_n = dg.get("name", "")
                                        name = clean_title(raw_n)
                                        hours = str(dg.get("hours_forever", dg.get("hours", "0")))
                                        aid_int = int(aid_str) if aid_str.isdigit() else 0
                                        is_f = is_item_free(aid_int, name)
                                        games_map[aid_str] = {
                                            "appid": aid_str,
                                            "name": name,
                                            "hours": hours,
                                            "is_free": is_f,
                                            "banner_url": f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{aid_str}/header.jpg"
                                        }
                                        if aid_int and name:
                                            APP_NAME_CACHE[aid_int] = name
                                    if games_map:
                                        break
                                except Exception:
                                    pass

                            # Try var rgGames
                            m_rg = re.search(r'var rgGames\s*=\s*(\[.*?\]);', html_text, re.DOTALL)
                            if m_rg:
                                try:
                                    rg_list = json.loads(m_rg.group(1))
                                    for rg in rg_list:
                                        aid_str = str(rg.get("appid", ""))
                                        raw_n = rg.get("name", "")
                                        name = clean_title(raw_n)
                                        hours = str(rg.get("hours_forever", rg.get("hours", "0")))
                                        aid_int = int(aid_str) if aid_str.isdigit() else 0
                                        is_f = is_item_free(aid_int, name)
                                        games_map[aid_str] = {
                                            "appid": aid_str,
                                            "name": name,
                                            "hours": hours,
                                            "is_free": is_f,
                                            "banner_url": f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{aid_str}/header.jpg"
                                        }
                                        if aid_int and name:
                                            APP_NAME_CACHE[aid_int] = name
                                    if games_map:
                                        break
                                except Exception:
                                    pass
                except Exception:
                    continue
        except Exception:
            pass

    # Layer 2: Profile XML Feed (mostPlayedGames, VAC, bans, location, avatar)
    try:
        profile_xml_url = f"https://steamcommunity.com/profiles/{steamid}/?xml=1"
        async with session.get(profile_xml_url, proxy=proxy, timeout=client_timeout) as resp:
            if resp.status == 200:
                text = await resp.text(errors="ignore")
                if "<profile>" in text:
                    try:
                        p_root = ET.fromstring(text)
                        
                        steam_name = p_root.find("steamID")
                        if steam_name is not None and steam_name.text:
                            inventory_data["persona_name"] = clean_title(steam_name.text)

                        avatar_node = p_root.find("avatarFull") or p_root.find("avatarMedium") or p_root.find("avatarIcon")
                        if avatar_node is not None and avatar_node.text:
                            inventory_data["avatar_url"] = avatar_node.text.strip()

                        vac_node = p_root.find("vacBanned")
                        if vac_node is not None and vac_node.text:
                            inventory_data["vac_banned"] = (vac_node.text.strip() == "1")

                        trade_node = p_root.find("tradeBanState")
                        if trade_node is not None and trade_node.text:
                            inventory_data["trade_banned"] = (trade_node.text.strip().lower() != "none")

                        limited_node = p_root.find("isLimitedAccount")
                        if limited_node is not None and limited_node.text:
                            inventory_data["is_limited"] = (limited_node.text.strip() == "1")

                        loc_node = p_root.find("location")
                        if loc_node is not None and loc_node.text:
                            loc_str = loc_node.text.strip()
                            inventory_data["location"] = loc_str
                            inventory_data["country_display"] = resolve_country_display(loc_str)

                        priv_node = p_root.find("privacyState")
                        if priv_node is not None and priv_node.text:
                            if "private" in priv_node.text.lower() or "friend" in priv_node.text.lower():
                                inventory_data["is_private"] = True

                        # Extract most played games
                        most_played = p_root.find("mostPlayedGames")
                        if most_played is not None:
                            for mg in most_played.findall("mostPlayedGame"):
                                gname_node = mg.find("gameName")
                                glink_node = mg.find("gameLink")
                                ghours_node = mg.find("hoursOnRecord")
                                
                                gname = clean_title(gname_node.text) if gname_node is not None and gname_node.text else ""
                                ghours = ghours_node.text.strip() if ghours_node is not None and ghours_node.text else "0"
                                glink = glink_node.text.strip() if glink_node is not None and glink_node.text else ""
                                
                                aid_m = re.search(r'/app/([0-9]+)', glink)
                                aid_str = aid_m.group(1) if aid_m else ""
                                
                                if aid_str:
                                    aid_int = int(aid_str)
                                    is_f = is_item_free(aid_int, gname)
                                    if aid_str not in games_map or not games_map[aid_str].get("name"):
                                        games_map[aid_str] = {
                                            "appid": aid_str,
                                            "name": gname,
                                            "hours": ghours,
                                            "is_free": is_f,
                                            "banner_url": f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{aid_str}/header.jpg"
                                        }
                                    if gname:
                                        APP_NAME_CACHE[aid_int] = gname
                    except Exception:
                        pass
    except Exception:
        pass

    # Layer 3: Authenticated Store Userdata (rgOwnedApps, rgWalletInfo)
    try:
        store_url = "https://store.steampowered.com/dynamicstore/userdata/"
        async with session.get(store_url, proxy=proxy, timeout=client_timeout) as resp:
            if resp.status == 200:
                store_data = await resp.json(content_type=None)
                
                # Extract Wallet Balance & Currency
                wallet_info = store_data.get("rgWalletInfo", {})
                if wallet_info:
                    try:
                        bal_cents = int(wallet_info.get("wallet_balance", 0))
                        currency_code = int(wallet_info.get("wallet_currency", 1))
                        curr_symbols = {
                            1: ("$", "USD"),
                            2: ("£", "GBP"),
                            3: ("€", "EUR"),
                            5: ("₽", "RUB"),
                            23: ("₺", "TRY"),
                            7: ("R$", "BRL"),
                            8: ("¥", "JPY"),
                            24: ("₴", "UAH"),
                            37: ("₸", "KZT")
                        }
                        if bal_cents > 0:
                            sym, code = curr_symbols.get(currency_code, ("$", "USD"))
                            bal_float = bal_cents / 100.0
                            inventory_data["wallet"] = f"{sym}{bal_float:.2f} {code}"
                    except Exception:
                        pass

                owned_ids = store_data.get("rgOwnedApps", [])
                for aid in owned_ids:
                    aid_str = str(aid)
                    if aid_str not in games_map:
                        name = clean_title(APP_NAME_CACHE.get(int(aid), ""))
                        games_map[aid_str] = {
                            "appid": aid_str,
                            "name": name,
                            "hours": "0",
                            "is_free": is_item_free(int(aid), name),
                            "banner_url": f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{aid_str}/header.jpg"
                        }
    except Exception:
        pass

    final_games = list(games_map.values())

    # Layer 4: Concurrently resolve names for missing items (up to 40)
    missing = [
        g for g in final_games
        if (not g.get("name") or g["name"].startswith("AppID ")) and g.get("appid", "").isdigit()
    ]
    if missing:
        sem = asyncio.Semaphore(15)
        async def _resolve_worker(g):
            aid = int(g["appid"])
            res = await resolve_app_name(session, aid, proxy=proxy)
            resolved_name = res.get("name", "")
            g["name"] = clean_title(resolved_name)
            if res.get("banner_url"):
                g["banner_url"] = res["banner_url"]
            if res.get("real_appid"):
                g["appid"] = res["real_appid"]
            g["is_free"] = is_item_free(aid, g["name"])

        tasks = [_resolve_worker(g) for g in missing[:40]]
        await asyncio.gather(*tasks, return_exceptions=True)

    # Sort games: Paid first, then by name
    final_games.sort(key=lambda g: (1 if g.get("is_free") else 0, g.get("name", "")))

    paid_count = sum(1 for g in final_games if not g.get("is_free"))
    inventory_data["games"] = final_games
    inventory_data["total_games"] = len(final_games)
    inventory_data["paid_games_count"] = paid_count

    return inventory_data
