# -*- coding: utf-8 -*-
"""
تحكيم إجابات لعبة الريبلكا.

التكامل مع "الوزير": نستخدم بالضبط نفس محرك الذكاء الاصطناعي وتدوير المفاتيح
(KeyRotator) الموجود بكوغ Architect بدل إنشاء اتصال منفصل - بهذا يكون الوزير
نفسه هو من يحكم صحة إجابات اللاعبين. لو تعذر الوصول لأي سبب (الكوغ غير محمّل،
ضغط على كل المفاتيح...) نتحول تلقائيًا لتحكيم احتياطي بسيط حتى ما تتوقف اللعبة.
"""
import json
import logging

import config
from riplaca_engine import normalize_arabic

log = logging.getLogger("riplaca_ai")

JUDGE_SYSTEM_PROMPT = """أنتَ "الوزير"، وتقوم الآن بدور حكم لعبة "الريبلكا" (لعبة الحروف والفئات) بنفس شخصيتك الذكية.
لكل إجابة أرسلها لاعب: تحقق أنها كلمة حقيقية تنتمي فعلاً للفئة المطلوبة، وتبدأ بالحرف المطلوب تحديدًا.
تجاهل فروقات الهمزات (أ إ آ) والتاء المربوطة/الهاء كاختلاف تافه، لكن ارفض أي إجابة فارغة، مكررة الحروف بلا معنى،
لا تبدأ بالحرف الصحيح، أو لا تنتمي للفئة المطلوبة فعلاً.
أجب حصرًا بصيغة JSON صحيحة بدون أي نص إضافي أو علامات ماركداون وبدون شرح، بالشكل التالي بالضبط:
{"verdicts": [{"id": "<المعرف>", "correct": true}, {"id": "<المعرف>", "correct": false}]}
"""


def _fallback_heuristic(game):
    """تحكيم احتياطي: الإجابة صحيحة لو غير فارغة، طولها حرفان فأكثر، وتبدأ بالحرف المطلوب."""
    r = game.current_round
    letter_norm = normalize_arabic(r.letter)
    verdicts = {}
    for pid in game.players:
        verdicts[pid] = {}
        for cat in r.categories:
            ans = r.answers.get(pid, {}).get(cat, "")
            ok = bool(ans) and len(ans.strip()) >= 2 and normalize_arabic(ans).startswith(letter_norm)
            verdicts[pid][cat] = ok
    return verdicts


def _parse_json_response(raw: str):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


async def judge_round(bot, game, names: dict):
    """
    يحكّم الجولة الحالية عبر ذكاء الوزير، ويرجّع {player_id: {category: bool}}.
    يستخدم KeyRotator الموجود أصلاً بكوغ Architect (نفس مفاتيح ونفس عقل الوزير).
    """
    architect_cog = bot.get_cog("Architect")
    r = game.current_round

    if architect_cog is None or not getattr(architect_cog, "ai", None):
        log.warning("⚠️ كوغ الوزير (Architect) غير محمّل، سيُستخدم التحكيم الاحتياطي للريبلكا.")
        return _fallback_heuristic(game)

    items = []
    id_map = {}
    for pid in game.players:
        for idx, cat in enumerate(r.categories):
            ans = r.answers.get(pid, {}).get(cat, "")
            key = f"{pid}__{idx}"
            id_map[key] = (pid, cat)
            items.append({
                "id": key,
                "اللاعب": names.get(pid, str(pid)),
                "الفئة": cat,
                "الحرف_المطلوب": r.letter,
                "الإجابة": ans or "(فارغة)",
            })

    user_content = "قيّم الإجابات التالية للعبة الريبلكا:\n" + json.dumps(items, ensure_ascii=False)

    try:
        response = await architect_cog.ai.create(
            model=config.AI_MODEL,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        raw = response.choices[0].message.content or ""
        data = _parse_json_response(raw)

        fallback = _fallback_heuristic(game)
        verdicts = {pid: dict(fallback[pid]) for pid in game.players}  # نبدأ بالاحتياطي كأساس آمن

        for entry in data.get("verdicts", []):
            key = entry.get("id")
            if key not in id_map:
                continue
            pid, cat = id_map[key]
            verdicts[pid][cat] = bool(entry.get("correct"))

        return verdicts
    except Exception as e:
        log.error(f"❌ تعذر تحكيم جولة الريبلكا عبر ذكاء الوزير، استخدام التحكيم الاحتياطي: {e}")
        return _fallback_heuristic(game)
