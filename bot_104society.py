"""
104Society Discord Bot
======================
Proper Discord bot (appears in members list, slash commands, rich embeds).
Run with:  python bot_104society.py
Requires:  BOT_TOKEN environment variable  (or .env file)

Setup:
  1. Go to https://discord.com/developers/applications
  2. Create application named "104Society"
  3. Bot tab → Add Bot → copy token
  4. OAuth2 → URL Generator → scopes: bot, applications.commands
     permissions: Send Messages, Embed Links, Mention Everyone, Ban Members
  5. Add bot to your server via the generated URL
  6. Set env:  BOT_TOKEN=your_token_here

Install:  pip install discord.py python-dotenv
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import discord
    from discord import app_commands
except ImportError:
    print("[104Society Bot] discord.py not installed.")
    print("Run: pip install discord.py")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "").strip()
RESULTS_DIR = Path("results")
CHECKPOINT  = RESULTS_DIR / "checkpoint.json"
HITS_FILE   = RESULTS_DIR / "hits_all_paid.txt"
HITSDC_FILE = RESULTS_DIR / "hitsdc.txt"
HITS_TARGET = RESULTS_DIR / "hits.txt"

STEAM_ICON  = "https://community.cloudflare.steamstatic.com/public/shared/images/responsive/share_steam_logo.png"
BOT_COLOR   = 0x5865F2   # Discord Blurple

# ── Game series keyword map ────────────────────────────────────────────────
GAME_SERIES = {
    "fc":      ["ea sports fc", "fc 24", "fc 25", "fc 26", "fc 27"],
    "fifa":    ["fifa 22", "fifa 23", "fifa 24", "fifa 19", "fifa 20", "fifa 21"],
    "pes":     ["pro evolution soccer", "pes ", "efootball"],
    "gta":     ["grand theft auto", "gta"],
    "witcher": ["the witcher", "witcher"],
    "cod":     ["call of duty", "modern warfare", "black ops", "warzone"],
    "elden":   ["elden ring", "shadow of the erdtree"],
    "souls":   ["dark souls", "sekiro", "elden ring", "armored core"],
    "ark":     ["ark: survival", "ark survival"],
    "cs":      ["counter-strike", "cs:go", "counter-strike 2"],
    "rust":    ["rust"],
    "rdr":     ["red dead redemption"],
    "cyberpunk": ["cyberpunk 2077"],
    "assassin": ["assassin's creed"],
    "batman":  ["batman", "arkham"],
    "resident": ["resident evil"],
    "nba":     ["nba 2k"],
    "mortal":  ["mortal kombat"],
    "tekken":  ["tekken"],
    "minecraft": ["minecraft"],
    "fallout": ["fallout"],
    "skyrim":  ["elder scrolls", "skyrim"],
}

# ──────────────────────────────────────────────────────────────────────────

def _read_checkpoint() -> dict:
    try:
        if CHECKPOINT.exists():
            return json.loads(CHECKPOINT.read_text("utf-8"))
    except Exception:
        pass
    return {}

def _count_lines(path: Path) -> int:
    try:
        if path.exists():
            return sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return 0

def _read_last_hits(n: int = 5) -> list:
    """Returns the last N lines from hitsdc.txt."""
    try:
        if HITSDC_FILE.exists():
            lines = HITSDC_FILE.read_text("utf-8", errors="ignore").splitlines()
            return [l for l in lines if l.strip()][-n:]
    except Exception:
        pass
    return []

def _search_series(keyword: str, n: int = 8) -> list:
    """Searches hitsdc.txt for accounts that own games matching the keyword series."""
    kw = keyword.lower()
    patterns = GAME_SERIES.get(kw, [kw])
    results = []
    try:
        if HITSDC_FILE.exists():
            for line in HITSDC_FILE.open("r", encoding="utf-8", errors="ignore"):
                line_low = line.lower()
                if any(p in line_low for p in patterns):
                    results.append(line.strip())
                    if len(results) >= n:
                        break
    except Exception:
        pass
    return results


# ── Bot Setup ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


# ──────────────────────────────────────────────────────────────────────────
# SLASH COMMANDS
# ──────────────────────────────────────────────────────────────────────────

@tree.command(name="ping", description="Bot gecikme süresi")
async def cmd_ping(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Bot gecikmesi: **{ms}ms**",
        color=0x4CAF50 if ms < 100 else 0xFF9800,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="104Society", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


@tree.command(name="stats", description="Anlık checker istatistikleri")
async def cmd_stats(interaction: discord.Interaction):
    cp = _read_checkpoint()
    checked     = cp.get("checked", 0)
    total       = cp.get("total", 0)
    target_hits = cp.get("target_hits", 0)
    hits        = cp.get("hits", 0)
    two_fa      = cp.get("two_fa", 0)
    dc_hits     = _count_lines(HITSDC_FILE)
    pct = f"{(checked/total*100):.1f}%" if total > 0 else "—"

    embed = discord.Embed(
        title="📊 104Society — Canlı İstatistikler",
        color=BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="✅ Kontrol Edilen", value=f"**{checked:,}** / {total:,} ({pct})", inline=False)
    embed.add_field(name="🎯 Target Hit",    value=f"**{target_hits:,}**", inline=True)
    embed.add_field(name="💚 Tüm Hit",       value=f"**{hits:,}**",        inline=True)
    embed.add_field(name="🔐 2FA Kilitli",   value=f"**{two_fa:,}**",      inline=True)
    embed.add_field(name="📨 Discord'a Gönderilen", value=f"**{dc_hits:,}**", inline=True)
    embed.set_thumbnail(url=STEAM_ICON)
    embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


@tree.command(name="recenthits", description="Son bulunan hit hesapları göster")
@app_commands.describe(count="Kaç hit gösterilsin? (max 10)")
async def cmd_recent(interaction: discord.Interaction, count: int = 5):
    count = min(max(1, count), 10)
    hits = _read_last_hits(count)
    if not hits:
        await interaction.response.send_message("❌ Henüz Discord'a gönderilmiş hit yok.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🔥 Son {count} Hit Hesap",
        color=0xFF5722,
        timestamp=datetime.now(timezone.utc)
    )
    for i, line in enumerate(hits, 1):
        # Parse: user:pass | SteamID:... | ...
        parts = [p.strip() for p in line.split("|")]
        account = parts[0] if parts else line[:80]
        games_part = next((p for p in parts if "PaidGames" in p), "")
        embed.add_field(
            name=f"#{i}",
            value=f"```{account}```{games_part[:200]}",
            inline=False
        )
    embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


@tree.command(name="search", description="Oyun serisi içeren hit hesaplarını ara")
@app_commands.describe(
    series="Aranacak oyun serisi (fc, fifa, pes, gta, witcher, cod, rust, ark, rdr, cs, elden...)",
    count="Sonuç sayısı (max 8)"
)
async def cmd_search(interaction: discord.Interaction, series: str, count: int = 5):
    count = min(max(1, count), 8)
    results = _search_series(series.lower(), count)

    if not results:
        embed = discord.Embed(
            title=f"🔍 '{series}' Serisi — Sonuç Yok",
            description=f"`{series}` içeren bir hit henüz bulunamadı.",
            color=0x9E9E9E
        )
    else:
        series_label = series.upper()
        known = GAME_SERIES.get(series.lower())
        patterns_str = ", ".join(known[:4]) if known else series
        embed = discord.Embed(
            title=f"🔍 '{series_label}' Serisi — {len(results)} Sonuç",
            description=f"Aranan pattern: `{patterns_str}`",
            color=0xFF5500 if series.lower() in ("fc","fifa","pes") else 0x2196F3,
            timestamp=datetime.now(timezone.utc)
        )
        for i, line in enumerate(results, 1):
            parts = [p.strip() for p in line.split("|")]
            account = parts[0] if parts else "?"
            games_part = next((p for p in parts if "PaidGames" in p), "")
            embed.add_field(
                name=f"#{i} — {account.split(':')[0] if ':' in account else account}",
                value=f"`{account}`\n{games_part[:150]}",
                inline=False
            )

    embed.set_footer(text="104Society Validator", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


@tree.command(name="serverinfo", description="Sunucu bilgilerini göster")
async def cmd_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("Bu komut sadece sunucularda çalışır.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🏠 {guild.name}",
        color=BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="🆔 Sunucu ID",    value=str(guild.id),          inline=True)
    embed.add_field(name="👑 Sahip",         value=str(guild.owner),       inline=True)
    embed.add_field(name="👥 Üye Sayısı",   value=f"{guild.member_count:,}", inline=True)
    embed.add_field(name="💬 Kanal Sayısı", value=str(len(guild.channels)),  inline=True)
    embed.add_field(name="🎭 Rol Sayısı",   value=str(len(guild.roles)),    inline=True)
    embed.add_field(name="📅 Oluşturuldu",  value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="104Society", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


@tree.command(name="ban", description="Bir kullanıcıyı sunucudan banla")
@app_commands.describe(user="Banlanacak kullanıcı", reason="Ban sebebi")
@app_commands.default_permissions(ban_members=True)
async def cmd_ban(interaction: discord.Interaction, user: discord.Member, reason: str = "Belirtilmedi"):
    if interaction.guild is None:
        await interaction.response.send_message("Bu komut sunucuda kullanılabilir.", ephemeral=True)
        return
    try:
        await user.ban(reason=f"[104Society] {reason}")
        embed = discord.Embed(
            title="🔨 Kullanıcı Banlandı",
            color=0xFF0000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Kullanıcı",  value=f"{user} (`{user.id}`)", inline=True)
        embed.add_field(name="Yetkili",    value=str(interaction.user),   inline=True)
        embed.add_field(name="Sebep",      value=reason,                  inline=False)
        embed.set_footer(text="104Society", icon_url=STEAM_ICON)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Bu kullanıcıyı banlama yetkim yok.", ephemeral=True)


@tree.command(name="unban", description="Banlı bir kullanıcının banını kaldır")
@app_commands.describe(user_id="Kullanıcı ID'si")
@app_commands.default_permissions(ban_members=True)
async def cmd_unban(interaction: discord.Interaction, user_id: str):
    if interaction.guild is None:
        await interaction.response.send_message("Bu komut sunucuda kullanılabilir.", ephemeral=True)
        return
    try:
        uid = int(user_id)
        user = await bot.fetch_user(uid)
        await interaction.guild.unban(user)
        embed = discord.Embed(
            title="✅ Ban Kaldırıldı",
            color=0x4CAF50,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Kullanıcı", value=f"{user} (`{uid}`)", inline=True)
        embed.add_field(name="Yetkili",   value=str(interaction.user), inline=True)
        embed.set_footer(text="104Society", icon_url=STEAM_ICON)
        await interaction.response.send_message(embed=embed)
    except (ValueError, discord.NotFound):
        await interaction.response.send_message("❌ Geçersiz ID veya kullanıcı zaten banlı değil.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Ban kaldırma yetkim yok.", ephemeral=True)


@tree.command(name="kick", description="Bir kullanıcıyı sunucudan at")
@app_commands.describe(user="Atılacak kullanıcı", reason="Sebep")
@app_commands.default_permissions(kick_members=True)
async def cmd_kick(interaction: discord.Interaction, user: discord.Member, reason: str = "Belirtilmedi"):
    if interaction.guild is None:
        await interaction.response.send_message("Bu komut sunucuda kullanılabilir.", ephemeral=True)
        return
    try:
        await user.kick(reason=f"[104Society] {reason}")
        embed = discord.Embed(title="👢 Kullanıcı Atıldı", color=0xFF9800, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Kullanıcı", value=f"{user} (`{user.id}`)", inline=True)
        embed.add_field(name="Yetkili",   value=str(interaction.user),   inline=True)
        embed.add_field(name="Sebep",     value=reason,                  inline=False)
        embed.set_footer(text="104Society", icon_url=STEAM_ICON)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Bu kullanıcıyı atma yetkim yok.", ephemeral=True)


@tree.command(name="clear", description="Kanaldan mesaj sil")
@app_commands.describe(count="Silinecek mesaj sayısı (max 100)")
@app_commands.default_permissions(manage_messages=True)
async def cmd_clear(interaction: discord.Interaction, count: int = 10):
    count = min(max(1, count), 100)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=count)
    await interaction.followup.send(f"✅ **{len(deleted)}** mesaj silindi.", ephemeral=True)


@tree.command(name="userinfo", description="Bir kullanıcının bilgilerini göster")
@app_commands.describe(user="Bilgi gösterilecek kullanıcı")
async def cmd_userinfo(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    embed = discord.Embed(
        title=f"👤 {target.display_name}",
        color=target.color if hasattr(target, "color") else BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Kullanıcı Adı", value=str(target),          inline=True)
    embed.add_field(name="ID",            value=str(target.id),        inline=True)
    embed.add_field(name="Bot?",          value="Evet" if target.bot else "Hayır", inline=True)
    if hasattr(target, "joined_at") and target.joined_at:
        embed.add_field(name="Sunucuya Katıldı", value=target.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Hesap Oluşturuldu", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
    if hasattr(target, "roles"):
        roles = [r.mention for r in target.roles[1:]][:10]
        embed.add_field(name=f"Roller ({len(target.roles)-1})", value=" ".join(roles) or "—", inline=False)
    if target.avatar:
        embed.set_thumbnail(url=target.avatar.url)
    embed.set_footer(text="104Society", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


@tree.command(name="help", description="104Society bot komutları")
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 104Society Bot — Komutlar",
        description="Slash komutları (/ ile başlar):",
        color=BOT_COLOR,
        timestamp=datetime.now(timezone.utc)
    )
    commands_list = [
        ("/stats",        "Anlık checker istatistikleri"),
        ("/recenthits",   "Son Discord'a gönderilen hitler"),
        ("/search",       "Oyun serisi arama (fc, gta, witcher...)"),
        ("/serverinfo",   "Sunucu bilgileri"),
        ("/userinfo",     "Kullanıcı bilgileri"),
        ("/ban",          "Kullanıcı banla (yetki gerekir)"),
        ("/unban",        "Ban kaldır (yetki gerekir)"),
        ("/kick",         "Kullanıcı at (yetki gerekir)"),
        ("/clear",        "Toplu mesaj sil (yetki gerekir)"),
        ("/ping",         "Bot gecikmesi"),
    ]
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=True)
    embed.add_field(
        name="🔍 /search Seriler",
        value="`fc` `fifa` `pes` `gta` `witcher` `cod` `rust` `ark` `rdr` `cs` `elden` `souls` `nba` `tekken` `mortal` `cyberpunk` `fallout` `skyrim`",
        inline=False
    )
    embed.set_thumbnail(url=STEAM_ICON)
    embed.set_footer(text="104Society — Steam Account Validator Bot", icon_url=STEAM_ICON)
    await interaction.response.send_message(embed=embed)


# ── Bot Events ─────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await tree.sync()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Steam hesapları | /help"
        )
    )
    print(f"\n[104Society Bot] Logged in as: {bot.user} (ID: {bot.user.id})")
    print(f"[104Society Bot] Slash commands synced. Bot is ready!")
    print(f"[104Society Bot] Invite URL (replace CLIENT_ID):")
    print(f"  https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands\n")


# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("=" * 60)
        print("  104Society Bot — Kurulum Gerekli")
        print("=" * 60)
        print()
        print("  BOT_TOKEN bulunamadı! Şu adımları izle:")
        print()
        print("  1. https://discord.com/developers/applications adresine git")
        print("  2. 'New Application' → isim: '104Society'")
        print("  3. Sol menü: Bot → 'Add Bot' → Token kopyala")
        print("  4. Ortam değişkeni ayarla:")
        print("     Windows: set BOT_TOKEN=token_buraya")
        print("     veya .env dosyası oluştur: BOT_TOKEN=token_buraya")
        print()
        print("  5. Bot'u sunucuya ekle (OAuth2 → URL Generator):")
        print("     Scopes: bot + applications.commands")
        print("     Permissions: Send Messages, Embed Links, Ban Members, Kick Members")
        print("=" * 60)
        sys.exit(0)

    bot.run(BOT_TOKEN)
