import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# جلب المفاتيح تلقائياً من بيئة عمل Railway (حتى 5 مفاتيح، الفاضي يتجاهل تلقائيًا)
GEMINI_API_KEYS = [
    key for key in [
        os.environ.get("GEMINI_API_KEY_1", ""),
        os.environ.get("GEMINI_API_KEY_2", ""),
        os.environ.get("GEMINI_API_KEY_3", ""),
        os.environ.get("GEMINI_API_KEY_4", ""),
        os.environ.get("GEMINI_API_KEY_5", ""),
    ] if key
]

# endpoint التوافق مع OpenAI الرسمي من قوقل - أكثر استقرارًا من مكتبة google.generativeai المتوقفة
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

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

# اسم موديل Gemini الرسمي المدعوم عبر endpoint التوافق مع OpenAI
AI_MODEL = "gemini-1.5-flash"

# المهلة الزمنية لحماية البوت من التجميد والسبام
try:
    COOLDOWN_SECONDS = float(os.environ.get("COOLDOWN_SECONDS", "6"))
except ValueError:
    COOLDOWN_SECONDS = 6.0
