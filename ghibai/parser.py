"""Doc ket qua 1 van tu tin nhan Telegram.

Hai cu phap, tu dong nhan dien:

  1. Theo vi tri (mac dinh, nhanh nhat) - so luong o phai dung so cho ngoi:
       -5, 5, , 6      -> o trong la nguoi cam chuong
       -5, 5, c, 6     -> 'c' cung la cam chuong
       -5, 5, , x      -> 'x' la nguoi bo van nay

  2. Theo ten (khi ban muon ghi ro):
       Huong -5, Hang 5, Toan, Thu 6      ten tran = cam chuong
       Toan*, Huong -5, Hang 5, Thu 6     dau * = cam chuong
       c:Toan Huong -5 Hang 5 Thu 6       tien to c: = cam chuong

Diem cua nguoi cam chuong KHONG BAO GIO do user nhap - xem scoring.resolve_scores.
"""

import re
from dataclasses import dataclass, field

from .db import Player
from .text import normalize

BANKER_SLOTS = {"", "c"}
SITOUT_SLOTS = {"x"}

_POSITIONAL_SHAPE = re.compile(r"^[0-9+\-,\scCxX]*$")
_NUMBER = re.compile(r"^[+-]?\d+$")
_BANKER_SUFFIX = "\x00B"
_BANKER_PREFIX = "\x00C"


class ParseError(Exception):
    """Loi nhap; message duoc hien thi thang cho user nen phai viet bang tieng Viet."""


@dataclass(frozen=True)
class ParsedRound:
    banker_id: int
    scores: dict[int, int]  # chi nguoi choi thuong, chua co chuong
    mode: str
    sat_out: list[int] = field(default_factory=list)


def example_round(count: int, game_type: str = "3cay") -> str:
    if count < 2:
        return "-5, c"
    if count == 2:
        return "-5, c"
    if count == 3:
        return "-5, -10, c" if game_type == "sam" else "-5, 5, c"

    if game_type == "sam":
        pool = ["-5", "-10", "-20", "-15", "-8", "-12", "-4", "-6", "-14", "-18"]
    else:
        pool = ["-5", "5", "6", "-10", "8", "-3", "4", "-2", "7", "-6"]

    slots: list[str] = []
    pool_idx = 0
    for i in range(count):
        if i == 2:
            slots.append("c")
        else:
            slots.append(pool[pool_idx % len(pool)])
            pool_idx += 1
    return ", ".join(slots)


def seat_hint(seats: list[Player], game_type: str = "3cay") -> str:
    role = "người thắng" if game_type == "sam" else "người cầm chương"
    order = "  ".join(f"{i}.{p.name}" for i, p in enumerate(seats, 1))
    example = example_round(len(seats), game_type)
    return f"Thứ tự chỗ: {order}\nVí dụ: {example}   (c = {role})"


# Chi bat tin nhan tran chac chan la ket qua van, de khong an lam chat thuong trong group.
def looks_like_round(text: str, seats: list[Player]) -> bool:
    t = text.strip()
    if not t or not seats or not any(c.isdigit() for c in t):
        return False
    if "," in t and _POSITIONAL_SHAPE.match(t):
        return True
    padded = f" {normalize(t.replace(',', ' '))} "
    return sum(1 for p in seats if f" {p.norm_name} " in padded) >= 2


def parse_round(text: str, seats: list[Player], game_type: str = "3cay") -> ParsedRound:
    t = text.strip()
    if not seats:
        raise ParseError("Chưa khai báo người chơi. Dùng: /nguoichoi Hương, Hằng, Toàn, Thu")
    if not t:
        raise ParseError(f"Tin nhắn trống.\n{seat_hint(seats, game_type)}")

    # Uu tien cu phap vi tri; chi roi sang cu phap ten khi tin nhan that su co ten nguoi choi.
    if "," in t and (_POSITIONAL_SHAPE.match(t) or not _mentions_any_name(t, seats)):
        return _parse_positional(t, seats, game_type)
    return _parse_named(t, seats, game_type)


def _mentions_any_name(text: str, seats: list[Player]) -> bool:
    padded = f" {normalize(text.replace(',', ' '))} "
    return any(f" {p.norm_name} " in padded for p in seats)


def _parse_positional(text: str, seats: list[Player], game_type: str = "3cay") -> ParsedRound:
    slots = [s.strip() for s in text.split(",")]
    if len(slots) != len(seats):
        raise ParseError(
            f"Bàn có {len(seats)} chỗ nhưng bạn nhập {len(slots)} ô.\n{seat_hint(seats, game_type)}"
        )

    role_verb = "thắng" if game_type == "sam" else "cầm chương"
    role_subject = "người thắng" if game_type == "sam" else "người cầm chương"

    banker_id: int | None = None
    scores: dict[int, int] = {}
    sat_out: list[int] = []

    for pos, (slot, player) in enumerate(zip(slots, seats), 1):
        low = slot.lower()
        if low in BANKER_SLOTS:
            if banker_id is not None:
                raise ParseError(
                    f"Có 2 ô trống nên không biết ai {role_verb}. "
                    f"Chỉ để trống đúng 1 ô.\n{seat_hint(seats, game_type)}"
                )
            banker_id = player.id
        elif low in SITOUT_SLOTS:
            sat_out.append(player.id)
        elif _NUMBER.match(slot):
            scores[player.id] = int(slot)
        else:
            raise ParseError(
                f"Ô thứ {pos} ({player.name}) không hiểu: '{slot}'.\n"
                f"Mỗi ô là 1 số điểm, hoặc điền 'c' nếu {role_verb}, hoặc 'x' nếu bỏ ván."
            )

    if banker_id is None:
        raise ParseError(
            f"Chưa đánh dấu {role_subject}. Gõ c vào ô của {role_subject} "
            f"\n{seat_hint(seats, game_type)}"
        )
    return _finish(banker_id, scores, sat_out, "positional", game_type)


def _parse_named(text: str, seats: list[Player], game_type: str = "3cay") -> ParsedRound:
    tokens = _tokenize_named(text, seats)

    role_verb = "thắng" if game_type == "sam" else "cầm chương"
    role_subject = "người thắng" if game_type == "sam" else "người cầm chương"
    role_score = "thắng" if game_type == "sam" else "cầm chương"

    banker_id: int | None = None
    scores: dict[int, int] = {}
    mentioned: list[int] = []
    marked_next = False
    i = 0

    while i < len(tokens):
        kind, value = tokens[i]

        if kind == "prefix":
            marked_next = True
            i += 1
            continue
        if kind != "name":
            raise ParseError(f"Thiếu tên người chơi trước '{value}'.\n{seat_hint(seats, game_type)}")

        player: Player = value
        i += 1
        is_banker = marked_next
        marked_next = False

        if i < len(tokens) and tokens[i][0] == "suffix":
            is_banker = True
            i += 1
        if i < len(tokens) and tokens[i][0] == "num":
            if is_banker:
                raise ParseError(
                    f"{player.name} là {role_subject} nên không điền điểm "
                    f"- điểm {role_score} do bot tự tính."
                )
            scores[player.id] = tokens[i][1]
            i += 1
        else:
            is_banker = True  # ten tran khong kem so = nguoi cam chuong / nguoi thang

        if player.id in mentioned:
            raise ParseError(f"{player.name} bị nhập 2 lần trong cùng 1 ván.")
        mentioned.append(player.id)

        if is_banker:
            if banker_id is not None and banker_id != player.id:
                names = [p.name for p in seats if p.id in (banker_id, player.id)]
                raise ParseError(f"Có 2 {role_subject} ({' và '.join(names)}). Chỉ được 1 người.")
            banker_id = player.id

    if marked_next:
        raise ParseError("Thiếu tên người chơi sau tiền tố đánh dấu thắng/chương.")

    absent = [p for p in seats if p.id not in mentioned]
    if banker_id is None:
        if len(absent) == 1:
            banker_id = absent[0].id
        elif not absent:
            raise ParseError(
                f"Mọi người đều có điểm nên không biết ai {role_verb}. "
                f"Bỏ điểm của {role_subject}, hoặc thêm dấu * sau tên."
            )
        else:
            names = ", ".join(p.name for p in absent)
            raise ParseError(f"Không rõ ai {role_verb} giữa: {names}. Thêm dấu * sau tên người đó.")
        absent = []

    return _finish(banker_id, scores, [p.id for p in absent], "named", game_type)


def _tokenize_named(text: str, seats: list[Player]) -> list[tuple[str, object]]:
    marked = re.sub(r"\*", f" {_BANKER_SUFFIX} ", text)
    marked = re.sub(r"(?i)\b(?:chuong|chg|c|thang|thg|t|win|w)\s*:", f" {_BANKER_PREFIX} ", marked)
    words = marked.replace(",", " ").split()

    index = {p.norm_name: p for p in seats}
    max_words = max((len(p.norm_name.split()) for p in seats), default=1)

    tokens: list[tuple[str, object]] = []
    i = 0
    while i < len(words):
        word = words[i]
        if word == _BANKER_SUFFIX:
            tokens.append(("suffix", "*"))
            i += 1
        elif word == _BANKER_PREFIX:
            tokens.append(("prefix", "c:"))
            i += 1
        elif _NUMBER.match(word):
            tokens.append(("num", int(word)))
            i += 1
        else:
            for size in range(min(max_words, len(words) - i), 0, -1):
                key = normalize(" ".join(words[i : i + size]))
                if key in index:
                    tokens.append(("name", index[key]))
                    i += size
                    break
            else:
                raise ParseError(
                    f"Không nhận ra '{word}'. Người chơi hiện tại: "
                    f"{', '.join(p.name for p in seats)}"
                )
    return tokens


def _finish(
    banker_id: int, scores: dict[int, int], sat_out: list[int], mode: str, game_type: str = "3cay"
) -> ParsedRound:
    if not scores:
        role_subject = "người thắng" if game_type == "sam" else "người cầm chương"
        raise ParseError(f"Cần ít nhất 1 người chơi có điểm ngoài {role_subject}.")
    return ParsedRound(banker_id=banker_id, scores=scores, mode=mode, sat_out=sat_out)
