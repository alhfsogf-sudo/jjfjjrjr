# -*- coding: utf-8 -*-
"""محرك لعبة المافيا - أدوار: مافيا، طبيب، محقق، مواطن."""
import random


def role_counts(n_players):
    """يحدد عدد أدوار المافيا حسب عدد اللاعبين (نسخة متوازنة)."""
    if n_players < 5:
        n_mafia = 1
    elif n_players < 8:
        n_mafia = 2
    else:
        n_mafia = 3
    has_doctor = n_players >= 5
    has_detective = n_players >= 6
    return n_mafia, has_doctor, has_detective


class MafiaGame:
    PHASE_NIGHT = "night"
    PHASE_DAY = "day"
    PHASE_VOTE = "vote"
    PHASE_OVER = "over"

    def __init__(self, player_ids):
        assert len(player_ids) >= 4
        self.players = list(player_ids)
        random.shuffle(self.players)

        n_mafia, has_doctor, has_detective = role_counts(len(self.players))
        roles = ["مافيا"] * n_mafia
        if has_doctor:
            roles.append("طبيب")
        if has_detective:
            roles.append("محقق")
        while len(roles) < len(self.players):
            roles.append("مواطن")
        random.shuffle(roles)

        self.roles = dict(zip(self.players, roles))
        self.alive = {pid: True for pid in self.players}
        self.phase = self.PHASE_NIGHT
        self.round_number = 1
        self.winner = None          # "mafia" أو "town"
        self.night_actions = {}     # {"mafia_target": pid, "doctor_save": pid, "detective_check": pid}
        self.votes = {}             # voter_id -> target_id
        self.last_night_result = None
        self.last_detective_result = None
        self.log = []

    # ------------------------------------------------------------------
    def alive_players(self):
        return [p for p in self.players if self.alive[p]]

    def mafia_alive(self):
        return [p for p in self.alive_players() if self.roles[p] == "مافيا"]

    def town_alive(self):
        return [p for p in self.alive_players() if self.roles[p] != "مافيا"]

    def role_of(self, pid):
        return self.roles.get(pid)

    def is_alive(self, pid):
        return self.alive.get(pid, False)

    # ------------------------------------------------------------------
    # مرحلة الليل
    # ------------------------------------------------------------------
    def submit_mafia_target(self, target_id):
        if target_id not in self.alive_players():
            raise ValueError("الهدف غير موجود أو ميت")
        self.night_actions["mafia_target"] = target_id

    def submit_doctor_save(self, target_id):
        if target_id not in self.alive_players():
            raise ValueError("الهدف غير موجود أو ميت")
        self.night_actions["doctor_save"] = target_id

    def submit_detective_check(self, target_id):
        if target_id not in self.alive_players():
            raise ValueError("الهدف غير موجود أو ميت")
        self.night_actions["detective_check"] = target_id
        is_mafia = self.roles.get(target_id) == "مافيا"
        self.last_detective_result = (target_id, is_mafia)
        return is_mafia

    def resolve_night(self):
        """ينفذ نتائج الليل وينتقل للنهار. يرجع نص وصفي للنتيجة."""
        target = self.night_actions.get("mafia_target")
        saved = self.night_actions.get("doctor_save")
        killed = None
        if target and target != saved and self.alive.get(target):
            self.alive[target] = False
            killed = target

        self.last_night_result = killed
        self.night_actions = {}
        self.phase = self.PHASE_DAY
        self.log.append(f"الليلة {self.round_number}: " + (f"قُتل {killed}" if killed else "لم يُقتل أحد"))

        result = self._check_game_over()
        if result:
            self.phase = self.PHASE_OVER
        return killed

    # ------------------------------------------------------------------
    # مرحلة التصويت النهاري
    # ------------------------------------------------------------------
    def start_vote(self):
        self.phase = self.PHASE_VOTE
        self.votes = {}

    def cast_vote(self, voter_id, target_id):
        if not self.alive.get(voter_id):
            raise ValueError("اللاعب الميت لا يصوّت")
        if not self.alive.get(target_id):
            raise ValueError("لا يمكن التصويت على لاعب ميت")
        self.votes[voter_id] = target_id

    def resolve_vote(self):
        """يحسب أصوات الإعدام. يرجع (المطرود أو None, تعادل؟)."""
        if not self.votes:
            self.phase = self.PHASE_NIGHT
            self.round_number += 1
            return None, False

        tally = {}
        for target in self.votes.values():
            tally[target] = tally.get(target, 0) + 1
        max_votes = max(tally.values())
        top = [pid for pid, c in tally.items() if c == max_votes]

        eliminated = None
        tie = len(top) > 1
        if not tie:
            eliminated = top[0]
            self.alive[eliminated] = False
            self.log.append(f"النهار {self.round_number}: تم إعدام {eliminated}")
        else:
            self.log.append(f"النهار {self.round_number}: تعادل بالتصويت، لا أحد يُعدم")

        self.votes = {}
        result = self._check_game_over()
        if result:
            self.phase = self.PHASE_OVER
        else:
            self.phase = self.PHASE_NIGHT
            self.round_number += 1
        return eliminated, tie

    # ------------------------------------------------------------------
    def _check_game_over(self):
        mafia = len(self.mafia_alive())
        town = len(self.town_alive())
        if mafia == 0:
            self.winner = "town"
            self.phase = self.PHASE_OVER
            return True
        if mafia >= town:
            self.winner = "mafia"
            self.phase = self.PHASE_OVER
            return True
        return False
