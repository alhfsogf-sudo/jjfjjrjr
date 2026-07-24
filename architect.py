import json
import discord
from discord.ext import commands
from openai import OpenAI
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


def build_openai_tools():
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
        for t in TOOLS
    ]


class KeyRotator:
    def __init__(self, api_keys: list):
        if not api_keys:
            raise RuntimeError("لا يوجد أي مفتاح Gemini API معرّف بمتغيرات البيئة.")
        self.current_index = 0
        self.clients = [OpenAI(api_key=
