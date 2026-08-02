# -*- coding: utf-8 -*-
"""محرك لعبة المحيبس العراقية - نسخة رقمية مبسطة وعادلة لديسكورد."""
import random


class MheibesGame:
    TARGET_SCORE = 7

    def __init__(self, team_a, team_b):
        """team_a, team_b: قوائم user_id."""
        self.team_a = list(team_a)
        self.team_b = list(team_b)
        self.scores = {"a": 0, "b": 0}
        self.hiding_team = "a"      # الفريق اللي يخبي المحبس هالجولة
        self.holder = None          # مين ماسك المحبس فعليًا
        self.excluded = set()       # لاعبين استبعدهم القاضي هالجولة (خطأ)
        self.round_over = False
        self.game_over = False
        self.champion = None
        self.round_number = 1
        self.last_result = None
        self._start_round()

    def _hiders(self):
        return self.team_a if self.hiding_team == "a" else self.team_b

    def _guessers_team(self):
        return "b" if self.hiding_team == "a" else "a"

    def _start_round(self):
        self.holder = random.choice(self._hiders())
        self.excluded = set()
        self.round_over = False
        self.last_result = None

    def remaining_suspects(self):
        return [p for p in self._hiders() if p not in self.excluded]

    def guess(self, guesser_id, target_user_id):
        """القاضي (من فريق التخمين) يخمّن لاعبًا من الفريق المخبّي."""
        if self.game_over:
            raise ValueError("انتهت اللعبة")
        if self.round_over:
            raise ValueError("انتهت الجولة، ابدأ جولة جديدة")
        guessing_team = self._guessers_team()
        team_members = self.team_a if guessing_team == "a" else self.team_b
        if guesser_id not in team_members:
            raise ValueError("أنت لست في فريق التخمين هالجولة")
        if target_user_id not in self._hiders():
            raise ValueError("هذا اللاعب مو من الفريق المخبّي")
        if target_user_id in self.excluded:
            raise ValueError("تم استبعاد هذا اللاعب مسبقًا")

        if target_user_id == self.holder:
            self.scores[guessing_team] += 2
            self.last_result = "correct"
            self.round_over = True
            self._check_winner()
            if not self.game_over:
                self.hiding_team = guessing_team  # الفريق الفاشل بالإخفاء يصير مخمّن... الفريق الفايز بالتخمين يصير يخبي
                self._start_round()
            return True
        else:
            self.excluded.add(target_user_id)
            self.last_result = "wrong"
            remaining = self.remaining_suspects()
            if len(remaining) <= 1:
                # الفريق المخبي نجح بتضليل كل التخمينات -> يسجل نقطة ويستمر بالإخفاء
                self.scores[self.hiding_team] += 3
                self.round_over = True
                self._check_winner()
                if not self.game_over:
                    self.round_number += 1
                    self._start_round()
            return False

    def _check_winner(self):
        for team in ("a", "b"):
            if self.scores[team] >= self.TARGET_SCORE:
                self.game_over = True
                self.champion = team
                return

    def score_string(self):
        return f"فريق أ: {self.scores['a']} | فريق ب: {self.scores['b']}"
