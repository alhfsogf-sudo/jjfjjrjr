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

# ======================================================================
# 🔐 نظام التصريح بالرتبة (بدل التصريح بأشخاص محددين)
# ======================================================================
# الأفضل والأدق: ضع آيدي الرتبة هنا (ثابت حتى لو تغيّر اسم الرتبة لاحقًا)
_authorized_role_id_raw = os.environ.get("AUTHORIZED_ROLE_ID", "")
try:
    AUTHORIZED_ROLE_ID = int(_authorized_role_id_raw) if _authorized_role_id_raw.strip() else None
except ValueError:
    AUTHORIZED_ROLE_ID = None

# احتياطي بالاسم في حال ما وضعت آيدي (يُستخدم فقط لو AUTHORIZED_ROLE_ID فاضي)
AUTHORIZED_ROLE_NAME = os.environ.get("AUTHORIZED_ROLE_NAME", "الوزير")

# المناديات الخاصة بك
TRIGGER_WORDS = ["جلب زهير", "عمو", "ياوزير", "وزير"]
COMMAND_PREFIX = "!"

# اسم موديل Gemini الرسمي المدعوم عبر endpoint التوافق مع OpenAI
AI_MODEL = "gemini-3.5-flash"

# المهلة الزمنية لحماية البوت من التجميد والسبام (بالثواني)
try:
    COOLDOWN_FAST_SECONDS = float(os.environ.get("COOLDOWN_FAST_SECONDS", "2"))
except ValueError:
    COOLDOWN_FAST_SECONDS = 2.0

try:
    COOLDOWN_SLOW_SECONDS = float(os.environ.get("COOLDOWN_SLOW_SECONDS", "6"))
except ValueError:
    COOLDOWN_SLOW_SECONDS = 6.0

# ======================================================================
# 🏆 إعدادات نظام الليدبورد الصافي (توب التفاعل للرتبة)
# ======================================================================
# اسم الرتبة المراقبة التي سيتم حساب التوب لأعضائها (تستطيع تغيير "الوزير" لأي اسم رتبة تفضلها)
LEADERBOARD_ROLE_NAME = os.environ.get("LEADERBOARD_ROLE_NAME", "الوزير")

# مسار ملف حفظ بيانات النقاط والتفاعل تلقائياً داخل مجلد data
LEADERBOARD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "leaderboard.json")


def is_authorized_member(member) -> bool:
    """
    يتحقق فيما إذا كان العضو (discord.Member) يملك الرتبة المصرح لها.
    يفضّل التحقق بالآيدي (AUTHORIZED_ROLE_ID) لأنه ثابت حتى لو تغيّر اسم الرتبة.
    """
    if member is None or not hasattr(member, "roles"):
        return False

    if AUTHORIZED_ROLE_ID:
        return any(r.id == AUTHORIZED_ROLE_ID for r in member.roles)

    if AUTHORIZED_ROLE_NAME:
        return any(r.name == AUTHORIZED_ROLE_NAME for r in member.roles)

    return False
