# -*- coding: utf-8 -*-
"""
كوغ لعبة الريبلكا (لعبة الحروف والفئات) - مدمجة مع "الوزير":
  - الوزير نفسه (نفس محرك الذكاء الاصطناعي بكوغ Architect) هو من يحكّم صحة إجابات اللاعبين.
  - كل جولة تُختم ببطاقة صورة (Pillow) تعرض الحرف، إجابة كل لاعب، والنقاط.
  - النتيجة النهائية تُعرض بصورة ترتيب توضح الفائز/الفائزين وترتيب بقية اللاعبين.
  - يوجد ليدربورد دائم لكل سيرفر عبر أمر /ريبلكا-توب.
"""
import asyncio
import json
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

import config
from riplaca_engine import RiplacaGame
from riplaca_ai import judge_round
import riplaca_cards as cards

log = logging.getLogger("riplaca")

COLOR_MAIN = discord.Color.gold()
COLOR_WIN = discord.Color.green()
COLOR_INFO = discord.Color.blurple()
COLOR_ERROR = discord.Color.red()

LOBBY_TIMEOUT = 300
STOP_GRACE_SECONDS = 8  # مهلة بسيطة بعد ما أحد يضغط "ستوب" حتى يقدر البقية يرسلون إجاباتهم إذا خلصوا فعلاً

LEADERBOARD_PATH = os.path.join(os.path.dirname(config.LEADERBOARD_FILE), "riplaca_leaderboard.json")


def mention(uid):
    return f"<@{uid}>"


def load_riplaca_leaderboard():
    if os.path.exists(LEADERBOARD_PATH):
        try:
            with open(LEADERBOARD_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"❌ خطأ بقراءة ليدربورد الريبلكا: {e}")
            return {}
    return {}


def save_riplaca_leaderboard(data):
    try:
        os.makedirs(os.path.dirname(LEADERBOARD_PATH), exist_ok=True)
        with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        log.error(f"❌ خطأ بحفظ ليدربورد الريبلكا: {e}")


# ======================================================================
#  لوبي عام لانتظار اللاعبين
# ======================================================================
class LobbyView(discord.ui.View):
    def __init__(self, host_id, min_players, max_players, on_start, settings_text):
        super().__init__(timeout=LOBBY_TIMEOUT)
        self.host_id = host_id
        self.min_players = min_players
        self.max_players = max_players
        self.on_start = on_start
        self.settings_text = settings_text
        self.players = [host_id]
        self.message = None
        self.closed = False

    def embed(self):
        e = discord.Embed(
            title="🔤 لوبي الريبلكا",
            description=(
                f"اضغط **انضمام** للمشاركة.\n"
                f"عدد اللاعبين: {self.min_players}-{self.max_players}\n"
                f"{self.settings_text}\n\n"
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
        e.title = "🛑 تم إلغاء لوبي الريبلكا"
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
                e.title = "⏰ انتهى وقت لوبي الريبلكا"
                await self.message.edit(embed=e, view=self)
            except Exception:
                pass


# ======================================================================
#  نافذة إدخال الإجابات (Modal) - حتى ٥ فئات (حد ديسكورد للحقول)
# ======================================================================
class AnswerModal(discord.ui.Modal):
    def __init__(self, session, categories, letter):
        super().__init__(title=f"إجاباتك - حرف {letter}", timeout=300)
        self.session = session
        self.categories = categories
        self.inputs = []
        for cat in categories:
            ti = discord.ui.TextInput(
                label=f"{cat} (حرف {letter})",
                placeholder=f"اكتب {cat} يبدأ بحرف {letter}...",
                required=False,
                max_length=40,
            )
            self.inputs.append(ti)
            self.add_item(ti)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {cat: ti.value for cat, ti in zip(self.categories, self.inputs)}
        await self.session.submit_answers(interaction, answers)


# ======================================================================
#  عناصر التحكم أثناء الجولة (إرسال إجابات + ستوب)
# ======================================================================
class RoundView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=session.game.round_seconds + STOP_GRACE_SECONDS + 30)
        self.session = session

    @discord.ui.button(label="📝 أرسل إجاباتك", style=discord.ButtonStyle.primary)
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.session.game.players:
            await interaction.response.send_message("أنت لست من لاعبي هذه الجلسة.", ephemeral=True)
            return
        if self.session.round_locked:
            await interaction.response.send_message("انتهت هذه الجولة بالفعل.", ephemeral=True)
            return
        g = self.session.game
        modal = AnswerModal(self.session, g.current_round.categories, g.current_round.letter)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⏹️ ستوب!", style=discord.ButtonStyle.danger)
    async def stop_round(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.session.game.players:
            await interaction.response.send_message("أنت لست من لاعبي هذه الجلسة.", ephemeral=True)
            return
        if self.session.round_locked:
            await interaction.response.send_message("انتهت هذه الجولة بالفعل.", ephemeral=True)
            return
        if not self.session.game.current_round.has_submitted(uid):
            await interaction.response.send_message("لازم ترسل إجاباتك أولاً قبل ما تضغط ستوب!", ephemeral=True)
            return
        await interaction.response.send_message(f"⏹️ {interaction.user.display_name} ضغط ستوب! مهلة أخيرة قصيرة للبقية...", ephemeral=False)
        self.session.request_stop()


# ======================================================================
#  جلسة لعبة ريبلكا واحدة (قناة واحدة)
# ======================================================================
class RiplacaSession:
    def __init__(self, cog, channel, game: RiplacaGame, names: dict):
        self.cog = cog
        self.channel = channel
        self.game = game
        self.names = names
        self.round_locked = False
        self.stop_event = asyncio.Event()
        self.current_view: RoundView = None
        self.task: asyncio.Task = None

    def request_stop(self):
        self.stop_event.set()

    async def submit_answers(self, interaction: discord.Interaction, answers: dict):
        if self.round_locked:
            await interaction.response.send_message("انتهت هذه الجولة بالفعل.", ephemeral=True)
            return
        self.game.current_round.submit(interaction.user.id, answers)
        await interaction.response.send_message("✅ تم استلام إجاباتك! تقدر تعدلها بالضغط على الزر مجددًا لحد ما تنتهي الجولة.", ephemeral=True)

    async def run(self):
        try:
            while not self.game.finished:
                await self._play_round()
                if not self.game.finished:
                    await asyncio.sleep(6)
            await self._announce_final()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"❌ خطأ أثناء تشغيل جلسة الريبلكا: {e}")
            try:
                await self.channel.send(f"⚠️ حدث خطأ غير متوقع باللعبة، تم إيقافها: {e}")
            except Exception:
                pass
        finally:
            self.cog.sessions.pop(self.channel.id, None)

    async def _play_round(self):
        self.round_locked = False
        self.stop_event = asyncio.Event()
        r = self.game.start_next_round()

        view = RoundView(self)
        self.current_view = view
        e = discord.Embed(
            title=f"🔤 جولة {self.game.round_number}/{self.game.total_rounds} - حرف «{r.letter}»",
            description=(
                "أرسل إجابة لكل فئة تبدأ بالحرف أعلاه عبر زر **أرسل إجاباتك** 📝\n"
                f"لديك حتى **{self.game.round_seconds} ثانية**، أو اضغط **⏹️ ستوب** بعد إرسال إجاباتك لإنهاء الجولة مبكرًا.\n\n"
                "**الفئات:**\n" + "\n".join(f"• {c}" for c in r.categories)
            ),
            color=COLOR_MAIN,
        )
        e.add_field(name="اللاعبون", value="\n".join(mention(p) for p in self.game.players), inline=False)
        msg = await self.channel.send(embed=e, view=view)

        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=self.game.round_seconds)
        except asyncio.TimeoutError:
            pass
        else:
            # حد ضغط ستوب، نعطي مهلة قصيرة أخيرة للبقية
            await self.channel.send(f"⏳ {STOP_GRACE_SECONDS} ثواني أخيرة لإرسال إجاباتكم!")
            await asyncio.sleep(STOP_GRACE_SECONDS)

        self.round_locked = True
        for child in view.children:
            child.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        await self._resolve_round(r)

    async def _resolve_round(self, r):
        thinking = await self.channel.send("🧠 الوزير يراجع إجابات الجولة الآن...")
        verdicts = await judge_round(self.cog.bot, self.game, self.names)
        points = self.game.score_round(verdicts)
        try:
            await thinking.delete()
        except Exception:
            pass

        lines = []
        for pid in self.game.players:
            round_pts = sum(points.get(pid, {}).values())
            lines.append(f"{mention(pid)}: +{round_pts} نقطة (المجموع: {self.game.scores[pid]})")

        e = discord.Embed(
            title=f"📊 نتيجة الجولة {self.game.round_number}/{self.game.total_rounds} - حرف «{r.letter}»",
            description="\n".join(lines),
            color=COLOR_INFO,
        )

        buf = cards.render_round_card(
            r.letter, r.categories, self.game.players, self.names,
            points, r.answers, self.game.round_number, self.game.total_rounds,
        )
        if buf:
            file = discord.File(buf, filename="riplaca_round.png")
            e.set_image(url="attachment://riplaca_round.png")
            await self.channel.send(embed=e, file=file)
        else:
            for cat in r.categories:
                col = []
                for pid in self.game.players:
                    ans = r.answers.get(pid, {}).get(cat) or "-"
                    pts = points.get(pid, {}).get(cat, 0)
                    col.append(f"{self.names.get(pid, pid)}: {ans} ({'✅' if pts else '❌'} +{pts})")
                e.add_field(name=cat, value="\n".join(col), inline=False)
            await self.channel.send(embed=e)

    async def _announce_final(self):
        standings = self.game.standings()
        winners = self.game.winners()

        winners_text = " و ".join(mention(w) for w in winners)
        desc = f"🏆 **{'فاز' if len(winners) == 1 else 'فاز (بالتعادل)'}**: {winners_text}\n\n"
        desc += "**الترتيب الكامل:**\n"
        for idx, (pid, score) in enumerate(standings):
            medal = ["🥇", "🥈", "🥉"][idx] if idx < 3 else f"#{idx + 1}"
            desc += f"{medal} {mention(pid)} — {score} نقطة\n"

        e = discord.Embed(title="🏁 انتهت لعبة الريبلكا!", description=desc, color=COLOR_WIN)

        buf = cards.render_standings_card(
            standings, self.names, "🏁 النتيجة النهائية - الريبلكا",
            subtitle=f"بعد {self.game.total_rounds} جولات",
        )
        if buf:
            file = discord.File(buf, filename="riplaca_final.png")
            e.set_image(url="attachment://riplaca_final.png")
            await self.channel.send(embed=e, file=file)
        else:
            await self.channel.send(embed=e)

        self._update_persistent_leaderboard(standings, winners)

    def _update_persistent_leaderboard(self, standings, winners):
        guild_id = str(self.channel.guild.id) if self.channel.guild else "dm"
        data = load_riplaca_leaderboard()
        guild_data = data.setdefault(guild_id, {})
        for pid, score in standings:
            entry = guild_data.setdefault(str(pid), {"name": self.names.get(pid, str(pid)), "total_points": 0, "wins": 0, "games_played": 0})
            entry["name"] = self.names.get(pid, entry.get("name", str(pid)))
            entry["total_points"] += score
            entry["games_played"] += 1
            if pid in winners:
                entry["wins"] += 1
        save_riplaca_leaderboard(data)


# ======================================================================
#  الكوغ الرئيسي
# ======================================================================
class Riplaca(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions = {}  # channel_id -> RiplacaSession

    @app_commands.command(name="ريبلكا-مساعدة", description="شرح لعبة الريبلكا وطريقة اللعب")
    async def help_cmd(self, interaction: discord.Interaction):
        e = discord.Embed(title="🔤 لعبة الريبلكا", color=COLOR_MAIN)
        e.description = (
            "لعبة الحروف والفئات: كل جولة يعطيكم الوزير حرفًا وعدة فئات "
            "(دولة، مهنة، حيوان...)، وعليكم إرسال كلمة تبدأ بنفس الحرف لكل فئة.\n\n"
            "**النقاط:** إجابة صحيحة وفريدة = ١٠ نقاط، صحيحة لكن مكررة بين لاعبين = ٥ نقاط لكل واحد، خاطئة/فارغة = صفر.\n"
            "الوزير نفسه هو من يحكّم صحة إجاباتكم! 🧠"
        )
        e.add_field(name="/ريبلكا-ابدأ", value="فتح لوبي جديد (اختياري: عدد الجولات، عدد الفئات، مدة الجولة)", inline=False)
        e.add_field(name="/ريبلكا-انهاء", value="إنهاء اللعبة الحالية بهذه القناة (للطوارئ)", inline=False)
        e.add_field(name="/ريبلكا-توب", value="عرض ليدربورد اللعبة الدائم لهذا السيرفر", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="ريبلكا-ابدأ", description="فتح لوبي لعبة الريبلكا (٢ لاعبين فأكثر)")
    @app_commands.describe(
        الجولات="عدد جولات اللعبة (افتراضي ٥، الحد الأقصى ١٠)",
        الفئات="عدد الفئات بكل جولة (افتراضي ٥، الحد الأقصى ٥)",
        مدة_الجولة="مدة الجولة بالثواني (افتراضي ٩٠)",
    )
    async def start(
        self,
        interaction: discord.Interaction,
        الجولات: app_commands.Range[int, 1, 10] = 5,
        الفئات: app_commands.Range[int, 3, 5] = 5,
        مدة_الجولة: app_commands.Range[int, 30, 240] = 90,
    ):
        if interaction.channel_id in self.sessions:
            await interaction.response.send_message("توجد لعبة ريبلكا شغالة بهذه القناة أصلاً!", ephemeral=True)
            return

        settings_text = f"الجولات: {الجولات} | الفئات بالجولة: {الفئات} | مدة الجولة: {مدة_الجولة} ثانية"

        async def on_start(start_interaction, player_ids):
            names = {}
            for pid in player_ids:
                try:
                    u = await self.bot.fetch_user(pid)
                    names[pid] = u.display_name
                except Exception:
                    names[pid] = str(pid)

            game = RiplacaGame(player_ids, total_rounds=الجولات, categories_per_round=الفئات, round_seconds=مدة_الجولة)
            session = RiplacaSession(self, start_interaction.channel, game, names)
            self.sessions[start_interaction.channel_id] = session
            await start_interaction.channel.send(
                f"🔤 بدأت لعبة الريبلكا! ({settings_text})\nحظ موفق للجميع 🍀"
            )
            session.task = asyncio.create_task(session.run())

        lobby = LobbyView(interaction.user.id, 2, 12, on_start, settings_text)
        await interaction.response.send_message(embed=lobby.embed(), view=lobby)
        lobby.message = await interaction.original_response()

    @app_commands.command(name="ريبلكا-انهاء", description="إنهاء لعبة الريبلكا الحالية بهذه القناة (للطوارئ)")
    async def end(self, interaction: discord.Interaction):
        session = self.sessions.pop(interaction.channel_id, None)
        if not session:
            await interaction.response.send_message("لا توجد لعبة ريبلكا شغالة هنا.", ephemeral=True)
            return
        if session.task:
            session.task.cancel()
        await interaction.response.send_message("تم إنهاء لعبة الريبلكا. 🛑")

    @app_commands.command(name="ريبلكا-توب", description="عرض ليدربورد لعبة الريبلكا الدائم لهذا السيرفر")
    async def top(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        data = load_riplaca_leaderboard()
        guild_data = data.get(guild_id, {})
        if not guild_data:
            await interaction.response.send_message("لا توجد بيانات ريبلكا مسجلة بهذا السيرفر بعد.", ephemeral=True)
            return

        sorted_entries = sorted(guild_data.items(), key=lambda kv: kv[1]["total_points"], reverse=True)[:10]
        standings = [(int(uid), entry["total_points"]) for uid, entry in sorted_entries]
        names = {int(uid): entry["name"] for uid, entry in sorted_entries}

        lines = []
        for idx, (uid, entry) in enumerate(sorted_entries):
            medal = ["🥇", "🥈", "🥉"][idx] if idx < 3 else f"#{idx + 1}"
            lines.append(f"{medal} {mention(int(uid))} — {entry['total_points']} نقطة ({entry['wins']} فوز من {entry['games_played']} لعبة)")

        e = discord.Embed(title="🏆 ليدربورد الريبلكا الدائم", description="\n".join(lines), color=COLOR_MAIN)

        buf = cards.render_standings_card(standings, names, "🏆 ليدربورد الريبلكا", subtitle=interaction.guild.name if interaction.guild else None)
        if buf:
            file = discord.File(buf, filename="riplaca_top.png")
            e.set_image(url="attachment://riplaca_top.png")
            await interaction.response.send_message(embed=e, file=file)
        else:
            await interaction.response.send_message(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Riplaca(bot))
    log.info("✅ تم تحميل كوغ لعبة الريبلكا (مدمجة مع الوزير)")
