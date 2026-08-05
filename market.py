"""cogs/market.py — Module 8: تسجيل View السوق الدائم + أمر أدمن لنشره."""
import discord
from discord import app_commands
from discord.ext import commands

from ui.market_view import MarketView
from utils import embeds


class Market(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(MarketView())

    @app_commands.command(name="setup_market", description="[أدمن] ينشر لوحة السوق الحرة في هذه القناة")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_market(self, interaction: discord.Interaction):
        e = embeds.mail_log_embed(
            "🤝 السوق الحرة",
            "اعرض مواردك للبيع بزر واحد، أو اشترِ من أي عرض معروض في هذه القناة.",
            0xF1C40F,
        )
        await interaction.channel.send(embed=e, view=MarketView())
        await interaction.response.send_message("✅ تم النشر.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Market(bot))
