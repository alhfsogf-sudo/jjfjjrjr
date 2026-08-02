# -*- coding: utf-8 -*-
"""
توليد صور بطاقات نتائج لعبة الريبلكا (نتيجة كل جولة + النتيجة النهائية) عبر Pillow.

يحتاج الرسم العربي الصحيح بالصورة تشكيل الحروف (arabic_reshaper) وترتيبها من
اليمين لليسار (python-bidi)، وخطًا يدعم العربية. بما إن السيرفر (Railway) ما
نضمن وجود خط عربي جاهز عليه، نحمّل خط Amiri (مفتوح المصدر) تلقائيًا أول مرة
ونخزنه محليًا بمجلد data/fonts. لو تعذر التحميل (لا يوجد إنترنت خارجي مثلاً)،
الدوال ترجّع None بهدوء، والكوغ يتحول تلقائيًا لإرسال embed نصي بدل الصورة.
"""
import io
import logging
import os
import urllib.request

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("riplaca_cards")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _SHAPING_AVAILABLE = True
except ImportError:
    _SHAPING_AVAILABLE = False
    log.warning("⚠️ مكتبتا arabic_reshaper و python-bidi غير مثبتتين، النص العربي بالصور قد يظهر مقلوبًا.")

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fonts")
FONT_REGULAR_PATH = os.path.join(FONTS_DIR, "Amiri-Regular.ttf")
FONT_BOLD_PATH = os.path.join(FONTS_DIR, "Amiri-Bold.ttf")

FONT_URLS = {
    FONT_REGULAR_PATH: "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf",
    FONT_BOLD_PATH: "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Bold.ttf",
}

COLOR_BG = (24, 26, 38)
COLOR_CARD = (34, 37, 54)
COLOR_ROW = (46, 50, 70)
COLOR_ROW_TOP = (63, 53, 30)
COLOR_GOLD = (240, 190, 90)
COLOR_GREEN = (110, 210, 130)
COLOR_RED = (230, 100, 100)
COLOR_WHITE = (240, 240, 245)
COLOR_MUTED = (150, 155, 170)
COLOR_LINE = (60, 63, 82)

MEDALS = ["🥇", "🥈", "🥉"]


def _ensure_font(path):
    if os.path.exists(path):
        return True
    try:
        os.makedirs(FONTS_DIR, exist_ok=True)
        urllib.request.urlretrieve(FONT_URLS[path], path)
        log.info(f"✅ تم تحميل الخط العربي: {os.path.basename(path)}")
        return True
    except Exception as e:
        log.warning(f"⚠️ تعذر تحميل الخط العربي ({os.path.basename(path)}): {e}")
        return False


def _font(size, bold=False):
    path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    if not _ensure_font(path):
        return None
    try:
        return ImageFont.truetype(path, size)
    except Exception as e:
        log.warning(f"⚠️ تعذر فتح الخط العربي: {e}")
        return None


def _shape(text):
    text = "" if text is None else str(text)
    if not _SHAPING_AVAILABLE:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _text(draw, xy, text, font, fill, anchor="ra"):
    draw.text(xy, _shape(text), font=font, fill=fill, anchor=anchor)


def fonts_available() -> bool:
    """يتحقق مبكرًا إذا الخطوط جاهزة (يحاول تحميلها لو ناقصة) قبل محاولة الرسم."""
    return _ensure_font(FONT_REGULAR_PATH) and _ensure_font(FONT_BOLD_PATH)


def render_round_card(letter, categories, players_order, names, points_breakdown, answers, round_number, total_rounds):
    """بطاقة نتائج جولة واحدة: الحرف بالأعلى، وجدول (فئة × لاعب) بإجابته ونقاطه."""
    title_font = _font(30, bold=True)
    letter_font = _font(50, bold=True)
    header_font = _font(24, bold=True)
    cell_font = _font(22)
    small_font = _font(18)
    if not all([title_font, letter_font, header_font, cell_font, small_font]):
        return None

    n_players = len(players_order)
    row_h = 64
    col_w = 220
    width = 60 + col_w * n_players
    height = 220 + row_h * len(categories) + 30

    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((20, 20, width - 20, 140), radius=18, fill=COLOR_CARD)
    _text(draw, (width - 40, 40), f"لعبة الريبلكا  •  الجولة {round_number} من {total_rounds}", header_font, COLOR_WHITE, anchor="ra")
    _text(draw, (width - 40, 75), f"الحرف: {letter}", letter_font, COLOR_GOLD, anchor="ra")

    top = 160
    for i, pid in enumerate(players_order):
        x = width - 40 - col_w * i - col_w // 2
        _text(draw, (x, top), (names.get(pid, str(pid)))[:14], header_font, COLOR_WHITE, anchor="ma")

    y = top + 46
    for cat in categories:
        draw.line((20, y - 8, width - 20, y - 8), fill=COLOR_LINE, width=1)
        _text(draw, (width - 30, y), cat, cell_font, COLOR_MUTED, anchor="ra")
        for i, pid in enumerate(players_order):
            x = width - 40 - col_w * i - col_w // 2
            ans = (answers.get(pid, {}) or {}).get(cat) or "—"
            pts = (points_breakdown.get(pid, {}) or {}).get(cat, 0)
            ans_color = COLOR_GREEN if pts > 0 else (COLOR_RED if ans != "—" else COLOR_MUTED)
            _text(draw, (x, y), ans[:16], cell_font, ans_color, anchor="ma")
            _text(draw, (x, y + 26), (f"+{pts}" if pts else "0"), small_font, COLOR_GOLD if pts else COLOR_MUTED, anchor="ma")
        y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_standings_card(standings, names, title, subtitle=None):
    """بطاقة ترتيب عامة (تُستخدم للنتيجة النهائية ولأمر توب الريبلكا)."""
    title_font = _font(38, bold=True)
    sub_font = _font(22)
    name_font = _font(28, bold=True)
    score_font = _font(26)
    if not all([title_font, sub_font, name_font, score_font]):
        return None

    n = len(standings)
    row_h = 62
    width = 620
    height = 150 + row_h * max(n, 1) + 30

    img = Image.new("RGB", (width, height), COLOR_BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((20, 20, width - 20, 120), radius=18, fill=COLOR_CARD)
    _text(draw, (width - 40, 38), title, title_font, COLOR_GOLD, anchor="ra")
    if subtitle:
        _text(draw, (width - 40, 85), subtitle, sub_font, COLOR_MUTED, anchor="ra")

    y = 140
    for idx, (pid, score) in enumerate(standings):
        fill = COLOR_ROW_TOP if idx == 0 else COLOR_ROW
        draw.rounded_rectangle((30, y, width - 30, y + row_h - 10), radius=12, fill=fill)
        rank_label = MEDALS[idx] if idx < 3 else f"#{idx + 1}"
        _text(draw, (width - 50, y + 13), f"{rank_label}  {names.get(pid, str(pid))}", name_font, COLOR_WHITE, anchor="ra")
        _text(draw, (60, y + 13), f"{score} نقطة", score_font, COLOR_GOLD, anchor="la")
        y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
