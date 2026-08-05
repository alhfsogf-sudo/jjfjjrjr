"""cogs/world_events.py — Module 9: الأحداث العالمية (المجاعة، الكسوف، التيتان)."""
import discord
import asyncio
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands, tasks

from config import NEWS_CHANNEL_ID, GUILD_ID
from utils import embeds
from ui.titan_view import TitanAttackView

great_famine_active = False
_titan = None  # {"hp": int, "max_hp": int, "ends_at": datetime, "message_id": int, "channel_id": int}


class WorldEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.weekly_check.start()
        self.titan_watchdog.start()

    def cog_unload(self):
        self.weekly_check.cancel()
        self.titan_watchdog.cancel()

    @tasks.loop(hours=1)
    async def weekly_check(self):
        now = datetime.now(timezone.utc)
        if now.weekday() in (0, 3) and now.hour == 12:  # الاثنين=0 الخميس=3
            import random
            event = random.choice(["famine", "eclipse", "titan"])
            await self._trigger(event)

    @weekly_check.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=10)
    async def titan_watchdog(self):
        global _titan
        if _titan is None:
            return
        now = datetime.now(timezone.utc)
        if now >= _titan["ends_at"]:
            guild = self.bot.get_guild(GUILD_ID)
            news_ch = guild.get_channel(NEWS_CHANNEL_ID) if guild else None
            if _titan["hp"] <= 0:
                text = "🎉 هُزم التيتان! كل اللاعبين يحصلون على +10,000🪙 و +5,000⛓️"
                from core import database as db
                for p in await db.get_all_players():
                    await db.update_player_resources(p.user_id, gold=10000, iron=5000)
            else:
                text = "💀 نجا التيتان! كل اللاعبين يخسرون 10% من طعامهم."
                from core import database as db
                for p in await db.get_all_players():
                    await db.update_player_resources(p.user_id, food=-round(p.food * 0.10))
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed("👹 انتهت غارة التيتان", text, 0x7F8C8D))
            _titan = None

    @titan_watchdog.before_loop
    async def before_titan(self):
        await self.bot.wait_until_ready()

    async def _trigger(self, event: str):
        global great_famine_active, _titan
        guild = self.bot.get_guild(GUILD_ID)
        news_ch = guild.get_channel(NEWS_CHANNEL_ID) if guild else None

        if event == "famine":
            great_famine_active = True
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed(
                    "☠️ المجاعة الكبرى بدأت!", "إنتاج الطعام ينخفض 50% لجميع اللاعبين لمدة 24 ساعة.", 0x7F1D1D))
            await asyncio.sleep(86400)
            great_famine_active = False
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed("☀️ انتهت المجاعة الكبرى", "", 0x27AE60))

        elif event == "eclipse":
            import cogs.magic as magic_module
            magic_module.mystic_eclipse_active = True
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed(
                    "🌑 الكسوف الصوفي بدأ!", "نسبة نجاح البعثات السحرية ارتفعت إلى 20% لمدة 24 ساعة.", 0x2C3E50))
            await asyncio.sleep(86400)
            magic_module.mystic_eclipse_active = False
            if news_ch:
                await news_ch.send(embed=embeds.mail_log_embed("🌕 انتهى الكسوف الصوفي", "", 0x27AE60))

        elif event == "titan":
            _titan = {
                "hp": 1_000_000, "max_hp": 1_000_000,
                "ends_at": datetime.now(timezone.utc).replace(microsecond=0) + __import__("datetime").timedelta(hours=24),
            }
            if news_ch:
                e = discord.Embed(
                    title="👹 غارة التيتان!",
                    description=f"❤️ الصحة المتبقية: **{_titan['hp']:,} / {_titan['max_hp']:,}** (100.0%)",
                    color=0x922B21,
                )
                await news_ch.send(embed=e, view=TitanAttackView(_titan))

    @app_commands.command(name="trigger_event", description="[أدمن] إطلاق حدث عالمي يدوياً")
    @app_commands.describe(event="famine / eclipse / titan")
    @app_commands.checks.has_permissions(administrator=True)
    async def trigger_event(self, interaction: discord.Interaction, event: str):
        if event not in ("famine", "eclipse", "titan"):
            await interaction.response.send_message("❌ استخدم: famine / eclipse / titan", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ جارٍ إطلاق حدث: {event}", ephemeral=True)
        self.bot.loop.create_task(self._trigger(event))


async def setup(bot: commands.Bot):
    await bot.add_cog(WorldEvents(bot))
