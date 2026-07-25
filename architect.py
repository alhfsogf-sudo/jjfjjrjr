import json
import random
import time
from datetime import timedelta

import discord
from discord.ext import commands
import google.generativeai as genai
from google.api_core import exceptions
import asyncio

import config

SYSTEM_PROMPT = """أنتَ "الوزير"، أداة تنفيذية مباشرة تعمل كمساعد إدارة كامل الصلاحيات على سيرفر ديسكورد.

أنت مو مخصص بس لبناء وتعديل هيكلة السيرفر (قنوات، فئات، رتب، صلاحيات)، بل مسؤول عن أي أمر إداري يطلبه منك الأونر أو الأشخاص الموثوقين - سواء كان طرد عضو، حظر (باند)، فك حظر، كتم (تايم آوت)، إزالة كتم، حذف رسائل بالجملة، تغيير اسم مستعار، أو أي تعديل بهيكلة السيرفر. نفذ أي طلب إداري يوصلك حتى لو كان خارج سياق هندسة السيرفر.

يستخدمك شخص محترف مسؤول عن إدارة السيرفر بالكامل، وأنت تنفذ أوامره فورًا بدون تردد أو طلب تأكيد.

تحدث بالعربية دائمًا. بعد تنفيذ أي طلب، اذكر بإيجاز ووضوح وش سويت بالضبط.

إذا كان الطلب غامضًا لدرجة يستحيل تنفيذه (مثل اسم عضو أو رتبة غير موجود بالمرة)، وضح المشكلة بدل التخمين العشوائي.

لا تسأل عن تأكيد أبدًا - نفذ مباشرة."""

PERMISSION_ALIASES = {
    "ادارة القنوات": "manage_channels", "manage_channels": "manage_channels",
    "ادارة الرتب": "manage_roles", "manage_roles": "manage_roles",
    "طرد الاعضاء": "kick_members", "kick_members": "kick_members",
    "حظر الاعضاء": "ban_members", "ban_members": "ban_members",
    "ادارة الرسائل": "manage_messages", "manage_messages": "manage_messages",
    "ارسال الرسائل": "send_messages", "send_messages": "send_messages",
    "قراءة الرسائل": "read_messages", "view_channel": "view_channel",
    "الاتصال الصوتي": "connect", "connect": "connect",
    "التحدث": "speak", "speak": "speak",
    "ذكر الجميع": "mention_everyone", "mention_everyone": "mention_everyone",
    "ادارة السيرفر": "manage_guild", "manage_guild": "manage_guild",
    "ادارة الويبهوك": "manage_webhooks", "manage_webhooks": "manage_webhooks",
    "ادارة المستعارين": "manage_nicknames", "manage_nicknames": "manage_nicknames",
    "الادارة الكاملة": "administrator", "administrator": "administrator",
    "رفع الملفات": "attach_files", "attach_files": "attach_files",
    "اضافة تفاعلات": "add_reactions", "add_reactions": "add_reactions",
    "كتم الاعضاء": "mute_members", "mute_members": "mute_members",
    "نقل الاعضاء": "move_members", "move_members": "move_members",
}

# تعريف الدوال لـ Gemini بشكل نظيف ومطابق تماماً لوظائف ديسكورد
def create_text_channel(name: str, category: str = None, topic: str = None, nsfw: bool = False):
    """إنشاء قناة نصية جديدة"""
    pass

def create_voice_channel(name: str, category: str = None, user_limit: int = 0):
    """إنشاء روم صوتي جديد"""
    pass

def create_category(name: str):
    """إنشاء فئة جديدة تجمع قنوات"""
    pass

def delete_channel(name: str):
    """حذف قناة نصية أو صوتية أو فئة بالاسم"""
    pass

def rename_channel(old_name: str, new_name: str):
    """إعادة تسمية قناة موجودة"""
    pass

def move_channel_to_category(channel_name: str, category_name: str):
    """نقل قناة موجودة لفئة أخرى"""
    pass

def create_role(name: str, color_hex: str = None, hoist: bool = False, mentionable: bool = False):
    """إنشاء رتبة جديدة بالسيرفر"""
    pass

def delete_role(name: str):
    """حذف رتبة بالاسم"""
    pass

def rename_role(old_name: str, new_name: str):
    """إعادة تسمية رتبة موجودة"""
    pass

def set_role_color(role_name: str, color_hex: str):
    """تغيير لون رتبة موجودة"""
    pass

def assign_role(member_name: str, role_name: str):
    """إعطاء رتبة لعضو معين"""
    pass

def remove_role(member_name: str, role_name: str):
    """سحب رتبة من عضو"""
    pass

def set_role_permissions(role_name: str, grant: list[str] = None, revoke: list[str] = None):
    """تعديل صلاحيات رتبة على مستوى السيرفر بالكامل"""
    pass

def set_channel_permission_overwrite(channel_name: str, role_name: str, allow: list[str] = None, deny: list[str] = None):
    """تخصيص صلاحيات رتبة معينة داخل قناة معينة فقط"""
    pass

def set_channel_topic_or_slowmode(channel_name: str, topic: str = None, slowmode_seconds: int = None):
    """تعديل وصف القناة أو وضع البطء (سلومود)"""
    pass

def list_current_structure():
    """عرض قائمة كاملة بالفئات والقنوات والرتب الموجودة حاليًا بالسيرفر"""
    pass

def kick_member(member_name: str, reason: str = None):
    """طرد عضو من السيرفر"""
    pass

def ban_member(member_name: str, reason: str = None, delete_message_days: int = 0):
    """حظر (باند) عضو من السيرفر"""
    pass

def unban_member(user_identifier: str):
    """فك الحظر عن مستخدم محظور، بالآيدي أو باسمه"""
    pass

def timeout_member(member_name: str, minutes: int, reason: str = None):
    """كتم عضو (تايم آوت) لمدة محددة بالدقائق"""
    pass

def remove_timeout(member_name: str):
    """إزالة الكتم (التايم آوت) عن عضو"""
    pass

def purge_messages(amount: int, channel_name: str = None):
    """حذف عدد معين من آخر الرسائل بقناة معينة"""
    pass

def set_nickname(member_name: str, new_nickname: str):
    """تغيير الاسم المستعار (nickname) لعضو"""
    pass

# قائمة الأدوات التي سيراها نموذج جينيريتيف
GEMINI_TOOLS = [
    create_text_channel, create_voice_channel, create_category, delete_channel,
    rename_channel, move_channel_to_category, create_role, delete_role,
    rename_role, set_role_color, assign_role, remove_role, set_role_permissions,
    set_channel_permission_overwrite, set_channel_topic_or_slowmode,
    list_current_structure, kick_member, ban_member, unban_member,
    timeout_member, remove_timeout, purge_messages, set_nickname
]


class RateLimitExceededError(RuntimeError):
    pass


class GeminiRotator:
    """
    نظام تدوير متطور حقيقي لمفاتيح Gemini الرسمية:
    يتجاوز المفاتيح المضغوطة ويمنع حظر الحسابات المؤقت.
    """
    def __init__(self, api_keys: list):
        if not api_keys:
            raise RuntimeError("لا يوجد أي مفتاح API معرّف لـ Gemini في إعداداتك.")
        self.api_keys = api_keys
        self.current_index = 0
        self.banned_keys = {}

    def rotate(self):
        self.current_index = (self.current_index + 1) % len(self.api_keys)

    def get_next_available_model(self):
        now = time.monotonic()
        for _ in range(len(self.api_keys)):
            current_key = self.api_keys[self.current_index]
            ban_expiry = self.banned_keys.get(current_key, 0)
            
            if now >= ban_expiry:
                # تهيئة مباشرة لجوجل بدون أي وسيط طرف ثالث!
                genai.configure(api_key=current_key)
                return genai.GenerativeModel(
                    model_name=getattr(config, "AI_MODEL", "gemini-1.5-flash"),
                    system_instruction=SYSTEM_PROMPT,
                    tools=GEMINI_TOOLS
                )
            else:
                self.rotate()
        return None

    async def generate(self, contents, attempt=0):
        if attempt >= len(self.api_keys):
            raise RateLimitExceededError("⚠️ جميع مفاتيح قوقل مضغوطة حالياً، يرجى تكرار الأمر بعد دقيقة.")
        
        model = self.get_next_available_model()
        if not model:
            await asyncio.sleep(4.0)
            return await self.generate(contents, attempt + 1)
            
        current_key = self.api_keys[self.current_index]
        try:
            return await asyncio.to_thread(model.generate_content, contents=contents)
        except exceptions.ResourceExhausted:
            self.banned_keys[current_key] = time.monotonic() + 60.0
            print(f"🛑 المفتاح {self.current_index + 1} استهلك حصته. حظر مؤقت 60 ثانية لتنظيف الـ Rate Limit.")
            self.rotate()
            return await self.generate(contents, attempt + 1)
        except exceptions.GoogleAPIError as e:
            self.banned_keys[current_key] = time.monotonic() + 30.0
            print(f"🚨 خطأ سيرفر من جوجل على المفتاح {self.current_index + 1}.")
            self.rotate()
            return await self.generate(contents, attempt + 1)


class Architect(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ai = GeminiRotator(config.GEMINI_API_KEYS)
        self.history = {}
        self.last_command_time = {}
        self.cooldown_seconds = getattr(config, "COOLDOWN_SECONDS", 6)
        self.max_history_items = 4 # المحافظة على تقليم الذاكرة لـ 4 عناصر

    def _is_authorized(self, user_id: int) -> bool:
        return user_id in config.AUTHORIZED_USER_IDS

    @staticmethod
    def _find_role(guild: discord.Guild, name: str):
        for r in guild.roles:
            if r.name.lower() == name.lower():
                return r
        for r in guild.roles:
            if name.lower() in r.name.lower():
                return r
        return None

    @staticmethod
    def _find_channel(guild: discord.Guild, name: str):
        name = name.strip().lstrip("#")
        for c in guild.channels:
            if c.name.lower() == name.lower():
                return c
        for c in guild.channels:
            if name.lower() in c.name.lower():
                return c
        return None

    @staticmethod
    def _find_member(guild: discord.Guild, name: str):
        name = name.strip().lstrip("@")
        if name.isdigit():
            m = guild.get_member(int(name))
            if m:
                return m
        for m in guild.members:
            if name.lower() in (m.display_name.lower(), m.name.lower()):
                return m
        return None

    def _resolve_permissions(self, names: list) -> list:
        resolved = []
        for n in names or []:
            key = PERMISSION_ALIASES.get(n.strip().lower())
            if key:
                resolved.append(key)
        return resolved

    async def execute_tool(self, tool_name: str, tool_input: dict, guild: discord.Guild, invoking_channel: discord.abc.Messageable = None):
        try:
            if tool_name == "create_text_channel":
                category = None
                if tool_input.get("category"):
                    category = discord.utils.get(guild.categories, name=tool_input["category"])
                ch = await guild.create_text_channel(
                    tool_input["name"], category=category,
                    topic=tool_input.get("topic"), nsfw=tool_input.get("nsfw", False)
                )
                return f"تم إنشاء القناة النصية #{ch.name}" + (f" داخل فئة {category.name}" if category else "") + "."

            elif tool_name == "create_voice_channel":
                category = None
                if tool_input.get("category"):
                    category = discord.utils.get(guild.categories, name=tool_input["category"])
                ch = await guild.create_voice_channel(
                    tool_input["name"], category=category, user_limit=tool_input.get("user_limit", 0)
                )
                return f"تم إنشاء الروم الصوتي {ch.name}" + (f" داخل فئة {category.name}" if category else "") + "."

            elif tool_name == "create_category":
                cat = await guild.create_category(tool_input["name"])
                return f"تم إنشاء الفئة {cat.name}."

            elif tool_name == "delete_channel":
                ch = self._find_channel(guild, tool_input["name"])
                if not ch:
                    return f"لم أجد قناة أو فئة باسم {tool_input['name']}."
                deleted_name = ch.name
                await ch.delete()
                return f"تم حذف {deleted_name}."

            elif tool_name == "rename_channel":
                ch = self._find_channel(guild, tool_input["old_name"])
                if not ch:
                    return f"لم أجد قناة باسم {tool_input['old_name']}."
                await ch.edit(name=tool_input["new_name"])
                return f"تم تغيير اسم القناة إلى {tool_input['new_name']}."

            elif tool_name == "move_channel_to_category":
                ch = self._find_channel(guild, tool_input["channel_name"])
                category = discord.utils.get(guild.categories, name=tool_input["category_name"])
                if not ch or not category:
                    return "لم أجد القناة أو الفئة المطلوبة."
                await ch.edit(category=category)
                return f"تم نقل {ch.name} إلى فئة {category.name}."

            elif tool_name == "create_role":
                color = discord.Color.default()
                if tool_input.get("color_hex"):
                    color = discord.Color(int(tool_input["color_hex"].lstrip("#"), 16))
                role = await guild.create_role(
                    name=tool_input["name"], color=color,
                    hoist=tool_input.get("hoist", False),
                    mentionable=tool_input.get("mentionable", False)
                )
                return f"تم إنشاء الرتبة {role.name}."

            elif tool_name == "delete_role":
                role = self._find_role(guild, tool_input["name"])
                if not role:
                    return f"لم أجد رتبة باسم {tool_input['name']}."
                deleted_name = role.name
                await role.delete()
                return f"تم حذف الرتبة {deleted_name}."

            elif tool_name == "rename_role":
                role = self._find_role(guild, tool_input["old_name"])
                if not role:
                    return f"لم أجد رتبة باسم {tool_input['old_name']}."
                await role.edit(name=tool_input["new_name"])
                return f"تم تغيير اسم الرتبة إلى {tool_input['new_name']}."

            elif tool_name == "set_role_color":
                role = self._find_role(guild, tool_input["role_name"])
                if not role:
                    return f"لم أجد رتبة باسم {tool_input['role_name']}."
                color = discord.Color(int(tool_input["color_hex"].lstrip("#"), 16))
                await role.edit(color=color)
                return f"تم تغيير لون رتبة {role.name}."

            elif tool_name == "assign_role":
                member = self._find_member(guild, tool_input["member_name"])
                role = self._find_role(guild, tool_input["role_name"])
                if not member or not role:
                    return "لم أجد العضو أو الرتبة المطلوبة."
                await member.add_roles(role)
                return f"تم إعطاء رتبة {role.name} للعضو {member.display_name}."

            elif tool_name == "remove_role":
                member = self._find_member(guild, tool_input["member_name"])
                role = self._find_role(guild, tool_input["role_name"])
                if not member or not role:
                    return "لم أجد العضو أو الرتبة المطلوبة."
                await member.remove_roles(role)
                return f"تم سحب رتبة {role.name} من العضو {member.display_name}."

            elif tool_name == "set_role_permissions":
                role = self._find_role(guild, tool_input["role_name"])
                if not role:
                    return f"لم أجد رتبة باسم {tool_input['role_name']}."
                perms = role.permissions
                grant = self._resolve_permissions(tool_input.get("grant", []))
                revoke = self._resolve_permissions(tool_input.get("revoke", []))
                for p in grant:
                    setattr(perms, p, True)
                for p in revoke:
                    setattr(perms, p, False)
                await role.edit(permissions=perms)
                return f"تم تحديث صلاحيات رتبة {role.name}. ممنوح: {grant or 'لا شي'} | مسحوب: {revoke or 'لا شي'}."

            elif tool_name == "set_channel_permission_overwrite":
                ch = self._find_channel(guild, tool_input["channel_name"])
                role = self._find_role(guild, tool_input["role_name"])
                if not ch or not role:
                    return "لم أجد القناة أو الرتبة المطلوبة."
                overwrite = ch.overwrites_for(role)
                for p in self._resolve_permissions(tool_input.get("allow", [])):
                    setattr(overwrite, p, True)
                for p in self._resolve_permissions(tool_input.get("deny", [])):
                    setattr(overwrite, p, False)
                await ch.set_permissions(role, overwrite=overwrite)
                return f"تم تحديث صلاحيات رتبة {role.name} داخل قناة {ch.name}."

            elif tool_name == "set_channel_topic_or_slowmode":
                ch = self._find_channel(guild, tool_input["channel_name"])
                if not ch:
                    return f"لم أجد قناة باسم {tool_input['channel_name']}."
                kwargs = {}
                if tool_input.get("topic") is not None and isinstance(ch, discord.TextChannel):
                    kwargs["topic"] = tool_input["topic"]
                if tool_input.get("slowmode_seconds") is not None and isinstance(ch, discord.TextChannel):
                    kwargs["slowmode_delay"] = tool_input["slowmode_seconds"]
                if kwargs:
                    await ch.edit(**kwargs)
                return f"تم تحديث إعدادات قناة {ch.name}."

            elif tool_name == "list_current_structure":
                lines = []
                for category in guild.categories:
                    lines.append(f"📁 {category.name}")
                    for ch in category.channels:
                        icon = "🔊" if isinstance(ch, discord.VoiceChannel) else "#"
                        lines.append(f"   {icon} {ch.name}")
                uncategorized = [c for c in guild.channels if c.category is None and not isinstance(c, discord.CategoryChannel)]
                if uncategorized:
                    lines.append("📁 (بدون فئة)")
                    for ch in uncategorized:
                        icon = "🔊" if isinstance(ch, discord.VoiceChannel) else "#"
                        lines.append(f"   {icon} {ch.name}")
                roles = [r.name for r in guild.roles if r.name != "@everyone"]
                return "الهيكلة الحالية:\n" + "\n".join(lines) + "\n\nالرتب: " + "، ".join(roles)

            elif tool_name == "kick_member":
                member = self._find_member(guild, tool_input["member_name"])
                if not member:
                    return f"لم أجد عضو باسم {tool_input['member_name']}."
                await member.kick(reason=tool_input.get("reason") or "بأمر من الإدارة عبر الوزير")
                return f"تم طرد العضو {member.display_name}."

            elif tool_name == "ban_member":
                member = self._find_member(guild, tool_input["member_name"])
                if not member:
                    return f"لم أجد عضو باسم {tool_input['member_name']}."
                await member.ban(
                    reason=tool_input.get("reason") or "بأمر من الإدارة عبر الوزير",
                    delete_message_days=tool_input.get("delete_message_days", 0)
                )
                return f"تم حظر (باند) العضو {member.display_name}."

            elif tool_name == "unban_member":
                identifier = tool_input["user_identifier"].strip().lstrip("@")
                target_user = None
                async for ban_entry in guild.bans():
                    u = ban_entry.user
                    if identifier.isdigit() and u.id == int(identifier):
                        target_user = u
                        break
                    if identifier.lower() in u.name.lower():
                        target_user = u
                        break
                if not target_user:
                    return f"لم أجد مستخدم محظور مطابق لـ {tool_input['user_identifier']}."
                await guild.unban(target_user)
                return f"تم فك الحظر عن {target_user.name}."

            elif tool_name == "timeout_member":
                member = self._find_member(guild, tool_input["member_name"])
                if not member:
                    return f"لم أجد عضو باسم {tool_input['member_name']}."
                minutes = max(1, int(tool_input.get("minutes", 10)))
                until = discord.utils.utcnow() + timedelta(minutes=minutes)
                await member.timeout(until, reason=tool_input.get("reason") or "بأمر من الإدارة عبر الوزير")
                return f"تم كتم العضو {member.display_name} لمدة {minutes} دقيقة."

            elif tool_name == "remove_timeout":
                member = self._find_member(guild, tool_input["member_name"])
                if not member:
                    return f"لم أجد عضو باسم {tool_input['member_name']}."
                await member.timeout(None)
                return f"تم إزالة الكتم عن العضو {member.display_name}."

            elif tool_name == "purge_messages":
                ch = None
                if tool_input.get("channel_name"):
                    ch = self._find_channel(guild, tool_input["channel_name"])
                elif isinstance(invoking_channel, discord.TextChannel):
                    ch = invoking_channel
                if not ch or not isinstance(ch, discord.TextChannel):
                    return "لم أجد قناة نصية صالحة لحذف الرسائل منها."
                amount = max(1, min(int(tool_input.get("amount", 10)), 100))
                deleted = await ch.purge(limit=amount)
                return f"تم حذف {len(deleted)} رسالة من قناة {ch.name}."

            elif tool_name == "set_nickname":
                member = self._find_member(guild, tool_input["member_name"])
                if not member:
                    return f"لم أجد عضو باسم {tool_input['member_name']}."
                await member.edit(nick=tool_input["new_nickname"])
                return f"تم تغيير اسم العضو المستعار إلى {tool_input['new_nickname']}."

            return f"أداة غير معروفة: {tool_name}"

        except discord.Forbidden:
            return "لا أملك الصلاحيات الكافية لتنفيذ هذا الإجراء - تأكد أن رتبتي بالسيرفر مرتفعة بما يكفي."
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                return "⚠️ ديسكورد نفسه ضاغط علينا حاليًا (429)، جرب تعيد الأمر بعد شوي."
            return f"حدث خطأ من ديسكورد أثناء التنفيذ: {str(e)}"
        except ValueError:
            return "قيمة غير صحيحة (تأكد من صيغة اللون مثلاً #FF00AA)."
        except Exception as e:
            return f"حدث خطأ أثناء التنفيذ: {str(e)}"

    @staticmethod
    async def _send_long(message: discord.Message, text: str):
        if len(text) <= 1900:
            await message.reply(text)
            return
        chunks = [text[i:i + 1900] for i in range(0, len(text), 1900)]
        await message.reply(chunks[0])
        for chunk in chunks[1:]:
            await message.channel.send(chunk)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        content = message.content.strip()
        triggered = False
        query = content
        for trigger in config.TRIGGER_WORDS:
            if content.startswith(trigger):
                triggered = True
                query = content[len(trigger):].strip(" ,،:") or "مرحبًا"
                break

        if not triggered:
            return

        if not self._is_authorized(message.author.id):
            await message.reply("عذرًا، هذي الأداة مخصصة لشخص محدد فقط. 🛡️")
            return

        now = time.monotonic()
        last = self.last_command_time.get(message.author.id, 0.0)
        elapsed = now - last
        if elapsed < self.cooldown_seconds:
            remaining = round(self.cooldown_seconds - elapsed, 1)
            await message.reply(f"⏳ تمهل شوي! ينفع ترسل أمر جديد بعد {remaining} ثانية.")
            return
        self.last_command_time[message.author.id] = now

        try:
            async with message.channel.typing():
                reply = await self._process(query, message.guild, message.author.id, message.channel)
        except RateLimitExceededError:
            await message.reply("⚠️ الضغط عالٍ حالياً على مفاتيح جينوم، يرجى الانتظار دقيقة وإعادة الطلب.")
            return
        except Exception as e:
            await message.reply(f"⚠️ صار خطأ غير متوقع أثناء التنفيذ: {e}")
            return

        await self._send_long(message, reply)

    async def _process(self, query: str, guild: discord.Guild, user_id: int, channel: discord.abc.Messageable = None) -> str:
        history = self.history.setdefault(user_id, [])
        history[:] = history[-self.max_history_items:]

        # صياغة الذاكرة بطريقة قوقل الرسمية (role / parts)
        formatted_messages = []
        for h in history:
            formatted_messages.append({"role": h["role"], "parts": [h["content"]]})
        formatted_messages.append({"role": "user", "parts": [query]})

        for _ in range(6):
            try:
                response = await self.ai.generate(contents=formatted_messages)
            except RateLimitExceededError:
                raise
            except RuntimeError as e:
                return f"{e}"

            if response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                
                # إذا رجع نص عادي ينتهي التنفيذ
                if hasattr(part, 'text') and part.text:
                    final_text = part.text
                    history.append({"role": "user", "content": query})
                    history.append({"role": "model", "content": final_text})
                    self.history[user_id] = history[-self.max_history_items:]
                    return final_text
                
                # إذا طلب تشغيل دالة (Function Call)
                elif hasattr(part, 'function_call') and part.function_call:
                    call = part.function_call
                    tool_name = call.name
                    tool_input = dict(call.args) if call.args else {}
                    
                    # تنفيذ الأمر إدارياً
                    result = await self.execute_tool(tool_name, tool_input, guild, channel)
                    
                    # تغذية الرد للنموذج لمتابعة السير
                    formatted_messages.append({"role": "model", "parts": [part]})
                    formatted_messages.append({
                        "role": "tool",
                        "parts": [{
                            "function_response": {
                                "name": tool_name,
                                "response": {"result": result}
                            }
                        }]
                    })
                    continue

            return "تم الإجراء بنجاح."

        self.history[user_id] = history[-self.max_history_items:]
        return "نفذت عدة إجراءات، لكن الطلب كان معقدًا جدًا - جرب تقسمه لطلبات أبسط."


async def setup(bot: commands.Bot):
    await bot.add_cog(Architect(bot))
