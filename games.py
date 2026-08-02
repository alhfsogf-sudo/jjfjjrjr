# -*- coding: utf-8 -*-
"""
كوغ الألعاب - يضيف 4 ألعاب تفاعلية عبر أزرار ديسكورد:
  - الدومنو (الدومنة)
  - المحيبس العراقية
  - المافيا
  - الشطرنج

لا يعتمد على أي مكتبة خارجية إضافية (فقط discord.py الموجودة أصلاً بالمشروع).
"""
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from domino_engine import DominoGame
from mheibes_engine import MheibesGame
from mafia_engine import MafiaGame
from chess_engine import ChessGame

log = logging.getLogger("games")

COLOR_MAIN = discord.Color.gold()
COLOR_WIN = discord.Color.green()
COLOR_INFO = discord.Color.blurple()
COLOR_ERROR = discord.Color.red()

LOBBY_TIMEOUT = 300      # 5 دقائق لانتظار انضمام اللاعبين
TURN_TIMEOUT = 600       # 10 دقائق قبل اعتبار اللاعب غائب (لا ينهي اللعبة تلقائيًا حاليًا لتفادي فقدان تقدم)


def tile_label(tile):
    return f"[{tile[0]}|{tile[1]}]"


def mention(uid):
    return f"<@{uid}>"


class LobbyView(discord.ui.View):
    """لوبي عام لانتظار انضمام اللاعبين قبل بدء أي لعبة."""

    def __init__(self, host_id, game_name, min_players, max_players, on_start, emoji="🎮"):
        super().__init__(timeout=LOBBY_TIMEOUT)
        self.host_id = host_id
        self.game_name = game_name
        self.min_players = min_players
        self.max_players = max_players
        self.on_start = on_start
        self.players = [host_id]
        self.message = None
        self.emoji = emoji
        self.closed = False

    def embed(self):
        e = discord.Embed(
            title=f"{self.emoji} لوبي {self.game_name}",
            description=(
                f"اضغط **انضمام** للمشاركة.\n"
                f"عدد اللاعبين المطلوب: {self.min_players}-{self.max_players}\n\n"
                f"**اللاعبون المنضمون ({len(self.players)}):**\n" +
                "\n".join(mention(p) for p in self.players)
            ),
            color=COLOR_MAIN,
        )
        e.set_footer(text="صاحب اللوبي هو من يستطيع بدء اللعبة أو إلغاءها.")
        return e

    async def refresh(self, interaction=None):
        if interaction is not None:
            await interaction.response.edit_message(embed=self.embed(), view=self)
        elif self.message:
            await self.message.edit(embed=self.embed(), view=self)

    @discord.ui.button(label="انضمام", style=discord.ButtonStyle.success, emoji="✅")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.closed:
            await interaction.response.send_message("انتهى هذا اللوبي.", ephemeral=True)
            return
        uid = interaction.user.id
        if uid in self.players:
            await interaction.response.send_message("أنت منضم أصلاً!", ephemeral=True)
            return
        if len(self.players) >= self.max_players:
            await interaction.response.send_message("اللوبي مكتمل.", ephemeral=True)
            return
        self.players.append(uid)
        await self.refresh(interaction)

    @discord.ui.button(label="انسحاب", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid == self.host_id:
            await interaction.response.send_message("أنت صاحب اللوبي، استخدم إلغاء بدل الانسحاب.", ephemeral=True)
            return
        if uid not in self.players:
            await interaction.response.send_message("أنت لست منضمًا.", ephemeral=True)
            return
        self.players.remove(uid)
        await self.refresh(interaction)

    @discord.ui.button(label="بدء اللعبة", style=discord.ButtonStyle.primary, emoji="🚀")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("فقط صاحب اللوبي يقدر يبدأ اللعبة.", ephemeral=True)
            return
        if len(self.players) < self.min_players:
            await interaction.response.send_message(
                f"تحتاج {self.min_players} لاعبين على الأقل (يوجد حاليًا {len(self.players)}).",
                ephemeral=True,
            )
            return
        self.closed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=self.embed(), view=self)
        await self.on_start(interaction, list(self.players))
        self.stop()

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("فقط صاحب اللوبي يقدر يلغي اللعبة.", ephemeral=True)
            return
        self.closed = True
        for child in self.children:
            child.disabled = True
        e = self.embed()
        e.title = f"🛑 تم إلغاء لوبي {self.game_name}"
        e.color = COLOR_ERROR
        await interaction.response.edit_message(embed=e, view=self)
        self.stop()

    async def on_timeout(self):
        if self.closed:
            return
        self.closed = True
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                e = self.embed()
                e.title = f"⏰ انتهى وقت لوبي {self.game_name}"
                await self.message.edit(embed=e, view=self)
            except Exception:
                pass


# ======================================================================
#  الدومنو
# ======================================================================
class DominoView(discord.ui.View):
    def __init__(self, cog, channel_id, game: DominoGame, names):
        super().__init__(timeout=TURN_TIMEOUT)
        self.cog = cog
        self.channel_id = channel_id
        self.game = game
        self.names = names  # {user_id: display_name}
        self.message = None
        self.pending_tile = None  # (tile) بانتظار اختيار الطرف

    def embed(self):
        g = self.game
        e = discord.Embed(title="🁢 لعبة الدومنو", color=COLOR_MAIN)
        e.add_field(name="الطاولة", value=g.board_string(), inline=False)
        if not g.finished:
            cur = g.current_player()
            e.add_field(name="الدور الحالي", value=mention(cur), inline=True)
            e.add_field(name="قطع الحوض المتبقية", value=str(len(g.boneyard)), inline=True)
            lines = []
            for pid in g.players:
                lines.append(f"{mention(pid)}: {len(g.hands[pid])} قطعة")
            e.add_field(name="اللاعبون", value="\n".join(lines), inline=False)
            if g.last_action:
                e.set_footer(text=f"آخر حركة: {g.last_action}")
        else:
            if g.winner == "tie":
                e.title = "🁢 انتهت لعبة الدومنو - تعادل!"
                e.color = COLOR_INFO
            else:
                e.title = "🁢 انتهت لعبة الدومنو!"
                e.color = COLOR_WIN
                e.add_field(name="🏆 الفائز", value=mention(g.winner), inline=False)
            if hasattr(g, "final_scores"):
                lines = [f"{mention(pid)}: {score} نقطة (مجموع النقاط بقطعه)" for pid, score in g.final_scores.items()]
                e.add_field(name="النتائج النهائية", value="\n".join(lines), inline=False)
            e.set_footer(text=g.last_action or "")
        return e

    async def update(self, interaction=None):
        if self.game.finished:
            for child in self.children:
                child.disabled = True
        if interaction is not None:
            await interaction.response.edit_message(embed=self.embed(), view=self)
        elif self.message:
            await self.message.edit(embed=self.embed(), view=self)

    async def send_hand_view(self, interaction: discord.Interaction):
        """يرسل يد اللاعب بشكل خاص (ephemeral) مع أزرار قطعه القابلة للعب."""
        g = self.game
        uid = interaction.user.id
        if uid not in g.players:
            await interaction.response.send_message("أنت لست من لاعبي هذه الجلسة.", ephemeral=True)
            return
        hand = g.hands[uid]
        hand_text = "  ".join(tile_label(t) for t in hand) if hand else "لا توجد قطع (فزت!)"
        view = HandView(self, uid) if uid == g.current_player() and not g.finished else None
        content = f"**يدك الحالية:**\n{hand_text}"
        if uid != g.current_player() and not g.finished:
            content += f"\n\n⏳ الدور الآن على {mention(g.current_player())}"
        await interaction.response.send_message(content, view=view, ephemeral=True)

    @discord.ui.button(label="عرض يدي", style=discord.ButtonStyle.primary, emoji="🃏")
    async def show_hand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_hand_view(interaction)

    @discord.ui.button(label="سحب / تمرير", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def draw_or_pass(self, interaction: discord.Interaction, button: discord.ui.Button):
        g = self.game
        uid = interaction.user.id
        if g.finished:
            await interaction.response.send_message("انتهت اللعبة.", ephemeral=True)
            return
        if uid != g.current_player():
            await interaction.response.send_message("ليس دورك الآن.", ephemeral=True)
            return
        if g.can_play(uid):
            await interaction.response.send_message("تملك قطعة قابلة للعب! استخدم زر عرض يدي.", ephemeral=True)
            return
        try:
            if g.boneyard:
                tile = g.draw(uid)
                await interaction.response.send_message(f"سحبت القطعة {tile_label(tile)} من الحوض.", ephemeral=True)
                if not g.can_play(uid):
                    g.pass_turn(uid)
            else:
                g.pass_turn(uid)
                await interaction.response.send_message("تم تمرير دورك (لا توجد قطع للسحب).", ephemeral=True)
        except ValueError as ex:
            await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
            return
        await self.update()


class HandView(discord.ui.View):
    """عرض قطع يد لاعب الدومنو القابلة للعب حاليًا، لاختيار قطعة ثم طرف اللعب."""

    def __init__(self, domino_view: DominoView, uid):
        super().__init__(timeout=120)
        self.domino_view = domino_view
        self.uid = uid
        options = domino_view.game.playable_tiles(uid)
        seen = set()
        for tile, end in options:
            key = (tile, end)
            if key in seen:
                continue
            seen.add(key)
            label = f"{tile_label(tile)} - {'أي طرف' if end == 'any' else ('يسار' if end == 'left' else 'يمين')}"
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.success)

            async def cb(interaction, tile=tile, end=end):
                if interaction.user.id != self.uid:
                    await interaction.response.send_message("هذه ليست يدك!", ephemeral=True)
                    return
                try:
                    self.domino_view.game.play(self.uid, tile, end)
                except ValueError as ex:
                    await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
                    return
                await interaction.response.send_message(f"لعبت القطعة {tile_label(tile)} ✅", ephemeral=True)
                await self.domino_view.update()

            btn.callback = cb
            self.add_item(btn)


# ======================================================================
#  المحيبس
# ======================================================================
class MheibesView(discord.ui.View):
    def __init__(self, cog, channel_id, game: MheibesGame):
        super().__init__(timeout=TURN_TIMEOUT)
        self.cog = cog
        self.channel_id = channel_id
        self.game = game
        self.message = None
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        g = self.game
        if g.game_over:
            return
        for uid in g.remaining_suspects():
            btn = discord.ui.Button(label="؟", style=discord.ButtonStyle.secondary, emoji="✊")

            async def cb(interaction, target=uid):
                await self._handle_guess(interaction, target)

            btn.callback = cb
            self.add_item(btn)

    def embed(self):
        g = self.game
        hiders_team = "أ" if g.hiding_team == "a" else "ب"
        guessers_team = "ب" if g.hiding_team == "a" else "أ"
        e = discord.Embed(title="🤲 لعبة المحيبس العراقية", color=COLOR_MAIN)
        if g.game_over:
            e.title = "🤲 انتهت لعبة المحيبس!"
            e.color = COLOR_WIN
            winner_name = "الفريق أ" if g.champion == "a" else "الفريق ب"
            e.add_field(name="🏆 الفائز", value=winner_name, inline=False)
            e.add_field(name="النتيجة النهائية", value=g.score_string(), inline=False)
            return e

        e.description = (
            f"الفريق **{hiders_team}** يخبّي المحبس هذه الجولة 🫙\n"
            f"الفريق **{guessers_team}** يخمّن الآن 🔍\n\n"
            f"اضغط على أحد اللاعبين أدناه لتخمين مين ماسك المحبس (فقط فريق التخمين يقدر يضغط)."
        )
        e.add_field(name="النتيجة", value=g.score_string(), inline=True)
        e.add_field(name="الجولة", value=str(g.round_number), inline=True)
        suspects_text = "\n".join(mention(u) for u in g.remaining_suspects())
        e.add_field(name="المشتبه بهم", value=suspects_text or "-", inline=False)
        if g.last_result == "wrong":
            e.set_footer(text="❌ تخمين خاطئ! جرّب لاعب ثاني.")
        return e

    async def _handle_guess(self, interaction: discord.Interaction, target):
        g = self.game
        guessing_team = g._guessers_team()
        team_members = g.team_a if guessing_team == "a" else g.team_b
        if interaction.user.id not in team_members:
            await interaction.response.send_message("أنت لست من فريق التخمين هذه الجولة.", ephemeral=True)
            return
        try:
            correct = g.guess(interaction.user.id, target)
        except ValueError as ex:
            await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
            return

        self._build_buttons()
        if g.game_over:
            for child in self.children:
                child.disabled = True

        result_text = "🎉 تخمين صحيح! المحبس كان معاه." if correct else "❌ تخمين خاطئ، هذا اللاعب مو ماسك المحبس."
        await interaction.response.edit_message(embed=self.embed(), view=self)
        await interaction.followup.send(result_text)


# ======================================================================
#  المافيا
# ======================================================================
class MafiaSession:
    def __init__(self, cog, channel, game: MafiaGame, member_names):
        self.cog = cog
        self.channel = channel
        self.game = game
        self.member_names = member_names  # {uid: display_name}
        self.day_view = None
        self.night_task = None
        self.mafia_choice = None
        self.doctor_choice = None
        self.detective_done = False

    def name(self, uid):
        return self.member_names.get(uid, str(uid))

    async def announce_roles(self):
        for pid in self.game.players:
            role = self.game.role_of(pid)
            extra = ""
            if role == "مافيا":
                partners = [self.name(p) for p in self.game.mafia_alive() if p != pid]
                if partners:
                    extra = "\nزملاؤك بالمافيا: " + "، ".join(partners)
                else:
                    extra = "\nأنت المافيا الوحيد."
            elif role == "طبيب":
                extra = "\nكل ليلة تقدر تحمي شخص واحد من القتل (تقدر تحمي نفسك)."
            elif role == "محقق":
                extra = "\nكل ليلة تقدر تحقق مع شخص لتعرف إذا كان مافيا أو لا."
            try:
                member = await self.cog.bot.fetch_user(pid)
                await member.send(f"🎭 دورك في لعبة المافيا هو: **{role}**{extra}")
            except Exception:
                await self.channel.send(
                    f"⚠️ ما قدرت أرسل رسالة خاصة لـ {mention(pid)}، تأكد إن الخاص مفتوح عندك للسيرفر.",
                )

    def alive_list_text(self):
        lines = []
        for pid in self.game.alive_players():
            lines.append(f"• {mention(pid)}")
        return "\n".join(lines) if lines else "-"

    async def start_night(self):
        g = self.game
        self.mafia_choice = None
        self.doctor_choice = None
        e = discord.Embed(
            title=f"🌙 الليلة {g.round_number}",
            description="نزلت الظلمة على القرية... المافيا والطبيب والمحقق يتحركون الآن سرًا عبر الخاص.\n"
                        "بانتظار انتهاء أفعال الليل (60 ثانية أو حتى يكتمل الجميع).",
            color=discord.Color.dark_blue(),
        )
        e.add_field(name="الأحياء", value=self.alive_list_text(), inline=False)
        await self.channel.send(embed=e)

        alive = g.alive_players()
        mafia_members = g.mafia_alive()
        doctors = [p for p in alive if g.role_of(p) == "طبيب"]
        detectives = [p for p in alive if g.role_of(p) == "محقق"]

        tasks = []
        mafia_title = "اختر ضحية الليلة (المافيا)"
        if len(mafia_members) > 1:
            mafia_title += " - إذا اخترتم أهداف مختلفة، يُعتمد آخر اختيار يصل"
        for m in mafia_members:
            tasks.append(self._send_night_action(m, mafia_title, alive, "mafia"))
        for d in doctors:
            tasks.append(self._send_night_action(d, "اختر من تريد حمايته الليلة (الطبيب)", alive, "doctor"))
        for det in detectives:
            tasks.append(self._send_night_action(det, "اختر من تريد التحقيق معه (المحقق)", alive, "detective"))

        if tasks:
            await asyncio.gather(*tasks)

        await asyncio.sleep(2)  # مهلة بسيطة لضمان وصول أي تفاعل أخير معلق
        await self.resolve_night_and_continue()

    async def _send_night_action(self, uid, title, alive_targets, role_kind):
        try:
            user = await self.cog.bot.fetch_user(uid)
        except Exception:
            return
        view = NightActionView(self, uid, alive_targets, role_kind)
        try:
            await user.send(title, view=view)
        except Exception:
            await self.channel.send(f"⚠️ ما قدرت أرسل خيارات الليل لـ {mention(uid)} (الخاص مغلق).")
            return
        await view.wait()

    async def resolve_night_and_continue(self):
        g = self.game
        if self.mafia_choice:
            g.submit_mafia_target(self.mafia_choice)
        if self.doctor_choice:
            g.submit_doctor_save(self.doctor_choice)
        killed = g.resolve_night()

        if killed:
            e = discord.Embed(
                title="☀️ الصباح جاء...",
                description=f"للأسف، تم العثور على {mention(killed)} مقتولًا هذا الصباح. 💀\n"
                            f"كان دوره: **{g.role_of(killed)}**",
                color=COLOR_ERROR,
            )
        else:
            e = discord.Embed(
                title="☀️ الصباح جاء...",
                description="لحسن الحظ، لم يمت أحد هذه الليلة! 🙏",
                color=COLOR_WIN,
            )
        e.add_field(name="الأحياء", value=self.alive_list_text(), inline=False)
        await self.channel.send(embed=e)

        if g.phase == MafiaGame.PHASE_OVER:
            await self.announce_game_over()
            return

        await self.start_day()

    async def start_day(self):
        g = self.game
        e = discord.Embed(
            title=f"💬 نقاش النهار {g.round_number}",
            description="ناقشوا الآن مين تشكون فيه! لديكم 60 ثانية قبل بدء التصويت.",
            color=COLOR_INFO,
        )
        e.add_field(name="الأحياء", value=self.alive_list_text(), inline=False)
        await self.channel.send(embed=e)
        await asyncio.sleep(60)
        if g.phase == MafiaGame.PHASE_OVER:
            return
        await self.start_vote()

    async def start_vote(self):
        g = self.game
        g.start_vote()
        view = VoteView(self)
        e = discord.Embed(
            title="🗳️ وقت التصويت!",
            description="صوّتوا على من تعتقدون أنه المافيا. صاحب أعلى الأصوات يُطرد.\nلديكم 45 ثانية.",
            color=COLOR_MAIN,
        )
        msg = await self.channel.send(embed=e, view=view)
        view.message = msg
        await asyncio.sleep(45)
        if g.phase != MafiaGame.PHASE_VOTE:
            return
        for child in view.children:
            child.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass
        eliminated, tie = g.resolve_vote()
        if tie:
            e2 = discord.Embed(title="🗳️ نتيجة التصويت", description="تعادل بالأصوات، ما حد يُطرد هالمرة.", color=COLOR_INFO)
        elif eliminated:
            e2 = discord.Embed(
                title="🗳️ نتيجة التصويت",
                description=f"تم طرد {mention(eliminated)} من القرية!\nكان دوره: **{g.role_of(eliminated)}**",
                color=COLOR_ERROR,
            )
        else:
            e2 = discord.Embed(title="🗳️ نتيجة التصويت", description="لم يصوّت أحد.", color=COLOR_INFO)
        e2.add_field(name="الأحياء", value=self.alive_list_text(), inline=False)
        await self.channel.send(embed=e2)

        if g.phase == MafiaGame.PHASE_OVER:
            await self.announce_game_over()
        else:
            await self.start_night()

    async def announce_game_over(self):
        g = self.game
        winner_text = "🏆 فازت **المافيا**!" if g.winner == "mafia" else "🏆 فازت **القرية**!"
        lines = [f"{mention(p)}: {g.role_of(p)}" for p in g.players]
        e = discord.Embed(title="🎬 انتهت لعبة المافيا!", description=winner_text, color=COLOR_WIN)
        e.add_field(name="الأدوار الكاملة", value="\n".join(lines), inline=False)
        await self.channel.send(embed=e)
        self.cog.mafia_sessions.pop(self.channel.id, None)


class NightActionView(discord.ui.View):
    def __init__(self, session: MafiaSession, uid, targets, role_kind):
        super().__init__(timeout=55)
        self.session = session
        self.uid = uid
        self.role_kind = role_kind
        self.done = False
        options = [
            discord.SelectOption(label=session.name(t)[:100], value=str(t))
            for t in targets
        ]
        select = discord.ui.Select(placeholder="اختر الهدف...", options=options[:25])

        async def cb(interaction):
            target = int(select.values[0])
            if self.role_kind == "mafia":
                self.session.mafia_choice = target
                await interaction.response.send_message(f"تم اختيار {session.name(target)} كضحية. 🗡️", ephemeral=True)
            elif self.role_kind == "doctor":
                self.session.doctor_choice = target
                await interaction.response.send_message(f"تم اختيار حماية {session.name(target)}. 💉", ephemeral=True)
            elif self.role_kind == "detective":
                is_mafia = self.session.game.submit_detective_check(target)
                verdict = "**مافيا!** 🔴" if is_mafia else "**بريء** 🟢"
                await interaction.response.send_message(f"نتيجة التحقيق مع {session.name(target)}: {verdict}", ephemeral=True)
            self.done = True
            self.stop()

        select.callback = cb
        self.add_item(select)

    async def on_timeout(self):
        self.stop()


class VoteView(discord.ui.View):
    def __init__(self, session: MafiaSession):
        super().__init__(timeout=50)
        self.session = session
        self.message = None
        g = session.game
        for pid in g.alive_players():
            btn = discord.ui.Button(label=session.name(pid)[:80], style=discord.ButtonStyle.danger)

            async def cb(interaction, target=pid):
                if not g.alive.get(interaction.user.id):
                    await interaction.response.send_message("الموتى لا يصوّتون 👻", ephemeral=True)
                    return
                try:
                    g.cast_vote(interaction.user.id, target)
                except ValueError as ex:
                    await interaction.response.send_message(f"❌ {ex}", ephemeral=True)
                    return
                await interaction.response.send_message(f"صوّتّ على {session.name(target)} ✅", ephemeral=True)

            btn.callback = cb
            self.add_item(btn)


# ======================================================================
#  الشطرنج
# ======================================================================
class ChessSession:
    def __init__(self, cog, channel, white_id, black_id, names):
        self.cog = cog
        self.channel = channel
        self.game = ChessGame()
        self.white_id = white_id
        self.black_id = black_id
        self.names = names
        self.message = None
        self.draw_offer_by = None

    def player_for(self, color):
        return self.white_id if color == "w" else self.black_id

    def color_of_player(self, uid):
        if uid == self.white_id:
            return "w"
        if uid == self.black_id:
            return "b"
        return None

    def embed(self, note=None):
        g = self.game
        turn_name = "الأبيض" if g.turn == "w" else "الأسود"
        turn_player = self.player_for(g.turn)
        e = discord.Embed(title="♟️ لعبة الشطرنج", color=COLOR_MAIN)
        e.add_field(
            name="اللاعبون",
            value=f"⚪ الأبيض: {mention(self.white_id)}\n⚫ الأسود: {mention(self.black_id)}",
            inline=False,
        )
        e.add_field(name="اللوحة", value=g.render_unicode(), inline=False)
        over, result = g.game_result()
        if over:
            e.title = "♟️ انتهت لعبة الشطرنج!"
            e.color = COLOR_WIN
            e.add_field(name="النتيجة", value=result, inline=False)
        else:
            e.add_field(name="الدور الحالي", value=f"{turn_name} ({mention(turn_player)})", inline=True)
            if g.is_in_check(g.turn):
                e.add_field(name="⚠️ تنبيه", value="الملك تحت الكش!", inline=True)
        if g.history_san:
            last_moves = g.history_san[-8:]
            e.add_field(name="آخر الحركات", value=" ".join(last_moves), inline=False)
        if note:
            e.set_footer(text=note)
        else:
            e.set_footer(text="استخدم /شطرنج-نقل مع نقلتك بصيغة مثل e2e4")
        return e

    async def refresh(self):
        if self.message:
            try:
                await self.message.edit(embed=self.embed())
            except Exception:
                pass


# ======================================================================
#  الكوغ الرئيسي
# ======================================================================
class Games(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.domino_games = {}    # channel_id -> DominoView
        self.mheibes_games = {}   # channel_id -> MheibesView
        self.mafia_sessions = {}  # channel_id -> MafiaSession
        self.chess_sessions = {}  # channel_id -> ChessSession

    # ------------------------------------------------------------------
    # قائمة مساعدة
    # ------------------------------------------------------------------
    @app_commands.command(name="العاب-مساعدة", description="عرض كل أوامر الألعاب المتوفرة بالبوت")
    async def games_help(self, interaction: discord.Interaction):
        e = discord.Embed(title="🎮 قائمة الألعاب المتوفرة", color=COLOR_MAIN)
        e.add_field(
            name="🁢 الدومنو",
            value="`/دومنو-ابدأ` لفتح لوبي (٢-٤ لاعبين). تُلعب عبر أزرار خاصة بكل لاعب.",
            inline=False,
        )
        e.add_field(
            name="🤲 المحيبس",
            value="`/محيبس-ابدأ` ثم انضم فريقين متساويين تقريبًا وابدأ. اضغط على لاعب لتخمينه.",
            inline=False,
        )
        e.add_field(
            name="🎭 المافيا",
            value="`/مافيا-ابدأ` لفتح لوبي (٤ لاعبين فأكثر). الأدوار تُرسل بالخاص، والتصويت بالقناة.",
            inline=False,
        )
        e.add_field(
            name="♟️ الشطرنج",
            value="`/شطرنج-تحدي @الخصم` لبدء تحدي، ثم `/شطرنج-نقل نقلة` مثل e2e4 أو Nf3.\n"
                  "`/شطرنج-لوحة` لعرض اللوحة، `/شطرنج-استسلام` للاستسلام.",
            inline=False,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ------------------------------------------------------------------
    # الدومنو
    # ------------------------------------------------------------------
    @app_commands.command(name="دومنو-ابدأ", description="فتح لوبي لعبة الدومنو (٢-٤ لاعبين)")
    async def domino_start(self, interaction: discord.Interaction):
        if interaction.channel_id in self.domino_games:
            await interaction.response.send_message("توجد لعبة دومنو شغالة بهذه القناة أصلاً!", ephemeral=True)
            return

        async def on_start(start_interaction, player_ids):
            game = DominoGame(player_ids)
            names = {}
            for pid in player_ids:
                try:
                    u = await self.bot.fetch_user(pid)
                    names[pid] = u.display_name
                except Exception:
                    names[pid] = str(pid)
            view = DominoView(self, start_interaction.channel_id, game, names)
            self.domino_games[start_interaction.channel_id] = view
            msg = await start_interaction.channel.send(embed=view.embed(), view=view)
            view.message = msg

        lobby = LobbyView(interaction.user.id, "الدومنو 🁢", 2, 4, on_start, emoji="🁢")
        await interaction.response.send_message(embed=lobby.embed(), view=lobby)
        lobby.message = await interaction.original_response()

    @app_commands.command(name="دومنو-انهاء", description="إنهاء لعبة الدومنو الحالية بهذه القناة (للطوارئ)")
    async def domino_end(self, interaction: discord.Interaction):
        view = self.domino_games.pop(interaction.channel_id, None)
        if not view:
            await interaction.response.send_message("لا توجد لعبة دومنو شغالة هنا.", ephemeral=True)
            return
        await interaction.response.send_message("تم إنهاء لعبة الدومنو. 🛑")

    # ------------------------------------------------------------------
    # المحيبس
    # ------------------------------------------------------------------
    @app_commands.command(name="محيبس-ابدأ", description="فتح لوبي المحيبس العراقية (فريقين متقاربين بالعدد)")
    async def mheibes_start(self, interaction: discord.Interaction):
        if interaction.channel_id in self.mheibes_games:
            await interaction.response.send_message("توجد لعبة محيبس شغالة بهذه القناة أصلاً!", ephemeral=True)
            return

        async def on_start(start_interaction, player_ids):
            if len(player_ids) < 4:
                await start_interaction.followup.send("تحتاج ٤ لاعبين على الأقل (فريقين لا يقل كل فريق عن لاعبين).")
                return
            mid = len(player_ids) // 2
            team_a = player_ids[:mid] if len(player_ids) % 2 == 0 else player_ids[: mid + 1]
            team_b = player_ids[len(team_a):]
            game = MheibesGame(team_a, team_b)
            view = MheibesView(self, start_interaction.channel_id, game)
            self.mheibes_games[start_interaction.channel_id] = view
            e = view.embed()
            e.add_field(
                name="تشكيل الفرق",
                value=f"**فريق أ:** {' '.join(mention(p) for p in team_a)}\n**فريق ب:** {' '.join(mention(p) for p in team_b)}",
                inline=False,
            )
            msg = await start_interaction.channel.send(embed=e, view=view)
            view.message = msg

        lobby = LobbyView(interaction.user.id, "المحيبس 🤲", 4, 16, on_start, emoji="🤲")
        await interaction.response.send_message(embed=lobby.embed(), view=lobby)
        lobby.message = await interaction.original_response()

    @app_commands.command(name="محيبس-انهاء", description="إنهاء لعبة المحيبس الحالية بهذه القناة (للطوارئ)")
    async def mheibes_end(self, interaction: discord.Interaction):
        view = self.mheibes_games.pop(interaction.channel_id, None)
        if not view:
            await interaction.response.send_message("لا توجد لعبة محيبس شغالة هنا.", ephemeral=True)
            return
        await interaction.response.send_message("تم إنهاء لعبة المحيبس. 🛑")

    # ------------------------------------------------------------------
    # المافيا
    # ------------------------------------------------------------------
    @app_commands.command(name="مافيا-ابدأ", description="فتح لوبي لعبة المافيا (٤ لاعبين فأكثر)")
    async def mafia_start(self, interaction: discord.Interaction):
        if interaction.channel_id in self.mafia_sessions:
            await interaction.response.send_message("توجد لعبة مافيا شغالة بهذه القناة أصلاً!", ephemeral=True)
            return

        async def on_start(start_interaction, player_ids):
            names = {}
            for pid in player_ids:
                try:
                    u = await self.bot.fetch_user(pid)
                    names[pid] = u.display_name
                except Exception:
                    names[pid] = str(pid)
            game = MafiaGame(player_ids)
            session = MafiaSession(self, start_interaction.channel, game, names)
            self.mafia_sessions[start_interaction.channel_id] = session
            await start_interaction.channel.send(
                "🎭 تم توزيع الأدوار! تحقق من رسائلك الخاصة (DM). سيبدأ الليل الأول خلال لحظات..."
            )
            await session.announce_roles()
            await asyncio.sleep(3)
            await session.start_night()

        lobby = LobbyView(interaction.user.id, "المافيا 🎭", 4, 15, on_start, emoji="🎭")
        await interaction.response.send_message(embed=lobby.embed(), view=lobby)
        lobby.message = await interaction.original_response()

    @app_commands.command(name="مافيا-انهاء", description="إنهاء لعبة المافيا الحالية بهذه القناة (للطوارئ)")
    async def mafia_end(self, interaction: discord.Interaction):
        session = self.mafia_sessions.pop(interaction.channel_id, None)
        if not session:
            await interaction.response.send_message("لا توجد لعبة مافيا شغالة هنا.", ephemeral=True)
            return
        await interaction.response.send_message("تم إنهاء لعبة المافيا. 🛑")

    # ------------------------------------------------------------------
    # الشطرنج
    # ------------------------------------------------------------------
    @app_commands.command(name="شطرنج-تحدي", description="تحدي عضو آخر بلعبة شطرنج")
    @app_commands.describe(الخصم="الشخص اللي تريد تتحداه")
    async def chess_challenge(self, interaction: discord.Interaction, الخصم: discord.Member):
        if interaction.channel_id in self.chess_sessions:
            await interaction.response.send_message("توجد لعبة شطرنج شغالة بهذه القناة أصلاً!", ephemeral=True)
            return
        if الخصم.bot:
            await interaction.response.send_message("ما تقدر تتحدى بوت 😅", ephemeral=True)
            return
        if الخصم.id == interaction.user.id:
            await interaction.response.send_message("ما تقدر تتحدى نفسك!", ephemeral=True)
            return

        challenger_id = interaction.user.id
        opponent_id = الخصم.id

        view = discord.ui.View(timeout=120)

        async def accept_cb(inner_interaction: discord.Interaction):
            if inner_interaction.user.id != opponent_id:
                await inner_interaction.response.send_message("هذا التحدي مو إلك!", ephemeral=True)
                return
            for child in view.children:
                child.disabled = True
            await inner_interaction.response.edit_message(view=view)
            names = {challenger_id: interaction.user.display_name, opponent_id: الخصم.display_name}
            session = ChessSession(self, interaction.channel, challenger_id, opponent_id, names)
            self.chess_sessions[interaction.channel_id] = session
            msg = await interaction.channel.send(embed=session.embed())
            session.message = msg

        async def decline_cb(inner_interaction: discord.Interaction):
            if inner_interaction.user.id != opponent_id:
                await inner_interaction.response.send_message("هذا التحدي مو إلك!", ephemeral=True)
                return
            for child in view.children:
                child.disabled = True
            await inner_interaction.response.edit_message(content="❌ تم رفض التحدي.", view=view)

        accept_btn = discord.ui.Button(label="قبول", style=discord.ButtonStyle.success, emoji="✅")
        decline_btn = discord.ui.Button(label="رفض", style=discord.ButtonStyle.danger, emoji="❌")
        accept_btn.callback = accept_cb
        decline_btn.callback = decline_cb
        view.add_item(accept_btn)
        view.add_item(decline_btn)

        await interaction.response.send_message(
            f"♟️ {mention(challenger_id)} تحدى {mention(opponent_id)} بلعبة شطرنج! هل تقبل؟",
            view=view,
        )

    @app_commands.command(name="شطرنج-نقل", description="نفّذ نقلة شطرنج (مثل e2e4 أو Nf3)")
    @app_commands.describe(نقلة="الحركة بصيغة إحداثية مثل e2e4، أو e7e8q للترقية لوزير")
    async def chess_move(self, interaction: discord.Interaction, نقلة: str):
        session = self.chess_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("لا توجد لعبة شطرنج شغالة بهذه القناة.", ephemeral=True)
            return
        g = session.game
        over, _ = g.game_result()
        if over:
            await interaction.response.send_message("انتهت اللعبة بالفعل.", ephemeral=True)
            return
        player_color = session.color_of_player(interaction.user.id)
        if player_color is None:
            await interaction.response.send_message("أنت لست طرفًا بهذه المباراة.", ephemeral=True)
            return
        if player_color != g.turn:
            await interaction.response.send_message("ليس دورك الآن.", ephemeral=True)
            return

        move = g.find_move(نقلة)
        if move is None:
            await interaction.response.send_message(
                "❌ نقلة غير شرعية أو صيغة غير مفهومة. استخدم صيغة مثل `e2e4` (من-إلى).",
                ephemeral=True,
            )
            return

        san = g.push(move)
        await interaction.response.send_message(f"✅ تم لعب: **{san}**")
        await session.refresh()

        over, result = g.game_result()
        if over:
            await interaction.channel.send(embed=discord.Embed(
                title="🏁 انتهت المباراة!", description=result, color=COLOR_WIN
            ))
            self.chess_sessions.pop(interaction.channel_id, None)

    @app_commands.command(name="شطرنج-لوحة", description="عرض لوحة الشطرنج الحالية بهذه القناة")
    async def chess_board(self, interaction: discord.Interaction):
        session = self.chess_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("لا توجد لعبة شطرنج شغالة بهذه القناة.", ephemeral=True)
            return
        await interaction.response.send_message(embed=session.embed())

    @app_commands.command(name="شطرنج-حركات", description="عرض قائمة الحركات الشرعية المتاحة لك الآن")
    async def chess_legal_moves(self, interaction: discord.Interaction):
        session = self.chess_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("لا توجد لعبة شطرنج شغالة بهذه القناة.", ephemeral=True)
            return
        g = session.game
        player_color = session.color_of_player(interaction.user.id)
        if player_color != g.turn:
            await interaction.response.send_message("ليس دورك الآن، أو أنت لست طرفًا بالمباراة.", ephemeral=True)
            return
        legal = g.legal_moves()
        sans = sorted(g.san_for(m, legal) for m in legal)
        text = ", ".join(sans) if sans else "لا توجد حركات متاحة"
        await interaction.response.send_message(f"**الحركات المتاحة ({len(sans)}):**\n{text}", ephemeral=True)

    @app_commands.command(name="شطرنج-استسلام", description="الاستسلام في مباراة الشطرنج الحالية")
    async def chess_resign(self, interaction: discord.Interaction):
        session = self.chess_sessions.get(interaction.channel_id)
        if not session:
            await interaction.response.send_message("لا توجد لعبة شطرنج شغالة بهذه القناة.", ephemeral=True)
            return
        player_color = session.color_of_player(interaction.user.id)
        if player_color is None:
            await interaction.response.send_message("أنت لست طرفًا بهذه المباراة.", ephemeral=True)
            return
        winner_id = session.black_id if player_color == "w" else session.white_id
        await interaction.response.send_message(
            f"🏳️ {mention(interaction.user.id)} استسلم! الفوز لـ {mention(winner_id)} 🏆"
        )
        self.chess_sessions.pop(interaction.channel_id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
    log.info("✅ تم تحميل كوغ الألعاب (دومنو / محيبس / مافيا / شطرنج)")
