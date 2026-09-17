"""
104Society — Advanced Discord Bot & Platform Telemetry System
============================================================
Application ID : 1550151403220238396
Public Key     : 262373d354f89c639d98800c4fc5712346b2c1ff194a6b4f6c591129749b3487

Supports BOTH Slash Commands (/stats, /search, /ban...) and Prefix Commands (!stats, !search...)
Full moderation suite, live cloud runner status, hits search, and Steam store integration.
"""

import os
import sys
import json
import asyncio
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

# Environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import discord
from discord import app_commands
from discord.ext import commands

# ── Configuration ───────────────────────────────────────────────────────────
APPLICATION_ID = 1550151403220238396
PUBLIC_KEY     = "262373d354f89c639d98800c4fc5712346b2c1ff194a6b4f6c591129749b3487"
BOT_TOKEN      = os.environ.get("BOT_TOKEN", "").strip()

RESULTS_DIR     = Path("results")
CHECKPOINT_FILE = RESULTS_DIR / "checkpoint.json"
HITSDC_FILE     = RESULTS_DIR / "hitsdc.txt"
HITS_ALL_FILE   = RESULTS_DIR / "hits_all_paid.txt"
HITS_TARGET_FILE = RESULTS_DIR / "hits.txt"

TOTAL_ACCOUNTS_DEFAULT = 910027
GITHUB_REPO            = "mertkapan/nexus-validator"
GITHUB_RUNS_API        = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=5"

STEAM_ICON   = "https://community.cloudflare.steamstatic.com/public/shared/images/responsive/share_steam_logo.png"
BOT_COLOR    = 0x5865F2   # Blurple
COLOR_GREEN  = 0x10B981   # Emerald
COLOR_PURPLE = 0xA855F7   # Violet
COLOR_ORANGE = 0xF59E0B   # Amber
COLOR_RED    = 0xEF4444   # Red
COLOR_CYAN   = 0x06B6D4   # Cyan

# ── Extensive Game Series Taxonomy ──────────────────────────────────────────
GAME_SERIES = {
    "fc":        ["ea sports fc", "fc 24", "fc 25", "fc 26", "fc 27"],
    "fifa":      ["fifa 22", "fifa 23", "fifa 24", "fifa 21", "fifa 20", "fifa 19"],
    "pes":       ["pro evolution soccer", "pes ", "efootball"],
    "gta":       ["grand theft auto", "gta v", "gta 5", "gta iv", "san andreas", "vice city"],
    "witcher":   ["the witcher 3", "the witcher 2", "the witcher:", "wild hunt"],
    "cod":       ["call of duty", "modern warfare", "black ops", "warzone"],
    "rust":      ["rust"],
    "elden":     ["elden ring", "shadow of the erdtree"],
    "souls":     ["dark souls", "sekiro", "bloodborne", "demon's souls", "armored core"],
    "rdr":       ["red dead redemption", "rdr 2", "rdr2"],
    "cyberpunk": ["cyberpunk 2077", "phantom liberty"],
    "ark":       ["ark: survival evolved", "ark: survival ascended"],
    "cs":        ["counter-strike 2", "cs:go", "counter-strike:"],
    "godofwar":  ["god of war", "god of war ragnarok"],
    "assassin":  ["assassin's creed", "valhalla", "odyssey", "origins", "mirage"],
    "resident":  ["resident evil", "biohazard", "village"],
    "nba":       ["nba 2k21", "nba 2k22", "nba 2k23", "nba 2k24", "nba 2k25"],
    "mortal":    ["mortal kombat 11", "mortal kombat 1", "mortal kombat x"],
    "tekken":    ["tekken 8", "tekken 7"],
    "forza":     ["forza horizon 5", "forza horizon 4", "forza motorsport"],
    "nfs":       ["need for speed", "unbound", "heat", "payback"],
    "fallout":   ["fallout 4", "fallout: new vegas", "fallout 76", "fallout 3"],
    "skyrim":    ["elder scrolls v: skyrim", "skyrim special edition", "oblivion"],
    "batman":    ["batman: arkham", "arkham knight", "arkham city", "arkham asylum"],
    "spiderman": ["marvel's spider-man", "miles morales", "spider-man 2"],
    "battlefield": ["battlefield 2042", "battlefield v", "battlefield 1", "battlefield 4"],
}


# ── Data Access Helpers ─────────────────────────────────────────────────────
def read_checkpoint() -> dict:
    try:
        if CHECKPOINT_FILE.exists():
            return json.loads(CHECKPOINT_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {}

def count_lines(path: Path) -> int:
    try:
        if path.exists():
            return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return 0

def read_recent_hits(n: int = 6) -> List[str]:
    try:
        if HITSDC_FILE.exists():
            lines = [l.strip() for l in HITSDC_FILE.open("r", encoding="utf-8", errors="ignore") if l.strip()]
            return lines[-n:]
    except Exception:
        pass
    return []

def search_series_hits(series_key: str, max_results: int = 8) -> List[str]:
    patterns = GAME_SERIES.get(series_key.lower(), [series_key.lower()])
    matches = []
    try:
        if HITSDC_FILE.exists():
            for line in HITSDC_FILE.open("r", encoding="utf-8", errors="ignore"):
                low = line.lower()
                if any(p in low for p in patterns):
                    matches.append(line.strip())
                    if len(matches) >= max_results:
                        break
    except Exception:
        pass
    return matches

def fetch_github_actions_status() -> dict:
    try:
        req = urllib.request.Request(GITHUB_RUNS_API, headers={"User-Agent": "104Society-Bot"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            runs = data.get("workflow_runs", [])
            if runs:
                latest = runs[0]
                return {
                    "success": True,
                    "id": latest.get("id"),
                    "status": latest.get("status"),
                    "conclusion": latest.get("conclusion"),
                    "event": latest.get("event"),
                    "created_at": latest.get("created_at"),
                    "html_url": latest.get("html_url"),
                    "all_runs": runs[:5]
                }
    except Exception as e:
        return {"success": False, "error": str(e)}
    return {"success": False, "error": "Veri yok"}


# ── Bot Client Initialization ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=["!", "."], intents=intents, application_id=APPLICATION_ID, help_command=None)


# ────────────────────────────────────────────────────────────────────────────
# 1. VALIDATION & TELEMETRY COMMANDS
# ────────────────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="stats", description="Canlı Steam validator kontrol istatistikleri")
async def cmd_stats(ctx: commands.Context):
    cp = read_checkpoint()
    checked     = cp.get("checked", 0)
    target_hits = cp.get("target_hits", 0)
    hits        = cp.get("hits", 0)
    two_fa      = cp.get("two_fa", 0)
    total       = cp.get("total", TOTAL_ACCOUNTS_DEFAULT) or TOTAL_ACCOUNTS_DEFAULT
    bad_count   = max(0, checked - (hits + two_fa))
    remaining   = max(0, total - checked)
    pct         = (checked / max(1, total)) * 100
    hit_rate    = (hits / max(1, checked)) * 100

    embed = discord.Embed(
        title="📊 104Society — Canlı Doğrulama İstatistikleri",
        color=COLOR_GREEN,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="✅ Kontrol Edilen", value=f"**{checked:,}** / {total:,} (`%{pct:.2f}`)", inline=False)
    embed.add_field(name="⏳ Kalan Hesap",    value=f"**{remaining:,}**", inline=True)
    embed.add_field(name="💚 Geçerli Hit",     value=f"**{hits:,}** (`%{hit_rate:.2f}`)", inline=True)
    embed.add_field(name="🎯 Target Hit",      value=f"**{target_hits:,}** (FC/GTA)", inline=True)
    embed.add_field(name="🔐 2FA (Korumalı)",  value=f"**{two_fa:,}**", inline=True)
    embed.add_field(name="❌ Bad / Geçersiz",  value=f"**{bad_count:,}**", inline=True)
    embed.add_field(name="📨 Discord'a Atılan", value=f"**{count_lines(HITSDC_FILE):,}**", inline=True)
    embed.set_thumbnail(url=STEAM_ICON)
    embed.set_footer(text="104Society Cloud & Local Engine", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="cloud", description="GitHub Actions 24/7 bulut koşusunun anlık durumu")
async def cmd_cloud(ctx: commands.Context):
    data = fetch_github_actions_status()
    if not data.get("success"):
        await ctx.send(f"❌ GitHub API Hatası: `{data.get('error')}`")
        return

    st = data["status"]
    con = data["conclusion"] or "çalışıyor (in_progress)"
    is_active = (st == "in_progress")
    color = COLOR_GREEN if is_active else COLOR_PURPLE

    embed = discord.Embed(
        title=f"☁️ GitHub Actions Bulut Durumu — {'🟢 ÇALIŞIYOR' if is_active else '⚪ BEKLEMEDE'}",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Koşu ID", value=f"[`#{data['id']}`]({data['html_url']})", inline=True)
    embed.add_field(name="Durum", value=f"`{st.upper()}` ({con})", inline=True)
    embed.add_field(name="Tetikleyici", value=f"`{data['event']}`", inline=True)
    embed.add_field(name="Başlama Tarihi (UTC)", value=f"`{data['created_at'][:19].replace('T', ' ')}`", inline=False)
    embed.add_field(name="Depo (Repository)", value=f"https://github.com/{GITHUB_REPO}", inline=False)

    # List last 4 runs
    history = []
    for r in data.get("all_runs", [])[:4]:
        rid = r.get("id")
        rst = r.get("status")
        rcon = r.get("conclusion") or "running"
        history.append(f"• [`#{rid}`]({r.get('html_url')}): `{rst}` ({rcon})")
    embed.add_field(name="Son Koşular", value="\n".join(history) or "—", inline=False)

    embed.set_footer(text="104Society 24/7 Cloud Orchestrator", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="recenthits", description="Son bulunan hit hesapları gösterir")
@app_commands.describe(count="Kaç hesap gösterilsin? (1-10)")
async def cmd_recenthits(ctx: commands.Context, count: int = 5):
    count = min(max(1, count), 10)
    hits = read_recent_hits(count)
    if not hits:
        await ctx.send("❌ Henüz kaydedilmiş bir hit bulunamadı.")
        return

    embed = discord.Embed(
        title=f"🔥 Son {len(hits)} Hit Hesap",
        color=COLOR_ORANGE,
        timestamp=datetime.now(timezone.utc)
    )
    for i, line in enumerate(reversed(hits), 1):
        parts = [p.strip() for p in line.split("|")]
        acct = parts[0] if parts else "?"
        user, pwd = acct.split(":", 1) if ":" in acct else (acct, "")
        games_part = next((p for p in parts if "PaidGames" in p), "—")
        embed.add_field(
            name=f"#{i} — {user}",
            value=f"`{user}` : ||`{pwd}`||\n{games_part[:180]}",
            inline=False
        )
    embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="search", description="Belirli bir oyun serisine sahip hit hesapları arar")
@app_commands.describe(series="Aranacak seri (fc, fifa, pes, gta, witcher, cod, rust, elden, rdr, cyberpunk, godofwar...)")
async def cmd_search(ctx: commands.Context, series: str):
    matches = search_series_hits(series, max_results=6)
    s_upper = series.upper()

    if not matches:
        embed = discord.Embed(
            title=f"🔍 '{s_upper}' Serisi — Sonuç Bulunamadı",
            description=f"`{series}` içeren bir hit henüz `hitsdc.txt` kütüğüne düşmedi.",
            color=COLOR_RED
        )
        embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
        await ctx.send(embed=embed)
        return

    color = 0xFF5500 if series.lower() in ("fc", "fifa", "pes") else COLOR_PURPLE
    embed = discord.Embed(
        title=f"🔍 '{s_upper}' Serisi — {len(matches)} Hesap Bulundu",
        description=f"Son kütük taraması sonuçları:",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    for i, line in enumerate(matches, 1):
        parts = [p.strip() for p in line.split("|")]
        acct = parts[0] if parts else "?"
        user, pwd = acct.split(":", 1) if ":" in acct else (acct, "")
        games_part = next((p for p in parts if "PaidGames" in p), "—")
        embed.add_field(
            name=f"#{i} — {user}",
            value=f"`{user}` : ||`{pwd}`||\n{games_part[:180]}",
            inline=False
        )
    embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="serieslist", description="Desteklenen popüler oyun serileri anahtarları")
async def cmd_serieslist(ctx: commands.Context):
    embed = discord.Embed(
        title="🎮 Desteklenen Oyun Serileri Listesi",
        description="`/search <seri>` komutu ile aşağıdaki anahtarları kullanabilirsiniz:",
        color=COLOR_CYAN
    )
    lines = []
    for k, v in GAME_SERIES.items():
        sample = ", ".join(v[:2])
        lines.append(f"• **`{k}`** : {sample}")
    
    # Split into two fields
    mid = len(lines) // 2
    embed.add_field(name="Seriler (A-M)", value="\n".join(lines[:mid]), inline=True)
    embed.add_field(name="Seriler (N-Z)", value="\n".join(lines[mid:]), inline=True)
    embed.set_footer(text="104Society Taxonomy", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="steamgame", description="Steam Mağazasında oyun fiyatı ve bilgisi arar")
@app_commands.describe(query="Aranacak oyun ismi")
async def cmd_steamgame(ctx: commands.Context, query: str):
    await ctx.defer()
    encoded = urllib.parse.quote(query)
    url = f"https://store.steampowered.com/api/storesearch/?term={encoded}&l=turkish&cc=TR"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "104Society-Steam-Bot"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            if not items:
                await ctx.send(f"❌ Steam mağazasında `{query}` bulunamadı.")
                return

            game = items[0]
            appid = game.get("id")
            name = game.get("name")
            price_info = game.get("price")
            header_img = game.get("tiny_image", "").replace("capsule_sm_120", "header")
            
            price_str = "Ücretsiz / F2P"
            if price_info:
                init_p = price_info.get("initial", 0) / 100
                fin_p  = price_info.get("final", 0) / 100
                curr   = price_info.get("currency", "USD")
                disc   = price_info.get("discount_percent", 0)
                if disc > 0:
                    price_str = f"~~{init_p:.2f} {curr}~~ ➜ **{fin_p:.2f} {curr}** (%{disc} İndirim!)"
                else:
                    price_str = f"**{fin_p:.2f} {curr}**"

            embed = discord.Embed(
                title=f"🎮 {name}",
                url=f"https://store.steampowered.com/app/{appid}/",
                color=COLOR_GREEN,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="AppID", value=f"`{appid}`", inline=True)
            embed.add_field(name="Fiyat", value=price_str, inline=True)
            embed.set_image(url=f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg")
            embed.set_footer(text="Steam Store API", icon_url=STEAM_ICON)
            await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Steam sorgusu başarısız oldu: `{e}`")


# ────────────────────────────────────────────────────────────────────────────
# 2. MODERATION & SERVER MANAGEMENT COMMANDS
# ────────────────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="ban", description="Kullanıcıyı sunucudan yasaklar")
@app_commands.describe(member="Yasaklanacak kullanıcı", reason="Yasaklama sebebi")
@commands.has_permissions(ban_members=True)
async def cmd_ban(ctx: commands.Context, member: discord.Member, reason: str = "104Society Moderasyon"):
    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 Kullanıcı Yasaklandı", color=COLOR_RED, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Yetkili", value=str(ctx.author), inline=True)
        embed.add_field(name="Sebep", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Bu kullanıcıyı yasaklamak için yetkim yetersiz.")


@bot.hybrid_command(name="unban", description="Yasaklı kullanıcının yasağını kaldırır")
@app_commands.describe(user_id="Kullanıcı ID numarası")
@commands.has_permissions(ban_members=True)
async def cmd_unban(ctx: commands.Context, user_id: str):
    try:
        uid = int(user_id)
        user = await bot.fetch_user(uid)
        await ctx.guild.unban(user)
        embed = discord.Embed(title="✅ Yasak Kaldırıldı", color=COLOR_GREEN, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{user} (`{uid}`)", inline=True)
        embed.add_field(name="Yetkili", value=str(ctx.author), inline=True)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Yasak kaldırılamadı: `{e}`")


@bot.hybrid_command(name="kick", description="Kullanıcıyı sunucudan atar")
@app_commands.describe(member="Atılacak kullanıcı", reason="Sebep")
@commands.has_permissions(kick_members=True)
async def cmd_kick(ctx: commands.Context, member: discord.Member, reason: str = "104Society Moderasyon"):
    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 Kullanıcı Atıldı", color=COLOR_ORANGE, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Yetkili", value=str(ctx.author), inline=True)
        embed.add_field(name="Sebep", value=reason, inline=False)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ Bu kullanıcıyı atmak için yetkim yetersiz.")


@bot.hybrid_command(name="timeout", description="Kullanıcıya geçici susturma (timeout) uygular")
@app_commands.describe(member="Susturulacak kullanıcı", minutes="Süre (dakika)", reason="Sebep")
@commands.has_permissions(moderate_members=True)
async def cmd_timeout(ctx: commands.Context, member: discord.Member, minutes: int = 10, reason: str = "Belirtilmedi"):
    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(title="⏳ Kullanıcı Susturuldu", color=COLOR_ORANGE, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{member.mention}", inline=True)
        embed.add_field(name="Süre", value=f"**{minutes}** dakika", inline=True)
        embed.add_field(name="Sebep", value=reason, inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Susturma uygulanamadı: `{e}`")


@bot.hybrid_command(name="clear", description="Belirtilen sayıda mesajı siler")
@app_commands.describe(amount="Silinecek mesaj sayısı (1-100)")
@commands.has_permissions(manage_messages=True)
async def cmd_clear(ctx: commands.Context, amount: int = 10):
    amount = min(max(1, amount), 100)
    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.send(f"✅ **{len(deleted)}** adet mesaj temizlendi.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass


@bot.hybrid_command(name="lock", description="Kanalı mesaj yazmaya kilitler")
@commands.has_permissions(manage_channels=True)
async def cmd_lock(ctx: commands.Context):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Bu kanal mesaj gönderimine **kilitlendi**.")


@bot.hybrid_command(name="unlock", description="Kanal kilidini açar")
@commands.has_permissions(manage_channels=True)
async def cmd_unlock(ctx: commands.Context):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Bu kanal mesaj gönderimine **açıldı**.")


# ────────────────────────────────────────────────────────────────────────────
# 3. UTILITY & SERVER INFORMATION COMMANDS
# ────────────────────────────────────────────────────────────────────────────

@bot.hybrid_command(name="serverinfo", description="Sunucu hakkında detaylı analiz")
async def cmd_serverinfo(ctx: commands.Context):
    g = ctx.guild
    if not g:
        await ctx.send("Bu komut yalnızca sunucularda çalışır.")
        return

    embed = discord.Embed(title=f"🏠 {g.name}", color=BOT_COLOR, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="🆔 Sunucu ID", value=str(g.id), inline=True)
    embed.add_field(name="👑 Kurucu", value=str(g.owner), inline=True)
    embed.add_field(name="👥 Toplam Üye", value=f"{g.member_count:,}", inline=True)
    embed.add_field(name="💬 Metin Kanalları", value=str(len(g.text_channels)), inline=True)
    embed.add_field(name="🔊 Ses Kanalları", value=str(len(g.voice_channels)), inline=True)
    embed.add_field(name="🎭 Rol Sayısı", value=str(len(g.roles)), inline=True)
    embed.add_field(name="🚀 Boost Seviyesi", value=f"Seviye {g.premium_tier} ({g.premium_subscription_count} Boost)", inline=True)
    embed.add_field(name="📅 Kuruluş Tarihi", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.set_footer(text="104Society Server Telemetry", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="userinfo", description="Kullanıcı profili ve rolleri")
@app_commands.describe(member="Bilgisi istenecek kullanıcı")
async def cmd_userinfo(ctx: commands.Context, member: Optional[discord.Member] = None):
    m = member or ctx.author
    embed = discord.Embed(title=f"👤 {m.display_name}", color=m.color if hasattr(m, "color") else BOT_COLOR, timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Kullanıcı Adı", value=str(m), inline=True)
    embed.add_field(name="ID", value=str(m.id), inline=True)
    embed.add_field(name="Bot?", value="Evet" if m.bot else "Hayır", inline=True)
    if hasattr(m, "joined_at") and m.joined_at:
        embed.add_field(name="Sunucuya Katılma", value=m.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="Hesap Oluşturulma", value=m.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    roles = [r.mention for r in m.roles[1:]][:12]
    embed.add_field(name=f"Roller ({len(m.roles)-1})", value=" ".join(roles) or "Rol yok", inline=False)
    if m.avatar:
        embed.set_thumbnail(url=m.avatar.url)
    embed.set_footer(text="104Society User Telemetry", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="avatar", description="Kullanıcının profil fotoğrafını büyük boyutta gösterir")
@app_commands.describe(member="Hedef kullanıcı")
async def cmd_avatar(ctx: commands.Context, member: Optional[discord.Member] = None):
    m = member or ctx.author
    url = m.avatar.url if m.avatar else m.default_avatar.url
    embed = discord.Embed(title=f"🖼️ {m.display_name} Avatarı", color=BOT_COLOR)
    embed.set_image(url=url)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="invite", description="104Society botunun sunucu davet linkini verir")
async def cmd_invite(ctx: commands.Context):
    invite_url = f"https://discord.com/api/oauth2/authorize?client_id={APPLICATION_ID}&permissions=8&scope=bot%20applications.commands"
    embed = discord.Embed(
        title="🤖 104Society Bot Davet Linki",
        description=f"[Sunucuna Eklemek İçin Buraya Tıkla]({invite_url})\n\n**Gerekli İzinler:** Yönetici (Administrator), Slash Komutları",
        color=BOT_COLOR
    )
    embed.set_thumbnail(url=STEAM_ICON)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="ping", description="Bot gecikme süresi (latency)")
async def cmd_ping(ctx: commands.Context):
    ms = round(bot.latency * 1000)
    color = COLOR_GREEN if ms < 80 else (COLOR_ORANGE if ms < 180 else COLOR_RED)
    await ctx.send(embed=discord.Embed(title="🏓 Pong!", description=f"Gecikme: **{ms}ms**", color=color))


@bot.hybrid_command(name="help", description="Tüm 104Society bot komutlarını listeler")
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🤖 104Society Bot — Komut Kılavuzu",
        description="Tüm komutlar hem Slash (`/`) hem de Prefix (`!`) ile çalışır:",
        color=BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(
        name="📊 Doğrulayıcı & Bulut",
        value=(
            "`/stats` — Canlı doğrulama sayıları\n"
            "`/cloud` — GitHub Actions 24/7 canlı durumu\n"
            "`/recenthits` — Son düşen geçerli hesaplar\n"
            "`/search <seri>` — Belirli oyun serisi arama\n"
            "`/serieslist` — Desteklenen serilerin listesi\n"
            "`/steamgame <oyun>` — Steam mağaza fiyatı ve detayı"
        ),
        inline=False
    )
    embed.add_field(
        name="🛡️ Moderasyon Komutları",
        value=(
            "`/ban <üye> [sebep]` — Kullanıcı yasaklar\n"
            "`/unban <id>` — Yasak kaldırır\n"
            "`/kick <üye> [sebep]` — Kullanıcı atar\n"
            "`/timeout <üye> <dk>` — Susturma uygular\n"
            "`/clear <adet>` — Toplu mesaj siler\n"
            "`/lock` / `/unlock` — Kanalı kilitler/açar"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ Genel & Bilgi",
        value=(
            "`/serverinfo` — Sunucu analizleri\n"
            "`/userinfo [üye]` — Üye profili ve roller\n"
            "`/avatar [üye]` — Profil fotoğrafı\n"
            "`/invite` — Bot davet linki\n"
            "`/ping` — Gecikme süresi"
        ),
        inline=False
    )
    embed.set_thumbnail(url=STEAM_ICON)
    embed.set_footer(text="104Society Platform Management", icon_url=STEAM_ICON)
    await ctx.send(embed=embed)


# ── Lifecycle Hooks ─────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"\n[104Society Bot] Giriş yapıldı: {bot.user} (ID: {bot.user.id})")
        print(f"[104Society Bot] Toplam {len(synced)} adet Slash komutu senkronize edildi.")
    except Exception as e:
        print(f"[104Society Bot] Slash sync notice: {e}")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="1_combined.txt | /help | /stats"
        )
    )
    print("[104Society Bot] Bot durumu: Online | Göreve hazır.\n")


# ── Entrypoint ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("=" * 65)
        print(" [104Society Bot] BOT_TOKEN bulunamadı!")
        print("=" * 65)
        print(" Discord Developer Portal -> Bot -> 'Reset Token' / 'Copy Token'")
        print(" Token'ı .env dosyasına ekleyin veya komut satırında verin:")
        print("   set BOT_TOKEN=token_buraya")
        print("   python bot_104society.py")
        print("=" * 65)
        sys.exit(0)

    bot.run(BOT_TOKEN)
