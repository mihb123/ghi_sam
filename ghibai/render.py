"""Dung message cho tung nen tang.

Telegram co <pre> nen bang so can cot duoc bang font monospace.
Zalo chi ho tro <b> <i> <u> <s>, khong co <pre>/<code>, nen bang can cot se vo font
=> Zalo dung layout moi dong 1 ban ghi thay vi bang. Do la khac biet layout thuc su,
khong phai chi doi tag, nen moi formatter tu quyet dinh cach trinh bay.
"""

from datetime import datetime
from html import escape

from .db import Player, Round
from .text import fmt_signed

TELEGRAM_LIMIT = 4096
ZALO_LIMIT = 2000


def _hhmm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except ValueError:
        return ""


class TelegramFmt:
    name = "telegram"
    parse_mode = "HTML"
    limit = TELEGRAM_LIMIT
    prefix = "/"

    def esc(self, s: str) -> str:
        return escape(str(s))

    def b(self, s: str) -> str:
        return f"<b>{escape(str(s))}</b>"

    def code(self, s: str) -> str:
        return f"<code>{escape(str(s))}</code>"

    def row_label(self, label: str, value: object) -> str:
        return str(value)

    def table(self, header: list[str], rows: list[list[str]]) -> str:
        return self._aligned(header, rows)

    def wide_table(self, header: list[str], rows: list[list[str]]) -> str:
        return self._aligned(header, rows)

    def _aligned(self, header: list[str], rows: list[list[str]]) -> str:
        cells = [header, *rows]
        widths = [max(len(str(r[i])) for r in cells) for i in range(len(header))]
        lines = ["  ".join(str(c).ljust(w) for c, w in zip(header, widths)).rstrip()]
        lines.append("  ".join("-" * w for w in widths))
        for row in rows:
            lines.append("  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip())
        return "\n<pre>" + escape("\n".join(lines)) + "</pre>"


class ZaloFmt:
    name = "zalo"
    parse_mode = "html"
    limit = ZALO_LIMIT
    # Zalo khong co menu lenh dang '/' nen dung '#' cho de go va de phan biet voi chat thuong.
    prefix = "#"

    def esc(self, s: str) -> str:
        return escape(str(s))

    def b(self, s: str) -> str:
        return f"<b>{escape(str(s))}</b>"

    def code(self, s: str) -> str:
        return escape(str(s))

    def row_label(self, label: str, value: object) -> str:
        return f"{label} {value}"

    # 2 cot: moi dong "ten  giatri" van doc duoc du font khong deu.
    def table(self, header: list[str], rows: list[list[str]]) -> str:
        lines = [" · ".join(str(c) for c in row if str(c)) for row in rows]
        return "\n" + escape("\n".join(lines))

    # Bang nhieu cot: gom moi ban ghi thanh 1 khoi 2 dong.
    def wide_table(self, header: list[str], rows: list[list[str]]) -> str:
        blocks = []
        for row in rows:
            lead = " · ".join(str(c) for c in row[:2] if str(c))
            rest = " · ".join(
                f"{h} {v}" for h, v in zip(header[2:], row[2:]) if str(v) not in ("", "-")
            )
            blocks.append(f"{escape(lead)}\n  {escape(rest)}")
        return "\n" + "\n".join(blocks)


# Zalo gioi han 2000 ky tu/tin nen phai cat; cat theo dong de khong dut giua bang.
def split_message(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
        while len(current) > limit:
            chunks.append(current[:limit])
            current = current[limit:]
    if current:
        chunks.append(current)
    return chunks


# Nguoi bo van van hien ten de khong ai tuong minh bi ghi thieu diem.
def _cell(fmt, player: Player, rnd: Round) -> str:
    name = fmt.esc(player.name)
    mark = "*" if player.id == rnd.banker_id else ""
    if player.id not in rnd.scores:
        return f"{name}{mark} (bo van)"
    return f"{name}{mark} {fmt_signed(rnd.scores[player.id])}"


def roster(fmt, seats: list[Player]) -> str:
    if not seats:
        return "Chua co nguoi choi nao. Dung:\n" + fmt.code(
            "/nguoichoi Huong, Hang, Toan, Thu"
        )
    order = "\n".join(f"{i}. {fmt.esc(p.name)}" for i, p in enumerate(seats, 1))
    example = ", ".join(["-5", "5", "", "6"][: len(seats)])
    return (
        f"{fmt.b(f'Nguoi choi ({len(seats)} cho)')}\n{order}\n\n"
        f"Nhap 1 van theo dung thu tu tren:\n{fmt.code(example)}\n"
        "O trong = nguoi cam chuong (khong dien diem)."
    )


def round_saved(
    fmt, rnd: Round, seats: list[Player], totals: dict[int, int] | None = None, played: int = 0, edited: bool = False
) -> str:
    detail = " | ".join(_cell(fmt, p, rnd) for p in seats)
    verb = "Da sua" if edited else "Da ghi"
    head = f"{'✏️' if edited else '✅'} {fmt.b(f'{verb} van {rnd.seq}')}"
    return f"{head}\n{detail}"


def standings(
    fmt, seats: list[Player], totals: dict[int, int], played: int, title: str = "TONG"
) -> str:
    if not totals:
        return "Ban chua co van nao."
    ranked = sorted((p for p in seats if p.id in totals), key=lambda p: totals[p.id], reverse=True)
    rows = [[p.name, fmt_signed(totals[p.id])] for p in ranked]
    check = sum(totals.values())
    tail = "" if check == 0 else f"\n⚠️ Tong khong bang 0 ({check}) - co van bi loi."
    return f"{fmt.b(f'{title} sau {played} van')}{fmt.table(['Nguoi', 'Diem'], rows)}{tail}"


def history(fmt, rounds: list[Round], seats: list[Player], voided: list[int]) -> str:
    if not rounds:
        return "Ban chua co van nao."
    header = ["Van", "Gio", *[p.name for p in seats], "Chuong"]
    rows = []
    for r in rounds:
        banker = next((p.name for p in seats if p.id == r.banker_id), "?")
        cells = [fmt_signed(r.scores[p.id]) if p.id in r.scores else "-" for p in seats]
        rows.append([fmt.row_label("Van", r.seq), _hhmm(r.created_at), *cells, banker])
    note = f"\nDa xoa: van {', '.join(map(str, voided))}" if voided else ""
    return fmt.wide_table(header, rows) + note


def lifetime(fmt, stats: list[dict]) -> str:
    if not stats:
        return "Chua co du lieu nao."
    rows = [
        [s["name"], fmt_signed(s["total"]), str(s["rounds"]), str(s["banker_rounds"])]
        for s in stats
    ]
    return fmt.b("Xep hang tich luy") + fmt.wide_table(["Nguoi", "Tong", "Van", "Chuong"], rows)
