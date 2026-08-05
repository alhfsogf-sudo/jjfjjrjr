"""utils/embeds.py — مصنع كل الـ Embeds المرئية في البوت."""
import discord
from datetime import datetime, timezone

from utils.constants import EMOJI, CULTURES
from core.models import Player, Buildings, Troops


def _now_str() -> str:
    return f"<t:{int(datetime.now(timezone.utc).timestamp())}:R>"


def _next_refresh_str(hours: int = 1) -> str:
    from datetime import timedelta
    nxt = datetime.now(timezone.utc) + timedelta(hours=hours)
    return f"<t:{int(nxt.timestamp())}:R>"


# ------------------------------------------------------------------
# قناة الدليل
# ------------------------------------------------------------------
def guide_embed() -> discord.Embed:
    e = discord.Embed(
        title="⚔️ سيادة الأمم — Empires of Discord",
        description=(
            "مرحباً بك في عالم **سيادة الأمم**!\n"
            "ابنِ إمبراطوريتك، درّب جيشك، تحالف أو احارب — "
            "والفائز من يستولي على عاصمة الخادم!\n\n"
            "اضغط الزر أدناه لتبدأ رحلتك. اختيار الثقافة **نهائي** فاختر بحكمة."
        ),
        color=0x2C3E50,
    )
    for c in CULTURES.values():
        e.add_field(name=f"{c.emoji} {c.name}", value=c.description, inline=False)
    e.set_footer(text="اضغط 📖 لشرح اللعبة الكامل في أي وقت")
    return e


def culture_select_embed() -> discord.Embed:
    e = discord.Embed(
        title="🎭 اختر ثقافتك",
        description="هذا القرار **نهائي ولا رجعة فيه**. اختر بما يناسب أسلوب لعبك.",
        color=0x8E44AD,
    )
    for c in CULTURES.values():
        e.add_field(name=f"{c.emoji} {c.name}", value=c.description, inline=False)
    return e


def welcome_embed(player: Player, culture_name: str) -> discord.Embed:
    e = discord.Embed(
        title="👑 تأسست إمبراطوريتك!",
        description=(
            f"ثقافتك: **{culture_name}**\n"
            f"🛡️ لديك درع حماية **48 ساعة** — لا أحد يقدر يهاجمك خلالها."
        ),
        color=0x27AE60,
    )
    e.add_field(name="مواردك الابتدائية", value=_resources_line(player.resources), inline=False)
    e.set_footer(text="راجع صندوق البريد لكل التحديثات، وقاعة العرش للتحكم في مبانيك")
    return e


# ------------------------------------------------------------------
# لوحات التحكم (تتحدث كل ساعة تلقائياً + عند الطلب)
# ------------------------------------------------------------------
def _resources_line(resources: dict) -> str:
    return (
        f"{EMOJI['gold']} {resources['gold']:,}  "
        f"{EMOJI['wood']} {resources['wood']:,}  "
        f"{EMOJI['iron']} {resources['iron']:,}  "
        f"{EMOJI['food']} {resources['food']:,}  "
        f"{EMOJI['essence']} {resources['essence']:,}"
    )


def throne_hall_embed(player: Player, buildings: Buildings) -> discord.Embed:
    culture = CULTURES[player.culture]
    shield_txt = "🛡️ **نشط**" if player.shield_active else "❌ منتهي"
    if player.shield_active and player.shield_time_left:
        hrs = int(player.shield_time_left.total_seconds() // 3600)
        mins = int((player.shield_time_left.total_seconds() % 3600) // 60)
        shield_txt += f" ({hrs} س {mins} د متبقية)"

    e = discord.Embed(
        title=f"🏰 قاعة العرش — {culture.emoji} {culture.name}",
        color=culture.color,
    )
    e.add_field(name="💰 الموارد", value=_resources_line(player.resources), inline=False)
    e.add_field(
        name="🏗️ المباني",
        value=(
            f"🌾 المزرعة: مستوى **{buildings.farm}**\n"
            f"⛏️ المنجم: مستوى **{buildings.mine}**\n"
            f"🪓 المنشرة: مستوى **{buildings.lumber}**\n"
            f"🏰 القلعة: مستوى **{buildings.castle}**\n"
            f"🔮 المذبح: مستوى **{buildings.altar}**"
        ),
        inline=False,
    )
    e.add_field(name="🛡️ الدرع", value=shield_txt, inline=False)
    e.set_footer(text=f"🔄 آخر تحديث: الآن  •  تحديث تلقائي تالٍ: {_next_refresh_str()}")
    e.timestamp = datetime.now(timezone.utc)
    return e


def war_divan_embed(player: Player, troops: Troops, power: float) -> discord.Embed:
    culture = CULTURES[player.culture]
    e = discord.Embed(title=f"⚔️ ديوان الحرب — {culture.name}", color=0xC0392B)
    e.add_field(
        name="🪖 الجيش",
        value=(
            f"⚔️ مشاة: **{troops.infantry:,}**\n"
            f"🐎 فرسان: **{troops.cavalry:,}**\n"
            f"🏹 رماة: **{troops.archers:,}**\n"
            f"🩹 جرحى: **{troops.wounded:,}**"
        ),
        inline=False,
    )
    e.add_field(name="💥 القوة العسكرية الكلية", value=f"**{power:,.0f}**", inline=False)
    wizard_txt = f"🧙 {troops.wizard}" if troops.wizard else "لا يوجد"
    beast_txt = f"🐲 {troops.beast}" if troops.beast else "لا يوجد"
    e.add_field(name="🔮 الكيانات السحرية", value=f"{wizard_txt}\n{beast_txt}", inline=False)
    e.set_footer(text=f"🔄 آخر تحديث: الآن  •  تحديث تلقائي تالٍ: {_next_refresh_str()}")
    e.timestamp = datetime.now(timezone.utc)
    return e


def magic_altar_embed(player: Player, buildings: Buildings, troops: Troops) -> discord.Embed:
    e = discord.Embed(title="🔮 المذبح السحري", color=0x8E44AD)
    e.add_field(name="جوهر السحر", value=f"{EMOJI['essence']} **{player.essence:,}**", inline=False)
    e.add_field(name="مستوى المذبح", value=f"**{buildings.altar}** / 5", inline=True)
    can_summon = "✅ نعم" if buildings.altar >= 5 else "❌ يلزم مستوى 5"
    e.add_field(name="استدعاء كامل متاح؟", value=can_summon, inline=True)
    wizard_txt = f"🧙 {troops.wizard}" if troops.wizard else "لا يوجد"
    beast_txt = f"🐲 {troops.beast}" if troops.beast else "لا يوجد"
    e.add_field(name="ساحرك الحالي", value=wizard_txt, inline=False)
    e.add_field(name="مخلوقك الحالي", value=beast_txt, inline=False)
    e.set_footer(text=f"🔄 آخر تحديث: الآن  •  تحديث تلقائي تالٍ: {_next_refresh_str()}")
    e.timestamp = datetime.now(timezone.utc)
    return e


def kingdom_status_embed(player: Player, buildings: Buildings, troops: Troops, power: float) -> discord.Embed:
    """لوحة حالة شاملة موحّدة — تُستخدم في زر 'تحديث حالتي' العام."""
    culture = CULTURES[player.culture]
    shield_txt = "🛡️ نشط" if player.shield_active else "❌ منتهي"
    e = discord.Embed(
        title=f"👑 حالة إمبراطوريتك — {culture.emoji} {culture.name}",
        color=culture.color,
    )
    e.add_field(name="💰 الموارد", value=_resources_line(player.resources), inline=False)
    e.add_field(
        name="🏗️ المباني",
        value=f"🌾{buildings.farm} ⛏️{buildings.mine} 🪓{buildings.lumber} 🏰{buildings.castle} 🔮{buildings.altar}",
        inline=True,
    )
    e.add_field(
        name="🪖 الجيش",
        value=f"⚔️{troops.infantry} 🐎{troops.cavalry} 🏹{troops.archers} 🩹{troops.wounded}",
        inline=True,
    )
    e.add_field(name="💥 القوة", value=f"{power:,.0f}", inline=True)
    e.add_field(name="🛡️ الدرع", value=shield_txt, inline=True)
    e.set_footer(text="تُحدَّث هذه اللوحة تلقائياً كل ساعة، أو اضغط الزر لتحديث فوري")
    e.timestamp = datetime.now(timezone.utc)
    return e


def mail_log_embed(title: str, description: str, color: int = 0x95A5A6) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.timestamp = datetime.now(timezone.utc)
    return e


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(title="❌ خطأ", description=message, color=0xE74C3C)


def success_embed(message: str) -> discord.Embed:
    return discord.Embed(title="✅ تم", description=message, color=0x2ECC71)
