"""
cogs/economy.py — Module 2: محرك الموارد التلقائي.
تحسين UX: نفس الدورة الآن تُحدّث لوحات قاعة العرش/ديوان الحرب/المذبح تلقائياً كل ساعة،
وليس فقط الموارد، حتى يشعر اللاعب أن إمبراطوريته "حية" بدون أي تدخل منه.
"""
import discord
from discord.ext import commands, tasks

from core import database as db
from utils import embeds
from utils.game_math import (
    hourly_production, corruption_upkeep_multiplier, military_power,
)
from utils.constants import TROOP_TYPES
from ui.dashboard_view import DashboardView
from ui.war_view import WarView
from ui.magic_view import MagicView
from config import STATUS_REFRESH_HOURS

FOOD_CRISIS_DEATH_RATE = 0.05
GOLD_CRISIS_PRODUCTION_PENALTY = 0.30


async def _find_and_update_panel(channel: discord.abc.GuildChannel, embed: discord.Embed, view: discord.ui.View,
                                  title_prefix: str = None):
    """يبحث عن آخر رسالة للبوت تطابق عنوان اللوحة (title_prefix) ويحدّثها، أو ينشر واحدة جديدة إذا لم توجد.
    استخدام title_prefix ضروري في القنوات المدمجة (مثل king) التي تحتوي أكثر من نوع رسالة Embed."""
    if channel is None:
        return
    try:
        async for msg in channel.history(limit=50):
            if msg.author.id != channel.guild.me.id or not msg.embeds:
                continue
            if title_prefix is None or (msg.embeds[0].title or "").startswith(title_prefix):
                await msg.edit(embed=embed, view=view)
                return
        await channel.send(embed=embed, view=view)
    except discord.HTTPException:
        pass


class Economy(commands.Cog):
    """Module 2: نظام الموارد التلقائي — أهم نظام في اللعبة."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hourly_tick.start()

    def cog_unload(self):
        self.hourly_tick.cancel()

    @tasks.loop(hours=STATUS_REFRESH_HOURS)
    async def hourly_tick(self):
        players = await db.get_all_players()
        for player in players:
            try:
                await self._process_player_tick(player)
            except Exception as e:
                print(f"⚠️ خطأ أثناء معالجة اللاعب {player.user_id}: {e}")

    @hourly_tick.before_loop
    async def before_tick(self):
        await self.bot.wait_until_ready()

    async def _process_player_tick(self, player):
        buildings = await db.get_buildings(player.user_id)
        troops = await db.get_troops(player.user_id)
        guild = self.bot.get_guild(player.guild_id)
        if guild is None:
            return

        report_lines = []

        # 1) الإنتاج
        import cogs.world_events as world_events_module
        famine_active = world_events_module.great_famine_active

        production = {"gold": 0, "wood": 0, "iron": 0, "food": 0, "essence": 0}
        gold_crisis = player.gold <= 0
        for b in ("farm", "mine", "lumber", "altar"):
            level = getattr(buildings, b)
            if level <= 0:
                continue
            prod = hourly_production(b, level, player.culture)
            for res, amt in prod.items():
                if gold_crisis and res in ("wood", "iron", "essence"):
                    amt = round(amt * (1 - GOLD_CRISIS_PRODUCTION_PENALTY))
                if famine_active and res == "food":
                    amt = round(amt * 0.5)
                production[res] += amt

        if any(production.values()):
            report_lines.append(
                "📈 الإنتاج: " + ", ".join(f"+{v} {k}" for k, v in production.items() if v)
            )

        # 2) صيانة الطعام والذهب
        total_troops = troops.infantry + troops.cavalry + troops.archers
        corruption = corruption_upkeep_multiplier(total_troops)
        food_upkeep = round(total_troops * 1 * corruption)
        gold_upkeep = round((troops.cavalry * 2 + troops.archers * 1) * corruption)

        production["food"] -= food_upkeep
        production["gold"] -= gold_upkeep
        if food_upkeep or gold_upkeep:
            report_lines.append(f"🍖 صيانة: -{food_upkeep} طعام، -{gold_upkeep} ذهب (فساد ×{corruption})")

        await db.update_player_resources(player.user_id, **production)
        player = await db.get_player(player.user_id)

        # 3) أزمة الطعام — موت الجنود
        if player.food <= 0 and total_troops > 0:
            deaths = max(1, round(total_troops * FOOD_CRISIS_DEATH_RATE))
            # يموت الجنود بالتناسب مع توزيع الجيش
            inf_d = round(deaths * (troops.infantry / total_troops)) if total_troops else 0
            cav_d = round(deaths * (troops.cavalry / total_troops)) if total_troops else 0
            arc_d = max(0, deaths - inf_d - cav_d)
            await db.update_troops(player.user_id, infantry=-inf_d, cavalry=-cav_d, archers=-arc_d)
            report_lines.append(f"☠️ أزمة طعام! مات {deaths} جندي بسبب الجوع.")

        # 4) أزمة السحر — مغادرة الكيانات
        if player.essence <= 0:
            if troops.wizard:
                await db.set_wizard(player.user_id, None, None)
                report_lines.append(f"🔮 نفد السحر — غادرك ساحرك **{troops.wizard}**!")
            if troops.beast:
                await db.set_beast(player.user_id, None, None)
                report_lines.append(f"🔮 نفد السحر — غادرك مخلوقك **{troops.beast}**!")

        # إعادة الجلب النهائي بعد كل التعديلات
        player = await db.get_player(player.user_id)
        buildings = await db.get_buildings(player.user_id)
        troops = await db.get_troops(player.user_id)
        power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture)

        # 5) تحديث اللوحات الثلاث تلقائياً (تحسين UX الأساسي المطلوب)
        king_ch = guild.get_channel(player.king_channel_id)
        war_ch = guild.get_channel(player.war_channel_id)
        magic_ch = guild.get_channel(player.magic_channel_id)

        await _find_and_update_panel(king_ch, embeds.throne_hall_embed(player, buildings), DashboardView(),
                                      title_prefix="🏰")
        await _find_and_update_panel(war_ch, embeds.war_divan_embed(player, troops, power), WarView(),
                                      title_prefix="⚔️")
        await _find_and_update_panel(magic_ch, embeds.magic_altar_embed(player, buildings, troops), MagicView(),
                                      title_prefix="🔮")

        # 6) تقرير الساعة يُرسل كرسالة جديدة أسفل لوحة king (سجل نظام مدمج بدل قناة بريد منفصلة)
        if king_ch and report_lines:
            await king_ch.send(embed=embeds.mail_log_embed(
                "🕐 تقرير الساعة", "\n".join(report_lines), 0x3498DB
            ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
