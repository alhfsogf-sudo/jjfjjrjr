# -*- coding: utf-8 -*-
"""محرك لعبة الدومنو (الدومنة) - دعم 2 إلى 4 لاعبين، طقم مزدوج-ستة (28 قطعة)."""
import random


def full_set():
    return [(a, b) for a in range(7) for b in range(a, 7)]


class DominoGame:
    def __init__(self, player_ids):
        assert 2 <= len(player_ids) <= 4
        self.players = list(player_ids)          # ترتيب اللعب
        self.hands = {pid: [] for pid in self.players}
        self.boneyard = []
        self.board = []              # قائمة قطع بالترتيب كما وُضعت على الطاولة (بصيغتها بعد التدوير)
        self.left_end = None
        self.right_end = None
        self.current_index = 0
        self.passes_in_row = 0
        self.finished = False
        self.winner = None           # user_id أو "block" نتيجة انسداد
        self.last_action = None
        self._deal()

    # ------------------------------------------------------------------
    def _deal(self):
        tiles = full_set()
        random.shuffle(tiles)
        for pid in self.players:
            self.hands[pid] = [tiles.pop() for _ in range(7)]
        self.boneyard = tiles

        # يبدأ صاحب أعلى دبل (6-6 فما دون)، وإلا صاحب أعلى قطعة عمومًا
        starter_index = 0
        best_double = -1
        best_any = (-1, -1, -1)
        for i, pid in enumerate(self.players):
            for tile in self.hands[pid]:
                if tile[0] == tile[1] and tile[0] > best_double:
                    best_double = tile[0]
                    starter_index = i
        if best_double == -1:
            best_score = -1
            for i, pid in enumerate(self.players):
                for tile in self.hands[pid]:
                    if sum(tile) > best_score:
                        best_score = sum(tile)
                        starter_index = i
        self.current_index = starter_index

    def current_player(self):
        return self.players[self.current_index]

    def hand_of(self, pid):
        return self.hands[pid]

    def playable_tiles(self, pid):
        """يرجع قائمة (tile, end) الممكنة: end هي 'left' أو 'right' أو 'any' لو الطاولة فاضية."""
        options = []
        if not self.board:
            for tile in self.hands[pid]:
                options.append((tile, "any"))
            return options
        for tile in self.hands[pid]:
            if tile[0] == self.left_end or tile[1] == self.left_end:
                options.append((tile, "left"))
            if tile[0] == self.right_end or tile[1] == self.right_end:
                options.append((tile, "right"))
        return options

    def can_play(self, pid):
        return len(self.playable_tiles(pid)) > 0

    def play(self, pid, tile, end):
        """end: 'left' أو 'right' أو 'any'. يرمي ValueError لو غير شرعي."""
        if self.finished:
            raise ValueError("انتهت اللعبة")
        if pid != self.current_player():
            raise ValueError("ليس دورك")
        norm_tile = tuple(tile)
        hand = self.hands[pid]
        matched = None
        for t in hand:
            if t == norm_tile or t == (norm_tile[1], norm_tile[0]):
                matched = t
                break
        if matched is None:
            raise ValueError("لا تملك هذه القطعة")

        if not self.board:
            self.board.append(matched)
            self.left_end, self.right_end = matched[0], matched[1]
        elif end == "left":
            a, b = matched
            if b == self.left_end:
                pass
            elif a == self.left_end:
                a, b = b, a
            else:
                raise ValueError("القطعة لا تطابق الطرف الأيسر")
            self.board.insert(0, (a, b))
            self.left_end = a
        elif end == "right":
            a, b = matched
            if a == self.right_end:
                pass
            elif b == self.right_end:
                a, b = b, a
            else:
                raise ValueError("القطعة لا تطابق الطرف الأيمن")
            self.board.append((a, b))
            self.right_end = b
        else:
            raise ValueError("يجب تحديد الطرف (يسار/يمين)")

        hand.remove(matched)
        self.passes_in_row = 0
        self.last_action = f"وضع {matched[0]}-{matched[1]}"

        if not hand:
            self.finished = True
            self.winner = pid
            return

        self._advance_turn()

    def draw(self, pid):
        if pid != self.current_player():
            raise ValueError("ليس دورك")
        if self.can_play(pid):
            raise ValueError("تملك قطعة قابلة للعب، لا يمكنك السحب")
        if not self.boneyard:
            raise ValueError("لا توجد قطع في الحوض")
        tile = self.boneyard.pop()
        self.hands[pid].append(tile)
        self.last_action = "سحب قطعة من الحوض"
        return tile

    def pass_turn(self, pid):
        if pid != self.current_player():
            raise ValueError("ليس دورك")
        if self.can_play(pid) or self.boneyard:
            raise ValueError("لا يمكنك تمرير الدور الآن")
        self.passes_in_row += 1
        self.last_action = "تمرير الدور"
        if self.passes_in_row >= len(self.players):
            self._end_by_block()
            return
        self._advance_turn()

    def _advance_turn(self):
        self.current_index = (self.current_index + 1) % len(self.players)

    def _end_by_block(self):
        self.finished = True
        scores = {pid: sum(a + b for a, b in self.hands[pid]) for pid in self.players}
        min_score = min(scores.values())
        winners = [pid for pid, s in scores.items() if s == min_score]
        self.winner = winners[0] if len(winners) == 1 else "tie"
        self.last_action = "انسداد اللعبة (لا أحد يقدر يلعب)"
        self.final_scores = scores

    def board_string(self):
        if not self.board:
            return "الطاولة فاضية"
        return " | ".join(f"{a}-{b}" for a, b in self.board)
