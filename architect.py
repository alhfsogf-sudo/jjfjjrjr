import discord
from discord.ext import commands
import anthropic
import asyncio

import config


SYSTEM_PROMPT = """أنتَ "الوزير"، أداة تنفيذية مباشرة لبناء وتعديل هيكلة سيرفر ديسكورد.
يستخدمك شخص محترف مسؤول عن بناء السيرفر بالكامل، وأنت تنفذ أوامره فورًا بدون تردد أو طلب تأكيد.
تحدث بالعربية دائمًا. بعد تنفيذ أي طلب، اذكر بإيجاز ووضوح وش سويت بالضبط.
إذا كان الطلب غامضًا لدرجة يستحيل تنفيذه (مثل اسم رتبة غير موجود بالمرة)، وضح المشكلة بدل التخمين العشوائي.
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

TOOLS = [
    {
        "name": "create_text_channel",
        "description": "إنشاء قناة نصية جديدة",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "category": {"type": "string"},
                "topic": {"type": "string"},
                "nsfw": {"type": "boolean"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_voice_channel",
        "description": "إنشاء روم صوتي جديد",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "category": {"type": "string"},
                "user_limit": {"type": "integer"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_category",
        "description": "إنشاء فئة جديدة تجمع قنوات",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    },
    {
        "name": "delete_channel",
        "description": "حذف قناة نصية أو صوتية أو فئة بالاسم",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    },
    {
        "name": "rename_channel",
        "description": "إعادة تسمية قناة موجودة",
        "input_schema": {
            "type": "object",
            "properties": {"old_name": {"type": "string"}, "new_name": {"type": "string"}},
            "required": ["old_name", "new_name"]
        }
    },
    {
        "name": "move_channel_to_category",
        "description": "نقل قناة موجودة لفئة أخرى",
        "input_schema": {
            "type": "object",
            "properties": {"channel_name": {"type": "string"}, "category_name": {"type": "string"}},
            "required": ["channel_name", "category_name"]
        }
    },
    {
        "name": "create_role",
        "description": "إنشاء رتبة جديدة بالسيرفر",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "color_hex": {"type": "string"},
                "hoist": {"type": "boolean"},
                "mentionable": {"type": "boolean"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "delete_role",
        "description": "حذف رتبة بالاسم",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    },
    {
        "name": "rename_role",
        "description": "إعادة تسمية رتبة موجودة",
        "input_schema": {
            "type": "object",
            "properties": {"old_name": {"type": "string"}, "new_name": {"type": "string"}},
            "required": ["old_name", "new_name"]
        }
    },
    {
        "name": "set_role_color",
        "description": "تغيير لون رتبة موجودة",
        "input_schema": {
            "type": "object",
            "properties": {"role_name": {"type": "string"}, "color_hex": {"type": "string"}},
            "required": ["role_name", "color_hex"]
        }
    },
    {
        "name": "assign_role",
        "description": "إعطاء رتبة لعضو معين",
        "input_schema": {
            "type": "object",
            "properties": {"member_name": {"type": "string"}, "role_name": {"type": "string"}},
            "required": ["member_name", "role_name"]
        }
    },
    {
        "name": "remove_role",
        "description": "سحب رتبة من عضو",
        "input_schema": {
            "type": "object",
            "properties": {"member_name": {"type": "string"}, "role_name": {"type": "string"}},
            "required": ["member_name", "role_name"]
        }
    },
    {
        "name": "set_role_permissions",
        "description": "تعديل صلاحيات رتبة على مستوى السيرفر بالكامل (منح أو سحب صلاحيات محددة)",
        "input_schema": {
            "type": "object",
            "properties": {
                "role_name": {"type": "string"},
                "grant": {"type": "array", "items": {"type": "string"}, "description": "قائمة الصلاحيات الممنوحة"},
                "revoke": {"type": "array", "items": {"type": "string"}, "description": "قائمة الصلاحيات المسحوبة"}
            },
            "required": ["role_name"]
        }
    },
    {
        "name": "set_channel_permission_overwrite",
        "description": "تخصيص صلاحيات رتبة معينة داخل قناة معينة فقط (مثل إخفاء قناة عن رتبة أو منعها من الكتابة)",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string"},
                "role_name": {"type": "string"},
                "allow": {"type": "array", "items": {"type": "string"}},
                "deny": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["channel_name", "role_name"]
        }
    },
    {
        "name": "set_channel_topic_or_slowmode",
        "description": "تعديل وصف القناة أو وضع البطء (سلومود)",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string"},
                "topic": {"type": "string"},
                "slowmode_seconds": {"type": "integer"}
            },
            "required": ["channel_name"]
        }
    },
    {
        "name": "list_current_structure",
        "description": "عرض قائمة كاملة بالفئات والقنوات والرتب الموجودة حاليًا بالسيرفر",
        "input_schema": {"type": "object", "properties": {}}
    },
]


class KeyRotator:
    def __init__(self, api_keys: list):
        if not api_keys:
            raise RuntimeError("لا يوجد أي مفتاح Anthropic API معرّف بمتغيرات البيئة.")
        self.current_index = 0
        self.clients = [anthropic.Anthropic(api_key=k) for k in api_keys]

    @property
    def current_client(self):
        return self.clients[self.current_index]

    def rotate(self):
        self.current_index = (self.current_index + 1) % len(self.clients)

    async def create(self, **kwargs):
        last_error = None
        for _ in range(len(self.clients)):
            try:
                return await asyncio.to_thread(self.current_client.messages.create, **kwargs)
            except (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError) as e:
                last_error = e
                self.rotate()
                continue
        raise RuntimeError(f"جميع مفاتيح API فشلت أو انتهت حصتها. آخر خطأ: {last_error}")


class Architect(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ai = KeyRotator(config.ANTHROPIC_API_KEYS)
        self.history = {}

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

    async def execute_tool(self, tool_name: str, tool_input: dict, guild: discord.Guild):
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

            return f"أداة غير معروفة: {tool_name}"

        except discord.Forbidden:
            return "لا أملك الصلاحيات الكافية لتنفيذ هذا الإجراء - تأكد أن رتبتي بالسيرفر مرتفعة بما يكفي."
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

        try:
            async with message.channel.typing():
                reply = await self._process(query, message.guild, message.author.id)
        except Exception as e:
            await message.reply(f"⚠️ صار خطأ غير متوقع أثناء التنفيذ: {e}")
            return
        await self._send_long(message, reply)

    async def _process(self, query: str, guild: discord.Guild, user_id: int) -> str:
        history = self.history.setdefault(user_id, [])
        messages = history + [{"role": "user", "content": query}]

        for _ in range(6):
            try:
                response = await self.ai.create(
                    model=config.AI_MODEL,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
            except RuntimeError as e:
                return f"⚠️ تعذر الوصول للذكاء الاصطناعي حاليًا: {e}"

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                text_parts = [b.text for b in response.content if b.type == "text"]
                final_text = "\n".join(text_parts) if text_parts else "تم."
                self.history[user_id] = messages[-20:]
                return final_text

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self.execute_tool(block.name, block.input, guild)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            messages.append({"role": "user", "content": tool_results})

        self.history[user_id] = messages[-20:]
        return "نفذت عدة إجراءات، لكن الطلب كان معقدًا جدًا - جرب تقسمه لطلبات أبسط."


async def setup(bot: commands.Bot):
    await bot.add_cog(Architect(bot))
