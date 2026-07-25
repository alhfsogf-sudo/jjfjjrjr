import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# جلب المفاتيح الخمسة تلقائياً من بيئة عمل ريلواي
GEMINI_API_KEYS = [
    key for key in [
        os.environ.get("GEMINI_API_KEY_1", ""),
        os.environ.get("GEMINI_API_KEY_2", ""),
        os.environ.get("GEMINI_API_KEY_3", ""),
        os.environ.get("GEMINI_API_KEY_4", ""),
        os.environ.get("GEMINI_API_KEY_5", ""),
    ] if key
]

# تم حذف الـ BASE_URL القديم تماماً ليتصل البوت عبر مكتبة جوجل الرسمية مباشرة وبدون وسيط

try:
    OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
except ValueError:
    OWNER_ID = 0

_extra_ids = os.environ.get("AUTHORIZED_USER_IDS", "")
AUTHORIZED_USER_IDS = set()
for part in _extra_ids.split(","):
    part = part.strip()
    if part.isdigit():
        AUTHORIZED_USER_IDS.add(int(part))
if OWNER_ID:
    AUTHORIZED_USER_IDS.add(OWNER_ID)

# المناديات الخاصة بك 
TRIGGER_WORDS = ["جلب زهير", "عمو", "ياوزير", "وزير"]
COMMAND_PREFIX = "!"

# تعديل اسم الموديل للاسم الرسمي المدعوم والمستقر من قوقل
AI_MODEL = "gemini-1.5-flash"

# المهلة الزمنية لحماية البوت من التجميد والسبام
try:
    COOLDOWN_SECONDS = float(os.environ.get("COOLDOWN_SECONDS", "6"))
except ValueError:
    COOLDOWN_SECONDS = 6.0
