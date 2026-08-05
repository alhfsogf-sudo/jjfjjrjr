"""ui/main_menu.py — لوحة 'حالة إمبراطوريتي' العامة + زر تحديثها يدوياً (تحسين UX رئيسي)."""
import discord
import time

from core import database as db
from core.exceptions import PlayerNotFound, OnCooldown
from utils import embeds
from utils.game_math import military_power
from config import MANUAL_REFRESH_COOLDOWN_SECONDS

_last_refresh: dict[int, float] = {}


def _check_cooldown(user_id: int):
    now = time.time()
    last = _last_refresh.get(user_id, 0)
    if now - last < MANUAL_REFRESH_COOLDOWN_SECONDS:
        raise OnCooldown(int(MANUAL_REFRESH_COOLDOWN_SECONDS - (now - last)))
    _last_refresh[user_id] = now


class MainStatusView(discord.ui.View):
    """يُنشر في صندوق البريد — يعطي اللاعب نظرة شاملة وزر تحديث فوري بدون أوامر."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 تحديث حالتي الآن", style=discord.ButtonStyle.success,
                        custom_id="siyada:refresh_kingdom_status", row=0)
    async def refresh_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        try:
            _check_cooldown(user_id)
            player = await db.get_player(user_id)
            buildings = await db.get_buildings(user_id)
            troops = await db.get_troops(user_id)
            power = military_power(troops.infantry, troops.cavalry, troops.archers, player.culture)
            await db.touch_status_update(user_id)
            await interaction.response.send_message(
                embed=embeds.kingdom_status_embed(player, buildings, troops, power), ephemeral=True)
        except (PlayerNotFound, OnCooldown) as e:
            await interaction.response.send_message(embed=embeds.error_embed(e.message), ephemeral=True)

    @discord.ui.button(label="📖 كيف ألعب؟", style=discord.ButtonStyle.secondary,
                        custom_id="siyada:open_guide", row=0)
    async def open_guide(self, interaction: discord.Interaction, button: discord.ui.Button):
        from ui.guide_view import build_guide_pages, GuidePaginatorView
        pages = build_guide_pages()
        view = GuidePaginatorView(pages)
        view._sync_buttons()
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
