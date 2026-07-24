import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

CEREBRAS_API_KEYS = [
    key for key in [
        os.environ.get("CEREBRAS_API_KEY_1", ""),
        os.environ.get("CEREBRAS_API_KEY_2", ""),
        os.environ.get("CEREBRAS_API_KEY_3", ""),
        os.environ.get("CEREBRAS_API_KEY_4", ""),
        os.environ.get("CEREBRAS_API_KEY_5", ""),
    ] if key
]

CEREBRAS_BASE_URL = "https://api.cerebras.ai/v1"

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

TRIGGER_WORDS = ["الوزير", "يالوزير", "يا وزير", "وزير"]
COMMAND_PREFIX = "!"
AI_MODEL = "llama-3.3-70b"
