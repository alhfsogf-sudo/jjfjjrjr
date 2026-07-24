import asyncio
import logging
import sys
import discord
from discord.ext import commands

import config

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    log.info(f"✅ تم تسجيل الدخول باسم {bot.user} (ID: {bot.user.id})")
    log.info(f"🌐 متصل بـ {len(bot.guilds)} سيرفر")
    log.info(f"🔑 الأشخاص المصرح لهم: {config.AUTHORIZED_USER_IDS}")
    await bot.change_presence(activity=discord.Game(name="👷 أداة بناء السيرفر | نادِ الوزير"))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    log.error(f"خطأ بأمر {ctx.command}: {error}")


async def main():
    if not config.DISCORD_TOKEN:
        log.error("❌ لم يتم تعيين DISCORD_TOKEN. أضفه بمتغيرات البيئة على Railway.")
        return
    if not config.GEMINI_API_KEYS:
        log.error("❌ لا يوجد أي مفتاح Gemini API معرّف. أضف مفتاح واحد على الأقل.")
        return
    if not config.AUTHORIZED_USER_IDS:
        log.warning("⚠️ لا يوجد أي شخص مصرح له (OWNER_ID فاضي) - البوت ما راح يستجيب لأي أحد.")

    try:
        await bot.load_extension("architect")
        log.info("✅ تم تحميل أداة البناء")
    except Exception as e:
        log.error(f"❌ فشل تحميل الأداة: {e}")
        return

    await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main()) 
