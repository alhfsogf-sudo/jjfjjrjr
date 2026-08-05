"""ui/titan_view.py — زر مهاجمة التيتان في حدث غارة التيتان (PvE)."""
import discord

from core import database as db
from core.exceptions import PlayerNotFound
from utils import embeds
from utils.game_math import military_power


class TitanAttackView(discord.ui.View):
    def __init__(self, titan_state: dict):
        super().__init__(timeout=None)
        self.titan_state = titan_state  # {"hp": int, "max_hp": int}

    @discord.ui.button(label="⚔️ هاجم التيتان", style=discord.ButtonStyle.danger, custom_id="siyada:attack_titan")
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            player = await db.get_player(interaction.user.id)
            troops = await db.get_troops(interaction.user.id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture)
            damage = max(1, round(power))
            self.titan_state["hp"] = max(0, self.titan_state["hp"] - damage)

            remaining_pct = (self.titan_state["hp"] / self.titan_state["max_hp"]) * 100
            e = interaction.message.embeds[0]
            e.description = f"❤️ الصحة المتبقية: **{self.titan_state['hp']:,} / {self.titan_state['max_hp']:,}** ({remaining_pct:.1f}%)"
            await interaction.response.edit_message(embed=e, view=self)
            await interaction.followup.send(
                embed=embeds.success_embed(f"ألحقت **{damage:,}** ضرر بالتيتان!"), ephemeral=True)
        except PlayerNotFound as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)
