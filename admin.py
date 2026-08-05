"""cogs/admin.py — Module 10: أدوات الأدمن ومكافحة الغش. تبقى أوامر (أدمن فقط) لأنها أدوات إدارية
وليست تجربة لاعب، والطلب كان استبدال أوامر *اللاعبين* بأزرار."""
import discord
from discord import app_commands
from discord.ext import commands

from config import ADMIN_LOG_CHANNEL_ID
from core import database as db
from core.exceptions import PlayerNotFound
from utils import embeds

CHEAT_RAID_THRESHOLD = 5


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _log(self, guild: discord.Guild, text: str):
        ch = guild.get_channel(ADMIN_LOG_CHANNEL_ID)
        if ch:
            await ch.send(embed=embeds.mail_log_embed("🛠️ سجل الأدمن", text, 0x34495E))

    @app_commands.command(name="admin_give", description="[أدمن] إعطاء موارد للاعب")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_give(self, interaction: discord.Interaction, member: discord.Member,
                          resource: str, amount: int):
        try:
            await db.update_player_resources(member.id, **{resource: amount})
            await interaction.response.send_message(f"✅ أُعطي {member.mention} {amount} {resource}", ephemeral=True)
            await self._log(interaction.guild, f"{interaction.user.mention} أعطى {member.mention} {amount} {resource}")
        except Exception as e:
            await interaction.response.send_message(f"❌ خطأ: {e}", ephemeral=True)

    @app_commands.command(name="admin_remove_shield", description="[أدمن] إزالة درع لاعب")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_remove_shield(self, interaction: discord.Interaction, member: discord.Member):
        await db.remove_shield(member.id)
        await interaction.response.send_message(f"✅ أُزيل درع {member.mention}", ephemeral=True)
        await self._log(interaction.guild, f"{interaction.user.mention} أزال درع {member.mention}")

    @app_commands.command(name="admin_reset_player", description="[أدمن] حذف إمبراطورية لاعب بالكامل")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_reset_player(self, interaction: discord.Interaction, member: discord.Member):
        try:
            player = await db.get_player(member.id)
            guild = interaction.guild
            for ch_id in (player.king_channel_id, player.war_channel_id, player.magic_channel_id,
                          player.guide_channel_id, player.ally_channel_id):
                ch = guild.get_channel(ch_id)
                if ch:
                    await ch.delete(reason="حذف إمبراطورية")
            cat = guild.get_channel(player.category_id)
            if cat:
                await cat.delete(reason="حذف إمبراطورية")
            await db.delete_player(member.id)
            await interaction.response.send_message(f"✅ حُذفت إمبراطورية {member.mention}", ephemeral=True)
            await self._log(guild, f"{interaction.user.mention} حذف إمبراطورية {member.mention}")
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @app_commands.command(name="admin_list_players", description="[أدمن] عرض قائمة اللاعبين المسجلين")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_list_players(self, interaction: discord.Interaction):
        players = await db.get_all_players()
        lines = [f"<@{p.user_id}> — {p.culture} — 🪙{p.gold}" for p in players[:40]]
        await interaction.response.send_message(
            embed=embeds.mail_log_embed(f"👥 اللاعبون ({len(players)})", "\n".join(lines) or "لا يوجد", 0x34495E),
            ephemeral=True)

    @app_commands.command(name="admin_end_season", description="[أدمن] إعلان نهاية الموسم")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_end_season(self, interaction: discord.Interaction, winner: discord.Member):
        from config import NEWS_CHANNEL_ID
        news_ch = interaction.guild.get_channel(NEWS_CHANNEL_ID)
        if news_ch:
            await news_ch.send(embed=embeds.mail_log_embed(
                "🏆 نهاية الموسم!", f"الفائز بالموسم هو {winner.mention}! تهانينا لملك العالم الجديد 👑", 0xF1C40F))
        await interaction.response.send_message("✅ أُعلنت نهاية الموسم.", ephemeral=True)

    # ------------------------------------------------------------
    @commands.Cog.listener()
    async def on_raid_initiated_for_cheat_check(self, attacker_id: int, defender_id: int):
        counts = await db.count_raids_on_all_last_24h(attacker_id)
        total = sum(counts.values())
        if total > CHEAT_RAID_THRESHOLD:
            guild = self.bot.get_guild(__import__("config").GUILD_ID)
            if guild:
                await self._log(guild, f"⚠️ اشتباه غش: <@{attacker_id}> نفّذ {total} غارة خلال 24 ساعة.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
