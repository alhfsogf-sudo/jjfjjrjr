"""
bot.py — نقطة الدخول الرئيسية للبوت.
"""
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, GUILD_ID
from database import init_pool, close_pool

COGS = [
    "cogs.onboarding",
    "cogs.economy",
    "cogs.buildings",
    "cogs.military",
    "cogs.combat",
    "cogs.magic",
    "cogs.alliances",
    "cogs.market",
    "cogs.world_events",
    "cogs.admin",
    "cogs.help",
]


class SiyadaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = False
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        print("🔌 يتصل بقاعدة البيانات...")
        await init_pool()
        await create_tables()
        print("✅ قاعدة البيانات جاهزة.")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                print(f"✅ تم تحميل {cog}")
            except Exception as e:
                print(f"❌ فشل تحميل {cog}: {e}")

        # تسجيل الأزرار الدائمة الإضافية (المستقلة عن الـ cogs الفردية)
        from ui.main_menu import MainStatusView
        from ui.battle_result_view import BattleResultView
        self.add_view(MainStatusView())
        self.add_view(BattleResultView(loser_id=0, winner_id=0))  # placeholder ثابت custom_id فقط

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"✅ تمت مزامنة {len(synced)} أمر Slash (أدمن + /guide فقط).")

    async def on_ready(self):
        print(f"🚀 {self.user} جاهز ومتصل!")
        await self.change_presence(activity=discord.Game(name="⚔️ سيادة الأمم | /guide"))

    async def close(self):
        await close_pool()
        await super().close()


def main():
    bot = SiyadaBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
