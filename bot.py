import discord
from discord.ext import commands
import re
import os

# ──────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────
TOKEN          = os.getenv("DISCORD_TOKEN")          # env var บน Railway
DETECT_CHANNEL = "detectx"                           # ชื่อห้องที่ monitor (lowercase)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", 0)) # ห้อง log (0 = ปิด)

# regex จับลิ้งทุกรูปแบบ
URL_PATTERN = re.compile(
    r"(https?://|discord\.gg/|www\.|bit\.ly|tinyurl|t\.me|tenor\.com)",
    re.IGNORECASE
)

# ──────────────────────────────────────────
#  BOT SETUP
# ──────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ──────────────────────────────────────────
#  HELPER: ส่ง log ไปห้อง log
# ──────────────────────────────────────────
async def send_log(guild: discord.Guild, member: discord.Member, reason: str, content: str):
    if not LOG_CHANNEL_ID:
        return
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if not ch:
        return

    embed = discord.Embed(
        title="🚨 DetectX — Threat Removed",
        color=0xFF0000,
    )
    embed.add_field(name="👤 User",    value=f"{member} (`{member.id}`)", inline=False)
    embed.add_field(name="⚠️ Reason",  value=reason,                      inline=False)
    embed.add_field(name="💬 Content", value=content[:500] or "*(ไม่มี text)*", inline=False)
    embed.set_footer(text="DetectX Auto-Kick")
    await ch.send(embed=embed)


# ──────────────────────────────────────────
#  HELPER: ดำเนินการกับผู้กระทำ
# ──────────────────────────────────────────
async def handle_threat(message: discord.Message, reason: str):
    member = message.guild.get_member(message.author.id)
    content = message.content

    # 1) ลบข้อความก่อน
    try:
        await message.delete()
    except discord.Forbidden:
        print(f"[DetectX] ❌ ไม่มีสิทธิ์ลบข้อความ")
    except discord.NotFound:
        pass  # ลบไปแล้ว

    # 2) Log
    if member:
        await send_log(message.guild, member, reason, content)

    # 3) เตะออก Discord
    if member:
        try:
            await member.kick(reason=f"[DetectX] {reason}")
            print(f"[DetectX] ✅ Kicked: {member} — {reason}")
        except discord.Forbidden:
            print(f"[DetectX] ❌ ไม่มีสิทธิ์ kick {member}")
        except Exception as e:
            print(f"[DetectX] ❌ Kick error: {e}")
    else:
        print(f"[DetectX] ⚠️ ไม่พบ member {message.author.id} ในเซิร์ฟเวอร์")


# ──────────────────────────────────────────
#  EVENT: on_ready
# ──────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"[DetectX] ✅ Logged in as {bot.user}")
    print(f"[DetectX] 🔍 Monitoring channel: #{DETECT_CHANNEL}")


# ──────────────────────────────────────────
#  EVENT: on_message — จุดหลัก
# ──────────────────────────────────────────
@bot.event
async def on_message(message: discord.Message):
    # ไม่สนใจบอทด้วยกัน
    if message.author.bot:
        return

    # ตรวจเฉพาะห้อง detectx (ชื่อ lowercase)
    if message.channel.name.lower() != DETECT_CHANNEL:
        await bot.process_commands(message)
        return

    # ── ตรวจ 1: มีไฟล์แนบ (รูป, วิดีโอ, ไฟล์ทุกชนิด) ──
    if message.attachments:
        types = [a.content_type or "unknown" for a in message.attachments]
        reason = f"แนบไฟล์ในห้อง #{DETECT_CHANNEL} ({', '.join(types)})"
        await handle_threat(message, reason)
        return

    # ── ตรวจ 2: มี embed (Discord auto-embed จากลิ้ง) ──
    if message.embeds:
        reason = f"ส่ง embed/preview ในห้อง #{DETECT_CHANNEL}"
        await handle_threat(message, reason)
        return

    # ── ตรวจ 3: มีลิ้งใน text ──
    if URL_PATTERN.search(message.content):
        reason = f"ส่งลิ้งในห้อง #{DETECT_CHANNEL}"
        await handle_threat(message, reason)
        return

    await bot.process_commands(message)


# ──────────────────────────────────────────
#  EVENT: on_message_edit — กันแก้ข้อความหลังส่ง
# ──────────────────────────────────────────
@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.author.bot:
        return
    if after.channel.name.lower() != DETECT_CHANNEL:
        return

    # ถ้าแก้แล้วมีลิ้ง/ไฟล์
    if after.attachments or after.embeds or URL_PATTERN.search(after.content):
        reason = f"แก้ข้อความเพิ่มลิ้ง/ไฟล์ในห้อง #{DETECT_CHANNEL}"
        await handle_threat(after, reason)


# ──────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────
if __name__ == "__main__":
    bot.run(TOKEN)