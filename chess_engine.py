# -*- coding: utf-8 -*-
"""
محرك شطرنج قائم بذاته (بدون أي مكتبات خارجية) - يدعم:
- توليد كل الحركات الشرعية (بيادق/فرسان/أفيال/قلاع/وزراء/ملوك)
- التبييت (Castling) من الجهتين + شروطه الكاملة
- الأسر بالمرور (En Passant)
- ترقية البيدق (Promotion)
- كشف الكش، كش ملك، تعادل بالغرق (Stalemate)
- تعادل بنقص المادة، وتعادل بتكرار الوضعية 3 مرات، وقاعدة الخمسين نقلة
- تمثيل الحركات بترميز جبري قياسي (SAN) وترميز إحداثي بسيط (e2e4)
"""

FILES = "abcdefgh"


def sq(file, rank):
    return rank * 8 + file


def file_of(square):
    return square % 8


def rank_of(square):
    return square // 8


def algebraic(square):
    return f"{FILES[file_of(square)]}{rank_of(square) + 1}"


def parse_algebraic(text):
    text = text.strip().lower()
    file = FILES.index(text[0])
    rank = int(text[1]) - 1
    return sq(file, rank)


def is_white_piece(p):
    return p != "." and p.isupper()


def is_black_piece(p):
    return p != "." and p.islower()


def color_of(p):
    if p == ".":
        return None
    return "w" if p.isupper() else "b"


KNIGHT_OFFSETS = [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]
KING_OFFSETS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
QUEEN_DIRS = BISHOP_DIRS + ROOK_DIRS

UNICODE_PIECES = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
    ".": "·",
}

PIECE_NAMES_AR = {
    "P": "بيدق", "N": "حصان", "B": "فيل", "R": "قلعة", "Q": "وزير", "K": "ملك",
}


class Move:
    __slots__ = ("frm", "to", "promotion", "is_capture", "is_castle_king",
                 "is_castle_queen", "is_en_passant", "piece")

    def __init__(self, frm, to, promotion=None, is_capture=False,
                 is_castle_king=False, is_castle_queen=False,
                 is_en_passant=False, piece=""):
        self.frm = frm
        self.to = to
        self.promotion = promotion
        self.is_capture = is_capture
        self.is_castle_king = is_castle_king
        self.is_castle_queen = is_castle_queen
        self.is_en_passant = is_en_passant
        self.piece = piece

    def uci(self):
        s = algebraic(self.frm) + algebraic(self.to)
        if self.promotion:
            s += self.promotion.lower()
        return s

    def __eq__(self, other):
        return (self.frm == other.frm and self.to == other.to and
                (self.promotion or "").lower() == (other.promotion or "").lower())

    def __repr__(self):
        return self.uci()


class ChessGame:
    def __init__(self):
        self.board = list(
            "RNBQKBNR"
            "PPPPPPPP"
            "................................"
            "pppppppp"
            "rnbqkbnr"
        )
        self.turn = "w"
        self.castling = set(["K", "Q", "k", "q"])
        self.en_passant = None  # target square index or None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.history_san = []
        self.position_counts = {}
        self._record_position()

    # ---------------------------------------------------------------
    # أدوات مساعدة عامة
    # ---------------------------------------------------------------
    def clone(self):
        g = ChessGame.__new__(ChessGame)
        g.board = self.board[:]
        g.turn = self.turn
        g.castling = set(self.castling)
        g.en_passant = self.en_passant
        g.halfmove_clock = self.halfmove_clock
        g.fullmove_number = self.fullmove_number
        g.history_san = self.history_san[:]
        g.position_counts = dict(self.position_counts)
        return g

    def _position_key(self):
        return (
            "".join(self.board), self.turn,
            "".join(sorted(self.castling)), self.en_passant,
        )

    def _record_position(self):
        key = self._position_key()
        self.position_counts[key] = self.position_counts.get(key, 0) + 1

    def king_square(self, color):
        target = "K" if color == "w" else "k"
        return self.board.index(target)

    def is_square_attacked(self, square, by_color):
        board = self.board
        f0, r0 = file_of(square), rank_of(square)

        # هجوم الفرسان
        for df, dr in KNIGHT_OFFSETS:
            f, r = f0 + df, r0 + dr
            if 0 <= f < 8 and 0 <= r < 8:
                p = board[sq(f, r)]
                if color_of(p) == by_color and p.upper() == "N":
                    return True

        # هجوم الملك (للتحقق من التقارب بين الملوك)
        for df, dr in KING_OFFSETS:
            f, r = f0 + df, r0 + dr
            if 0 <= f < 8 and 0 <= r < 8:
                p = board[sq(f, r)]
                if color_of(p) == by_color and p.upper() == "K":
                    return True

        # هجوم الأفيال/الوزراء بالقطر
        for df, dr in BISHOP_DIRS:
            f, r = f0 + df, r0 + dr
            while 0 <= f < 8 and 0 <= r < 8:
                p = board[sq(f, r)]
                if p != ".":
                    if color_of(p) == by_color and p.upper() in ("B", "Q"):
                        return True
                    break
                f += df
                r += dr

        # هجوم القلاع/الوزراء بالمستقيم
        for df, dr in ROOK_DIRS:
            f, r = f0 + df, r0 + dr
            while 0 <= f < 8 and 0 <= r < 8:
                p = board[sq(f, r)]
                if p != ".":
                    if color_of(p) == by_color and p.upper() in ("R", "Q"):
                        return True
                    break
                f += df
                r += dr

        # هجوم البيادق
        pawn_dir = -1 if by_color == "w" else 1  # اتجاه الهجوم *نحو* المربع من موقع البيدق
        for df in (-1, 1):
            f, r = f0 + df, r0 + pawn_dir
            if 0 <= f < 8 and 0 <= r < 8:
                p = board[sq(f, r)]
                if color_of(p) == by_color and p.upper() == "P":
                    return True

        return False

    def is_in_check(self, color):
        return self.is_square_attacked(self.king_square(color), "b" if color == "w" else "w")

    # ---------------------------------------------------------------
    # توليد الحركات
    # ---------------------------------------------------------------
    def generate_pseudo_legal_moves(self):
        moves = []
        board = self.board
        turn = self.turn
        opp = "b" if turn == "w" else "w"

        for square in range(64):
            p = board[square]
            if p == "." or color_of(p) != turn:
                continue
            f0, r0 = file_of(square), rank_of(square)
            kind = p.upper()

            if kind == "P":
                direction = 1 if turn == "w" else -1
                start_rank = 1 if turn == "w" else 6
                promo_rank = 7 if turn == "w" else 0

                one_r = r0 + direction
                if 0 <= one_r < 8:
                    one_sq = sq(f0, one_r)
                    if board[one_sq] == ".":
                        if one_r == promo_rank:
                            for promo in ("Q", "R", "B", "N"):
                                moves.append(Move(square, one_sq, promotion=promo, piece=p))
                        else:
                            moves.append(Move(square, one_sq, piece=p))
                        # نقلتين من مربع البداية
                        if r0 == start_rank:
                            two_r = r0 + 2 * direction
                            two_sq = sq(f0, two_r)
                            if board[two_sq] == ".":
                                moves.append(Move(square, two_sq, piece=p))

                for df in (-1, 1):
                    f = f0 + df
                    r = r0 + direction
                    if 0 <= f < 8 and 0 <= r < 8:
                        target = sq(f, r)
                        tp = board[target]
                        if color_of(tp) == opp:
                            if r == promo_rank:
                                for promo in ("Q", "R", "B", "N"):
                                    moves.append(Move(square, target, promotion=promo,
                                                       is_capture=True, piece=p))
                            else:
                                moves.append(Move(square, target, is_capture=True, piece=p))
                        elif target == self.en_passant:
                            moves.append(Move(square, target, is_capture=True,
                                               is_en_passant=True, piece=p))

            elif kind == "N":
                for df, dr in KNIGHT_OFFSETS:
                    f, r = f0 + df, r0 + dr
                    if 0 <= f < 8 and 0 <= r < 8:
                        target = sq(f, r)
                        tp = board[target]
                        if color_of(tp) != turn:
                            moves.append(Move(square, target, is_capture=(tp != "."), piece=p))

            elif kind == "K":
                for df, dr in KING_OFFSETS:
                    f, r = f0 + df, r0 + dr
                    if 0 <= f < 8 and 0 <= r < 8:
                        target = sq(f, r)
                        tp = board[target]
                        if color_of(tp) != turn:
                            moves.append(Move(square, target, is_capture=(tp != "."), piece=p))

                # التبييت
                back_rank = 0 if turn == "w" else 7
                if square == sq(4, back_rank) and not self.is_in_check(turn):
                    k_flag = "K" if turn == "w" else "k"
                    q_flag = "Q" if turn == "w" else "q"
                    if k_flag in self.castling:
                        f_sq, g_sq, h_sq = sq(5, back_rank), sq(6, back_rank), sq(7, back_rank)
                        if board[f_sq] == "." and board[g_sq] == "." and board[h_sq].upper() == "R" \
                                and color_of(board[h_sq]) == turn:
                            if not self.is_square_attacked(f_sq, opp) and not self.is_square_attacked(g_sq, opp):
                                moves.append(Move(square, g_sq, is_castle_king=True, piece=p))
                    if q_flag in self.castling:
                        d_sq, c_sq, b_sq, a_sq = sq(3, back_rank), sq(2, back_rank), sq(1, back_rank), sq(0, back_rank)
                        if board[d_sq] == "." and board[c_sq] == "." and board[b_sq] == "." \
                                and board[a_sq].upper() == "R" and color_of(board[a_sq]) == turn:
                            if not self.is_square_attacked(d_sq, opp) and not self.is_square_attacked(c_sq, opp):
                                moves.append(Move(square, c_sq, is_castle_queen=True, piece=p))

            else:  # B, R, Q
                dirs = BISHOP_DIRS if kind == "B" else ROOK_DIRS if kind == "R" else QUEEN_DIRS
                for df, dr in dirs:
                    f, r = f0 + df, r0 + dr
                    while 0 <= f < 8 and 0 <= r < 8:
                        target = sq(f, r)
                        tp = board[target]
                        if tp == ".":
                            moves.append(Move(square, target, piece=p))
                        else:
                            if color_of(tp) == opp:
                                moves.append(Move(square, target, is_capture=True, piece=p))
                            break
                        f += df
                        r += dr

        return moves

    def _apply_move_inplace(self, move):
        """ينفذ الحركة على اللوحة الحالية دون فحوصات شرعية (يستخدم داخليًا)."""
        board = self.board
        moving_piece = board[move.frm]
        captured_piece = board[move.to]
        turn = self.turn

        new_en_passant = None

        if move.is_en_passant:
            board[move.to] = moving_piece
            board[move.frm] = "."
            captured_sq = sq(file_of(move.to), rank_of(move.frm))
            board[captured_sq] = "."
        elif move.is_castle_king or move.is_castle_queen:
            back_rank = rank_of(move.frm)
            board[move.to] = moving_piece
            board[move.frm] = "."
            if move.is_castle_king:
                rook_from, rook_to = sq(7, back_rank), sq(5, back_rank)
            else:
                rook_from, rook_to = sq(0, back_rank), sq(3, back_rank)
            board[rook_to] = board[rook_from]
            board[rook_from] = "."
        else:
            board[move.to] = moving_piece
            board[move.frm] = "."
            if move.promotion:
                board[move.to] = move.promotion if turn == "w" else move.promotion.lower()
            if moving_piece.upper() == "P" and abs(rank_of(move.to) - rank_of(move.frm)) == 2:
                new_en_passant = sq(file_of(move.frm), (rank_of(move.frm) + rank_of(move.to)) // 2)

        # تحديث حقوق التبييت
        def strip_rights(square_moved_from_or_to, color):
            back_rank = 0 if color == "w" else 7
            k_flag, q_flag = ("K", "Q") if color == "w" else ("k", "q")
            if square_moved_from_or_to == sq(4, back_rank):
                self.castling.discard(k_flag)
                self.castling.discard(q_flag)
            if square_moved_from_or_to == sq(7, back_rank):
                self.castling.discard(k_flag)
            if square_moved_from_or_to == sq(0, back_rank):
                self.castling.discard(q_flag)

        strip_rights(move.frm, turn)
        opp = "b" if turn == "w" else "w"
        strip_rights(move.to, opp)

        # عداد نصف النقلات (لقاعدة الخمسين نقلة)
        if moving_piece.upper() == "P" or captured_piece != "." or move.is_en_passant:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if turn == "b":
            self.fullmove_number += 1

        self.en_passant = new_en_passant
        self.turn = opp

    def legal_moves(self):
        pseudo = self.generate_pseudo_legal_moves()
        legal = []
        turn = self.turn
        for m in pseudo:
            trial = self.clone()
            trial._apply_move_inplace(m)
            if not trial.is_in_check(turn):
                legal.append(m)
        return legal

    def is_checkmate(self):
        return self.is_in_check(self.turn) and len(self.legal_moves()) == 0

    def is_stalemate(self):
        return not self.is_in_check(self.turn) and len(self.legal_moves()) == 0

    def is_insufficient_material(self):
        pieces = [p for p in self.board if p != "."]
        non_king = [p for p in pieces if p.upper() != "K"]
        if not non_king:
            return True
        if len(non_king) == 1 and non_king[0].upper() in ("B", "N"):
            return True
        if len(non_king) == 2 and all(p.upper() == "B" for p in non_king):
            squares = [i for i, p in enumerate(self.board) if p.upper() == "B"]
            colors = set(((file_of(s) + rank_of(s)) % 2) for s in squares)
            if len(colors) == 1:
                return True
        return False

    def is_threefold_repetition(self):
        return self.position_counts.get(self._position_key(), 0) >= 3

    def is_fifty_move_rule(self):
        return self.halfmove_clock >= 100

    def game_result(self):
        """يرجع (انتهت؟, نتيجة نصية) أو (False, None)."""
        if self.is_checkmate():
            winner = "الأسود" if self.turn == "w" else "الأبيض"
            return True, f"كش ملك! فاز {winner} 🏆"
        if self.is_stalemate():
            return True, "تعادل بالغرق (Stalemate) 🤝"
        if self.is_insufficient_material():
            return True, "تعادل بسبب نقص المادة الكافية للفوز 🤝"
        if self.is_threefold_repetition():
            return True, "تعادل بتكرار نفس الوضعية 3 مرات 🤝"
        if self.is_fifty_move_rule():
            return True, "تعادل بقاعدة الخمسين نقلة 🤝"
        return False, None

    # ---------------------------------------------------------------
    # تنفيذ حركة من الخارج (uci) + تسجيل SAN
    # ---------------------------------------------------------------
    def find_move(self, uci_or_alg):
        text = uci_or_alg.strip().lower().replace("x", "").replace("+", "").replace("#", "")
        legal = self.legal_moves()
        if len(text) >= 4 and text[0] in FILES and text[2] in FILES:
            try:
                frm = parse_algebraic(text[0:2])
                to = parse_algebraic(text[2:4])
            except Exception:
                return None
            promo = text[4].upper() if len(text) >= 5 else None
            for m in legal:
                if m.frm == frm and m.to == to and (m.promotion or None) == (promo or m.promotion if promo is None else promo):
                    if promo:
                        if (m.promotion or "").upper() == promo:
                            return m
                    else:
                        if not m.promotion:
                            return m
            # لو فيه ترقية إجبارية بدون تحديد حرف، خذ الوزير افتراضيًا
            for m in legal:
                if m.frm == frm and m.to == to and m.promotion == "Q":
                    return m
        return None

    def san_for(self, move, legal_moves=None):
        if legal_moves is None:
            legal_moves = self.legal_moves()
        piece = move.piece.upper()

        if move.is_castle_king:
            base = "O-O"
        elif move.is_castle_queen:
            base = "O-O-O"
        else:
            capture = move.is_capture
            dest = algebraic(move.to)
            if piece == "P":
                base = (FILES[file_of(move.frm)] + "x" + dest) if capture else dest
                if move.promotion:
                    base += "=" + move.promotion
            else:
                # تفريق بين قطعتين من نفس النوع تقدران تصلا لنفس المربع
                ambiguous = [m for m in legal_moves if m.piece.upper() == piece and m.to == move.to and m.frm != move.frm]
                disamb = ""
                if ambiguous:
                    same_file = any(file_of(m.frm) == file_of(move.frm) for m in ambiguous)
                    same_rank = any(rank_of(m.frm) == rank_of(move.frm) for m in ambiguous)
                    if not same_file:
                        disamb = FILES[file_of(move.frm)]
                    elif not same_rank:
                        disamb = str(rank_of(move.frm) + 1)
                    else:
                        disamb = algebraic(move.frm)
                base = piece + disamb + ("x" if capture else "") + dest

        trial = self.clone()
        trial._apply_move_inplace(move)
        if trial.is_in_check(trial.turn):
            base += "#" if (len(trial.legal_moves()) == 0) else "+"

        return base

    def push(self, move):
        legal = self.legal_moves()
        san = self.san_for(move, legal)
        self._apply_move_inplace(move)
        self.history_san.append(san)
        self._record_position()
        return san

    # ---------------------------------------------------------------
    # عرض اللوحة
    # ---------------------------------------------------------------
    def render_unicode(self, flipped=False):
        rows = range(7, -1, -1) if not flipped else range(8)
        lines = []
        for r in rows:
            rank_label = r + 1
            files_range = range(8) if not flipped else range(7, -1, -1)
            row_cells = []
            for f in files_range:
                p = self.board[sq(f, r)]
                row_cells.append(UNICODE_PIECES[p])
            lines.append(f"{rank_label} " + " ".join(row_cells))
        file_labels = FILES if not flipped else FILES[::-1]
        lines.append("  " + " ".join(file_labels))
        return "```\n" + "\n".join(lines) + "\n```"
