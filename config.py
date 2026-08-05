"""
config.py — إدارة جميع متغيرات البيئة (Railway / .env)
كل ملف في المشروع يستورد إعداداته من هنا.
"""
import sys
from decouple import config


def _require(key: str) -> str:
    """يقرأ متغير بيئة إجباري، ويوقف البوت برسالة واضحة إذا لم يجده."""
    value = config(key, default=None)
    if not value:
        print(f"❌ متغير البيئة المطلوب غير موجود: {key}")
        sys.exit(1)
    return value


# --- أساسيات الاتصال ---
DISCORD_TOKEN = _require("DISCORD_TOKEN")
DATABASE_URL = _require("DATABASE_URL")
GUILD_ID = int(_require("GUILD_ID"))

# --- قنوات النظام ---
ADMIN_LOG_CHANNEL_ID = int(_require("ADMIN_LOG_CHANNEL_ID"))
NEWS_CHANNEL_ID = int(_require("NEWS_CHANNEL_ID"))
GUIDE_CHANNEL_ID = int(_require("GUIDE_CHANNEL_ID"))

# --- ثوابت اللعبة ---
ACCOUNT_AGE_DAYS = 30
NEWBIE_SHIELD_HOURS = 48

# --- إعدادات التحديث الدوري (تحسين UX) ---
STATUS_REFRESH_HOURS = 1          # كل كم ساعة تتحدث لوحات الحالة تلقائياً
MANUAL_REFRESH_COOLDOWN_SECONDS = 30  # تبريد بين ضغطات زر "تحديث الآن" اليدوي
