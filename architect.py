import json
import logging
import random
import time
from datetime import timedelta

import discord
from discord.ext import commands
from openai import OpenAI, RateLimitError
import asyncio

import config

log = logging.getLogger("architect")

SYSTEM_PROMPT = """أنتَ "الوزير"، مستشار إداري وعسكري ذكي ومساعد كامل الصلاحيات في لعبة "سيادة الأمم" الاستراتيجية داخل ديسكورد.
مهمتك توجيه اللاعبين، شرح الاستراتيجيات، ومساعدتهم بناءً على قوانين اللعبة التالية:

1. الثقافات المتاحة: قائد عسكري (حرب وغارات)، بارون التجارة (اقتصاد وذهب)، كبير البنائين (ترقية وبناء وتطوير).
2. الموارد: الذهب (🪙)، الخشب (🪵)، الحديد (⛓️)، الطعام (🌾)، جوهر السحر (🔮).
3. مخاطر الموارد:
   - نفاد الطعام = انخفاض كفاءة الجيش 50% وموت 5% من الجنود كل ساعة.
   - نفاد الذهب = انخفاض إنتاج المنشرة والمنجم والمذبح 30%.
   - نفاد السحر = مغادرة السحرة والمخلوقات نهائياً.
4. مثلث قوة الجيش العسكري:
   - المشاة (infantry) يتفوق على الرماة (archers).
   - الفرسان (cavalry) يتفوق على المشاة (infantry).
   - الرماة (archers) يتفوقون على الفرسان (cavalry).
   - التفوق يمنح +25% قوة إضافية في المعركة.
5. الغارات: يجب أن تكون قوة الهدف بين 80% و 120% من قوة المهاجم لحماية الضعفاء، والحد الأقصى هو 3 غارات على نفس الشخص كل 24 ساعة. درع المبتدئين يدوم 48 ساعة.
6. السحر: يتطلب مذبح مستوى 5 للاستدعاء. السحرة المتاحين (Pyromancer, Arch-healer, Illusionist)، والمخلوقات (Dragon, Phoenix, Golem). البعثات السحرية (Expedition) نسبة نجاحها 5% وترتفع إلى 20% في الكسوف.

تحدث دائماً بلهجة مستشار ملكي، فصيح، ومخلص. شجّع اللاعبين على استخدام أوامر المائل واعلم أن لديك كامل الصلاحيات الإدارية والهندسية لتنفيذ ما يطلبه الموثوقون عبر الـ Slash Commands مثل /start, /upgrade, /train, /raid لإدارة إمبراطورياتهم."""

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
    {
        "name": "kick_member",
        "description": "طرد عضو من السيرفر",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["member_name"]
        }
    },
    {
        "name": "ban_member",
        "description": "حظر (باند) عضو من السيرفر",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {"type": "string"},
                "reason": {"type": "string"},
                "delete_message_days": {"type": "integer"}
            },
            "required": ["member_name"]
        }
    },
    {
        "name": "unban_member",
        "description": "فك الحظر عن مستخدم محظور، بالآيدي أو باسمه",
        "input_schema": {
            "type": "object",
            "properties": {"user_identifier": {"type": "string"}},
            "required": ["user_identifier"]
        }
    },
    {
        "name": "timeout_member",
        "description": "كتم عضو (تايم آوت) لمدة محددة بالدقائق",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {"type": "string"},
                "minutes": {"type": "integer"},
                "reason": {"type": "string"}
            },
            "required": ["member_name", "minutes"]
        }
    },
    {
        "name": "remove_timeout",
        "description": "إزالة الكتم (التايم آوت) عن عضو",
        "input_schema": {
            "type": "object",
            "properties": {"member_name": {"type": "string"}},
            "required": ["member_name"]
        }
    },
    {
        "name": "purge_messages",
        "description": "حذف عدد معين من آخر الرسائل بقناة معينة (أو بالقناة الحالية لو ما تحدد قناة)",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel_name": {"type": "string"},
                "amount": {"type": "integer"}
            },
            "required": ["amount"]
        }
    },
    {
        "name": "set_nickname",
        "description": "تغيير الاسم المستعار (nickname) لعضو",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_name": {"type": "string"},
                "new_nickname": {"type": "string"}
            },
            "required": ["member_name", "new_nickname"]
        }
    },
]

def build_openai_tools():
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS
    ]

FAST_ACTION_KEYWORDS = [
    "اطرد", "طرد", "احظر", "حظر", "باند", "بان",
    "فك الحظر", "الغاء الحظر", "إلغاء الحظر", "فك حظر",
    "كتم", "تايم اوت", "تايم آوت", "الغاء الكتم", "إلغاء الكتم", "ازالة الكتم", "إزالة الكتم", "شيل الكتم",
    "حذف رسائل", "امسح رسائل", "نظف الرسائل", "بورج", "purge",
    "غير اسمه", "غيّر اسمه", "غير الاسم المستعار", "غيّر الاسم المستعار", "نك نيم",
    "اعطي رتبة", "اعطه رتبة", "اعطيه رتبة", "سحب رتبة", "شيل رتبة", "احذف رتبة منه",
    "اعرض", "الهيكلة", "اظهر", "وضح", "اعرضلي",
]

SLOW_ACTION_KEYWORDS = [
    "انشئ", "أنشئ", "انشاء", "إنشاء", "اعمل", "سوي", "سو",
    "قناة جديدة", "رتبة جديدة", "فئة جديدة", "روم جديد",
    "احذف قناة", "احذف فئة", "احذف رتبة", "امسح قناة",
    "اعد تسمية", "أعد تسمية", "غير اسم القناة", "غيّر اسم القناة", "غير اسم الرتبة", "غيّر اسم الرتبة",
    "غير لون", "غيّر لون", "لون الرتبة", "صلاحيات", "نقل قناة", "نقل الفئة",
    "سلومود", "سلو مود", "وصف القناة", "التوبيك", "الوصف",
]

def classify_cooldown(query: str, fast_seconds: float, slow_seconds: float) -> float:
    q = query.lower()
    for kw in SLOW_ACTION_KEYWORDS:
        if kw in q:
            return slow_seconds
    for kw in FAST_ACTION_KEYWORDS:
        if kw in q:
            return fast_seconds
    return slow_seconds

class RateLimitExceededError(RuntimeError):
    pass

class KeyRotator:
    def __init__(self, api_keys: list):
        if not api_keys:
            raise RuntimeError("لا يوجد أي مفتاح API معرّف بمتغيرات البيئة.")
        self.clients = [OpenAI(api_key=k, base_url=config.GEMINI_BASE_URL) for k in api_keys]

    async def create(self, **kwargs):
        last_error = None
        saw_rate_limit = False

        for index, client in enumerate(self.clients):
            try:
                return await asyncio.to_thread(client.chat.completions.create, **kwargs)
            except RateLimitError as e:
                saw_rate_limit = True
                last_error = e
                log.warning(f"🛑 المفتاح {index + 1} رجع 429 (ضغط/حصة): {e}")
                if index < len(self.clients) - 1:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                continue
            except Exception as e:
                # التقاط خطأ 503 أو 500 أو 504 ومعاملته كضغط مؤقت للانتقال للمفتاح التالي
                error_str = str(e)
                if "503" in error_str or "500" in error_str or "504" in error_str:
                    saw_rate_limit = True
                    last_error = e
                    log.warning(f"⚠️ المفتاح {index + 1} واجه ضغط خوادم مؤقت (503/500): {e}")
                    if index < len(self.clients) - 1:
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                    continue
                
                log.error(f"🚨 خطأ غير متعلق بالحصة أو الضغط على المفتاح {index + 1}: {e}")
                raise

        if saw_rate_limit:
            raise RateLimitExceededError(f"كل المفاتيح صار عليها ضغط 429 أو 503 مؤقت. آخر خطأ: {last_error}")
        raise RuntimeError(f"جميع مفاتيح API فشلت. آخر خطأ: {last_error}")

class Architect(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ai = KeyRotator(config.GEMINI_API_KEYS)
        self.tools = build_openai_tools()
        self.history = {}
        self.last_command_time = {}
        self.cooldown_fast_seconds = getattr(config, "COOLDOWN_FAST_SECONDS", 2.0)
        self.cooldown_slow_seconds = getattr(
            config, "COOLDOWN_SLOW_SECONDS", getattr(config, "COOLDOWN_SECONDS", 6.0)
        )
        self.max_history_items = 4

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

        if not triggered and self.bot.user in message.mentions:
            triggered = True
            cleaned = content
            for mention_format in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
                cleaned = cleaned.replace(mention_format, "")
            query = cleaned.strip(" ,،:") or "مرحبًا"

        if not triggered and message.reference:
            ref_msg = message.reference.resolved
            if ref_msg is None:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                except (discord.NotFound, discord.HTTPException):
                    ref_msg = None
            if isinstance(ref_msg, discord.Message) and ref_msg.author and ref_msg.author.id == self.bot.user.id:
                triggered = True
                query = content.strip() or "مرحبًا"

        if not triggered:
            return

        if not self._is_authorized(message.author.id):
            await message.reply("ولي انا بس لعمو زُهير وجاي وحليب الشيوعي هيهيهيهيهي")
            return

        cooldown = classify_cooldown(query, self.cooldown_fast_seconds, self.cooldown_slow_seconds)
        now = time.monotonic()
        last = self.last_command_time.get(message.author.id, 0.0)
        elapsed = now - last
        if elapsed < cooldown:
            remaining = round(cooldown - elapsed, 1)
            await message.reply(f"⏳ تمهل شوي! ينفع ترسل أمر جديد بعد {remaining} ثانية.")
            return
        self.last_command_time[message.author.id] = now

        try:
            async with message.channel.typing():
                reply = await self._process(query, message.guild, message.author.id, message.channel)
        except RateLimitExceededError:
            await message.reply("⚠️ الضغط عالٍ حالياً على الذكاء الاصطناعي (429/503 على كل المفاتيح)، يرجى الانتظار بضع ثوانٍ وإعادة المحاولة!")
            return
        except Exception as e:
            log.error(f"خطأ غير متوقع أثناء المعالجة: {e}")
            await message.reply(f"⚠️ صار خطأ غير متوقع أثناء التنفيذ (راجع لوق Railway للتفاصيل): {e}")
            return

        await self._send_long(message, reply)

    async def _process(self, query: str, guild: discord.Guild, user_id: int, channel: discord.abc.Messageable = None) -> str:
        history = self.history.setdefault(user_id, [])
        history[:] = history[-self.max_history_items:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": query}]

        for _ in range(6):
            try:
                response = await self.ai.create(
                    model=config.AI_MODEL,
                    max_tokens=1024,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                )
            except RateLimitExceededError:
                raise
            except Exception as e:
                return f"⚠️ تعذر الوصول للذكاء الاصطناعي حاليًا: {e}"

            msg = response.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                final_text = msg.content or "تم."
                history.append({"role": "user", "content": query})
                history.append({"role": "assistant", "content": final_text})
                self.history[user_id] = history[-self.max_history_items:]
                return final_text

            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments) if call.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                result = await self.execute_tool(call.function.name, args, guild, channel)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        fallback_text = "نفذت عدة إجراءات، لكن الطلب كان معقدًا جدًا - جرب تقسمه لطلبات أبسط."
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": fallback_text})
        self.history[user_id] = history[-self.max_history_items:]
        return fallback_text

async def setup(bot: commands.Bot):
    await bot.add_cog(Architect(bot))
 
