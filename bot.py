import asyncio
import logging
import sys
import os
import json
import discord
from discord.ext import commands
from discord import app_commands

import config

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("bot")

intents = discord.Intents.all() 
bot = commands.Bot(command_prefix=getattr(config, "COMMAND_PREFIX", "!"), intents=intents, help_command=None)

# ------------------------------------------------------------------
#  إعدادات نظام الليدبورد وتخزين البيانات
# ------------------------------------------------------------------
DATA_FILE = "leaderboard.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"❌ خطأ في قراءة ملف الليدبورد: {e}")
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        log.error(f"❌ خطأ في حفظ ملف الليدبورد: {e}")

# رصد التفاعل بناءً على الرتبة المحددة لكل سيرفر
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    data = load_data()

    # جلب إعدادات الرتبة المستهدفة لهذا السيرفر (إن وجدت)
    guild_settings = data.get(guild_id, {})
    target_role_id = guild_settings.get("target_role_id")

    if target_role_id:
        # التحقق إذا كان العضو يمتلك الرتبة المحددة عبر الـ ID
        has_role = any(role.id == int(target_role_id) for role in message.author.roles)
        
        if has_role:
            if "users" not in data[guild_id]:
                data[guild_id]["users"] = {}
            
            if user_id not in data[guild_id]["users"]:
                data[guild_id]["users"][user_id] = {"messages": 0, "name": message.author.display_name}
                
            data[guild_id]["users"][user_id]["messages"] += 1
            data[guild_id]["users"][user_id]["name"] = message.author.display_name
            save_data(data)

    await bot.process_commands(message)

# ------------------------------------------------------------------
#  الأوامر المائلة (Slash Commands) المطورة
# ------------------------------------------------------------------

@bot.tree.command(name="انشاء-توب", description="تصفير الليدبورد وتحديد الرتبة المطلوب رصد تفاعلها")
@app_commands.describe(role="اختر الرتبة التي تريد حساب نقاط التفاعل لأعضائها")
async def reset_leaderboard(interaction: discord.Interaction, role: discord.Role):
    # التحقق من الصلاحيات الإدارية من الـ config
    if interaction.user.id not in getattr(config, "AUTHORIZED_USER_IDS", []):
        await interaction.response.send_message("❌ عذراً، هذا الأمر متاح فقط للمطورين المصرح لهم.", ephemeral=True)
        return
        
    guild_id = str(interaction.guild_id)
    data = load_data()
    
    # تهيئة وتحديث بيانات السيرفر بالرتبة الجديدة وتصفير المستخدمين
    data[guild_id] = {
        "target_role_id": role.id,
        "target_role_name": role.name,
        "users": {}
    }
    save_data(data)
        
    await interaction.response.send_message(f"🔄 تم تصفير الليدبورد بنجاح! بدأ رصد التفاعل الصافي الآن لأصحاب رتبة: **{role.name}** 🎯")


@bot.tree.command(name="توب", description="عرض لوحة الصدارة الحالية للرتبة المحددة")
async def leaderboard(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    data = load_data()
    
    guild_data = data.get(guild_id, {})
    users_data = guild_data.get("users", {})
    role_name = guild_data.get("target_role_name", "الرتبة المحددة")
    
    if not users_data:
        await interaction.response.send_message(f"📭 لا توجد بيانات تفاعل مسجلة لرتبة (**{role_name}**) في هذا السيرفر بعد.", ephemeral=True)
        return
        
    # ترتيب الأعضاء تنازلياً
    sorted_users = sorted(users_data.items(), key=lambda item: item[1]["messages"], reverse=True)
    
    embed = discord.Embed(
        title=f"🏆 لوحة الصدارة الصافية ({role_name})",
        description=f"ترتيب الأعضاء الأكثر تفاعلاً من حاملي رتبة **{role_name}**:",
        color=discord.Color.blue()
    )
    
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    
    for index, (user_id, user_info) in enumerate(sorted_users[:10]):
        prefix = medals[index] if index < 3 else f"**#{index + 1}**"
        lines.append(f"{prefix} <@{user_id}> - `{user_info['messages']}` رسالة صافية")
        
    embed.description += "\n\n" + "\n".join(lines)
    embed.set_footer(text=f"طلب بواسطة: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

# ------------------------------------------------------------------
#  أحداث تشغيل البوت ومزامنة الأوامر
# ------------------------------------------------------------------

@bot.event
async def on_ready():
    log.info(f"✅ تم تسجيل الدخول باسم {bot.user} (ID: {bot.user.id})")
    log.info(f"🌐 متصل بـ {len(bot.guilds)} سيرفر")
    log.info(f"🔑 الأشخاص المصرح لهم: {config.AUTHORIZED_USER_IDS}")
    
    try:
        log.info("🔄 جاري مزامنة الأوامر المائلة (Slash Commands) مع ديسكورد...")
        synced = await bot.tree.sync()
        log.info(f"✨ تم مزامنة {len(synced)} أمر مائل بنجاح!")
    except Exception as e:
        log.error(f"❌ فشل مزامنة الأوامر المائلة: {e}")
        
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
    
    if not getattr(config, "GEMINI_API_KEYS", None):
        log.error("❌ لا يوجد أي مفتاح Gemini API معرّف. أضف مفتاح واحد على الأقل.")
        return
        
    if not config.AUTHORIZED_USER_IDS:
        log.warning("⚠️ لا يوجد أي شخص مصرح له (OWNER_ID فاضي) - البوت ما راح يستجيب لأي أحد.")

    try:
        await bot.load_extension("architect")
        log.info("✅ تم تحميل أداة البناء (نظام الوزير المحدث)")
    except Exception as e:
        log.error(f"❌ فشل تحميل الأداة: {e}")
        return

    await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
 
