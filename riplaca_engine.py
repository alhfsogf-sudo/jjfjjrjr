# -*- coding: utf-8 -*-
"""
محرك لعبة الريبلكا (لعبة الحروف والفئات، على طراز "الاسم والحيوان والنبات والجماد").

كل جولة: يختار المحرك حرفًا عشوائيًا وعدة فئات (دولة، مهنة، حيوان...)،
ويرسل كل لاعب إجابة لكل فئة تبدأ بنفس الحرف. الإجابة الصحيحة والفريدة = 10 نقاط،
الصحيحة المكررة بين أكثر من لاعب = 5 نقاط لكل واحد، والخاطئة/الفارغة = صفر.

هذا الملف منطق خالص (بدون discord أو شبكة) حتى يسهل اختباره والتحقق منه.
"""
import random

# الحروف العربية المستخدمة (استبعدنا الهمزة المفردة والحروف النادرة جدًا كبداية كلمة)
LETTERS = list("ابتثجحخدرسشصطعغفقكلمنهوي")

CATEGORIES = [
    "دولة", "مدينة", "حيوان", "نبات", "جماد", "مهنة",
    "اسم ولد", "اسم بنت", "أكلة", "ماركة", "لون", "رياضة",
    "فاكهة أو خضار", "نهر أو بحر",
]

MAX_CATEGORIES_PER_ROUND = 5  # حد أقصى: نافذة الإدخال (Modal) بديسكورد تسمح بـ٥ حقول فقط


def normalize_arabic(text: str) -> str:
    """تطبيع بسيط للنص العربي لمقارنة الإجابات المتشابهة (همزات، تاء مربوطة...)."""
    text = (text or "").strip()
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = text.replace("ؤ", "و").replace("ئ", "ي")
    text = "".join(text.split())
    return text.lower()


class RiplacaRound:
    def __init__(self, letter: str, categories: list):
        self.letter = letter
        self.categories = categories
        self.answers = {}    # {player_id: {category: نص}}
        self.finished = False

    def submit(self, player_id, answers: dict):
        """يسجل/يحدّث إجابات لاعب لهذه الجولة."""
        self.answers[player_id] = {
            cat: (answers.get(cat, "") or "").strip() for cat in self.categories
        }

    def has_submitted(self, player_id) -> bool:
        return player_id in self.answers


class RiplacaGame:
    def __init__(self, player_ids, total_rounds=5, categories_per_round=5, round_seconds=90):
        if len(player_ids) < 2:
            raise ValueError("تحتاج لاعبين اثنين على الأقل")
        self.players = list(player_ids)
        self.total_rounds = max(1, min(total_rounds, 10))
        self.categories_per_round = max(3, min(categories_per_round, MAX_CATEGORIES_PER_ROUND))
        self.round_seconds = max(30, min(round_seconds, 240))
        self.round_number = 0
        self.scores = {pid: 0 for pid in self.players}
        self.used_letters = set()
        self.rounds_history = []
        self.current_round: RiplacaRound = None
        self.finished = False

    def start_next_round(self) -> RiplacaRound:
        available_letters = [l for l in LETTERS if l not in self.used_letters] or LETTERS[:]
        letter = random.choice(available_letters)
        self.used_letters.add(letter)
        cats = random.sample(CATEGORIES, min(self.categories_per_round, len(CATEGORIES)))
        self.round_number += 1
        self.current_round = RiplacaRound(letter, cats)
        return self.current_round

    def score_round(self, verdicts: dict) -> dict:
        """
        verdicts: {player_id: {category: True/False}} - حكم صحة كل إجابة.
        يحدّث self.scores تراكميًا ويرجّع تفصيل النقاط لهذه الجولة فقط.
        """
        r = self.current_round
        points_breakdown = {pid: {} for pid in self.players}

        for cat in r.categories:
            normalized_correct = {}
            for pid in self.players:
                ans = r.answers.get(pid, {}).get(cat, "")
                is_correct = bool(verdicts.get(pid, {}).get(cat, False))
                if is_correct and ans:
                    key = normalize_arabic(ans)
                    normalized_correct.setdefault(key, []).append(pid)

            for pid in self.players:
                ans = r.answers.get(pid, {}).get(cat, "")
                is_correct = bool(verdicts.get(pid, {}).get(cat, False))
                if not ans or not is_correct:
                    points_breakdown[pid][cat] = 0
                    continue
                key = normalize_arabic(ans)
                sharers = normalized_correct.get(key, [pid])
                pts = 10 if len(sharers) == 1 else 5
                points_breakdown[pid][cat] = pts
                self.scores[pid] += pts

        r.finished = True
        self.rounds_history.append({
            "letter": r.letter,
            "categories": list(r.categories),
            "answers": {pid: dict(r.answers.get(pid, {})) for pid in self.players},
            "points": points_breakdown,
        })
        if self.round_number >= self.total_rounds:
            self.finished = True
        return points_breakdown

    def standings(self):
        """ترتيب اللاعبين تنازليًا حسب النقاط."""
        return sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)

    def winners(self):
        """قائمة الفائز/الفائزين (أكثر من واحد بحال التعادل)."""
        st = self.standings()
        if not st:
            return []
        top_score = st[0][1]
        return [pid for pid, sc in st if sc == top_score]
