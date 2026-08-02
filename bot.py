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

# رصد التفاعل وزيادة النقاط للرتبة المحددة
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    data = load_data()

    guild_settings = data.get(guild_id, {})
    target_role_id = guild_settings.get("target_role_id")

    if target_role_id:
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
#  الأوامر المائلة (Slash Commands) المصححة بالكامل
# ------------------------------------------------------------------

@bot.tree.command(name="انشاء-توب", description="تصفير الليدبورد وتحديد الرتبة المطلوب رصد تفاعلها (للإدارة)")
@app_commands.describe(role="اختر الرتبة التي تريد حساب نقاط التفاعل لأعضائها")
async def reset_leaderboard(interaction: discord.Interaction, role: discord.Role):
    # التحقق من الصلاحية بالاعتماد على رتبة العضو بدل قائمة IDs
    member = interaction.user
    if not config.is_authorized_member(member):
        await interaction.response.send_message("❌ عذراً، هذا الأمر متاح فقط لأصحاب الرتبة المصرح لها.", ephemeral=True)
        return
        
    guild_id = str(interaction.guild_id)
    data = load_data()
    
    # تهيئة السيرفر بالرتبة الجديدة تماماً وتصفير العداد القديم
    data[guild_id] = {
        "target_role_id": role.id,
        "target_role_name": role.name,
        "users": {}
    }
    save_data(data)
        
    await interaction.response.send_message(f"🔄 تم تصفير الليدبورد وإعادة التهيئة! بدأ رصد التفاعل الصافي الآن لأصحاب رتبة: **{role.name}** 🎯")


@bot.tree.command(name="توب", description="عرض لوحة الصدارة الحالية للرتبة المسجلة")
async def leaderboard(interaction: discord.Interaction):
    guild_id = str(interaction.guild_id)
    data = load_data()
    
    guild_data = data.get(guild_id, {})
    users_data = guild_data.get("users", {})
    role_name = guild_data.get("target_role_name", "الرتبة المحددة")
    
    if not users_data:
        await interaction.response.send_message(f"📭 لا توجد بيانات تفاعل مسجلة لرتبة (**{role_name}**) حالياً. استخدم `/انشاء-توب` أولاً لتحديد رتبة.", ephemeral=True)
        return
        
    # ترتيب الأعضاء تنازلياً حسب عدد الرسائل الصافية
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
    if getattr(config, "AUTHORIZED_ROLE_ID", None):
        log.info(f"🔑 التصريح مفعّل عبر آيدي الرتبة: {config.AUTHORIZED_ROLE_ID}")
    else:
        log.info(f"🔑 التصريح مفعّل عبر اسم الرتبة: {config.AUTHORIZED_ROLE_NAME}")
    
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
        
    if not getattr(config, "AUTHORIZED_ROLE_ID", None) and not getattr(config, "AUTHORIZED_ROLE_NAME", None):
        log.warning("⚠️ لا يوجد رتبة مصرح لها محددة (AUTHORIZED_ROLE_ID أو AUTHORIZED_ROLE_NAME فاضيين) - البوت ما راح يستجيب لأي أحد.")

    try:
        await bot.load_extension("architect")
        log.info("✅ تم تحميل أداة البناء (نظام الوزير المحدث)")
    except Exception as e:
        log.error(f"❌ فشل تحميل الأداة: {e}")
        return

    try:
        await bot.load_extension("riplaca")
        log.info("✅ تم تحميل كوغ لعبة الريبلكا")
    except Exception as e:
        log.error(f"❌ فشل تحميل كوغ الريبلكا: {e}")
        return

    await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
