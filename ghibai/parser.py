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


def seat_hint(seats: list[Player]) -> str:
    order = "  ".join(f"{i}.{p.name}" for i, p in enumerate(seats, 1))
    example = ", ".join(["-5", "5", "", "6"][: len(seats)]) if len(seats) >= 2 else "-5, "
    return f"Thu tu cho: {order}\nVi du: {example}   (o trong = nguoi cam chuong)"


# Chi bat tin nhan tran chac chan la ket qua van, de khong an lam chat thuong trong group.
def looks_like_round(text: str, seats: list[Player]) -> bool:
    t = text.strip()
    if not t or not seats or not any(c.isdigit() for c in t):
        return False
    if "," in t and _POSITIONAL_SHAPE.match(t):
        return True
    padded = f" {normalize(t.replace(',', ' '))} "
    return sum(1 for p in seats if f" {p.norm_name} " in padded) >= 2


def parse_round(text: str, seats: list[Player]) -> ParsedRound:
    t = text.strip()
    if not seats:
        raise ParseError("Chua khai bao nguoi choi. Dung: /nguoichoi Huong, Hang, Toan, Thu")
    if not t:
        raise ParseError(f"Tin nhan trong.\n{seat_hint(seats)}")

    # Uu tien cu phap vi tri; chi roi sang cu phap ten khi tin nhan that su co ten nguoi choi.
    if "," in t and (_POSITIONAL_SHAPE.match(t) or not _mentions_any_name(t, seats)):
        return _parse_positional(t, seats)
    return _parse_named(t, seats)


def _mentions_any_name(text: str, seats: list[Player]) -> bool:
    padded = f" {normalize(text.replace(',', ' '))} "
    return any(f" {p.norm_name} " in padded for p in seats)


def _parse_positional(text: str, seats: list[Player]) -> ParsedRound:
    slots = [s.strip() for s in text.split(",")]
    if len(slots) != len(seats):
        raise ParseError(
            f"Ban co {len(seats)} cho nhung ban nhap {len(slots)} o.\n{seat_hint(seats)}"
        )

    banker_id: int | None = None
    scores: dict[int, int] = {}
    sat_out: list[int] = []

    for pos, (slot, player) in enumerate(zip(slots, seats), 1):
        low = slot.lower()
        if low in BANKER_SLOTS:
            if banker_id is not None:
                raise ParseError(
                    "Co 2 o trong nen khong biet ai cam chuong. "
                    f"Chi de trong dung 1 o.\n{seat_hint(seats)}"
                )
            banker_id = player.id
        elif low in SITOUT_SLOTS:
            sat_out.append(player.id)
        elif _NUMBER.match(slot):
            scores[player.id] = int(slot)
        else:
            raise ParseError(
                f"O thu {pos} ({player.name}) khong hieu: '{slot}'.\n"
                f"Moi o la 1 so diem, hoac de trong neu cam chuong, hoac 'x' neu bo van."
            )

    if banker_id is None:
        raise ParseError(
            "Chua danh dau nguoi cam chuong. De trong o cua nguoi cam chuong "
            f"(khong dien diem).\n{seat_hint(seats)}"
        )
    return _finish(banker_id, scores, sat_out, "positional")


def _parse_named(text: str, seats: list[Player]) -> ParsedRound:
    tokens = _tokenize_named(text, seats)

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
            raise ParseError(f"Thieu ten nguoi choi truoc '{value}'.\n{seat_hint(seats)}")

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
                    f"{player.name} la nguoi cam chuong nen khong dien diem "
                    "- diem cam chuong do bot tu tinh."
                )
            scores[player.id] = tokens[i][1]
            i += 1
        else:
            is_banker = True  # ten tran khong kem so = nguoi cam chuong

        if player.id in mentioned:
            raise ParseError(f"{player.name} bi nhap 2 lan trong cung 1 van.")
        mentioned.append(player.id)

        if is_banker:
            if banker_id is not None and banker_id != player.id:
                names = [p.name for p in seats if p.id in (banker_id, player.id)]
                raise ParseError(f"Co 2 nguoi cam chuong ({' va '.join(names)}). Chi duoc 1 nguoi.")
            banker_id = player.id

    if marked_next:
        raise ParseError("Thieu ten nguoi choi sau 'c:'.")

    absent = [p for p in seats if p.id not in mentioned]
    if banker_id is None:
        if len(absent) == 1:
            banker_id = absent[0].id
        elif not absent:
            raise ParseError(
                "Moi nguoi deu co diem nen khong biet ai cam chuong. "
                "Bo diem cua nguoi cam chuong, hoac them dau * sau ten."
            )
        else:
            names = ", ".join(p.name for p in absent)
            raise ParseError(f"Khong ro ai cam chuong giua: {names}. Them dau * sau ten nguoi do.")
        absent = []

    return _finish(banker_id, scores, [p.id for p in absent], "named")


def _tokenize_named(text: str, seats: list[Player]) -> list[tuple[str, object]]:
    marked = re.sub(r"\*", f" {_BANKER_SUFFIX} ", text)
    marked = re.sub(r"(?i)\b(?:chuong|chg|c)\s*:", f" {_BANKER_PREFIX} ", marked)
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
                    f"Khong nhan ra '{word}'. Nguoi choi hien tai: "
                    f"{', '.join(p.name for p in seats)}"
                )
    return tokens


def _finish(
    banker_id: int, scores: dict[int, int], sat_out: list[int], mode: str
) -> ParsedRound:
    if not scores:
        raise ParseError("Can it nhat 1 nguoi choi co diem ngoai nguoi cam chuong.")
    return ParsedRound(banker_id=banker_id, scores=scores, mode=mode, sat_out=sat_out)
