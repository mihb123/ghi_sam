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
        return f"{name}{mark} (bỏ ván)"
    return f"{name}{mark} {fmt_signed(rnd.scores[player.id])}"


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


def roster(fmt, seats: list[Player], game_type: str = "3cay") -> str:
    if not seats:
        return "Chưa có người chơi nào. Dùng:\n" + fmt.code(
            "/nguoichoi Hương, Hằng, Toàn, Thu"
        )
    role = "người thắng" if game_type == "sam" else "người cầm chương"
    order = "\n".join(f"{i}. {fmt.esc(p.name)}" for i, p in enumerate(seats, 1))
    example = example_round(len(seats), game_type)
    return (
        f"{fmt.b(f'Người chơi ({len(seats)} chỗ)')}\n{order}\n\n"
        f"Nhập 1 ván theo đúng thứ tự trên:\n{fmt.code(example)}\n"
        f"c = {role}."
    )


def round_saved(
    fmt, rnd: Round, seats: list[Player], totals: dict[int, int] | None = None, played: int = 0, edited: bool = False
) -> str:
    detail = " | ".join(_cell(fmt, p, rnd) for p in seats)
    verb = "Đã sửa" if edited else "Đã ghi"
    head = f"{'✏️' if edited else '✅'} {fmt.b(f'{verb} ván {rnd.seq}')}"
    return f"{head}\n{detail}"


def standings(
    fmt, seats: list[Player], totals: dict[int, int], played: int, title: str = "TỔNG", game_type: str = "3cay"
) -> str:
    if not totals:
        return "Bàn chưa có ván nào."
    ranked = sorted((p for p in seats if p.id in totals), key=lambda p: totals[p.id], reverse=True)
    rows = [[p.name, fmt_signed(totals[p.id])] for p in ranked]
    check = sum(totals.values())
    tail = "" if check == 0 else f"\n⚠️ Tổng không bằng 0 ({check}) - có ván bị lỗi."
    return f"{fmt.b(f'{title} sau {played} ván')}{fmt.table(['Người', 'Điểm'], rows)}{tail}"


def history(
    fmt, rounds: list[Round], seats: list[Player], voided: list[int], game_type: str = "3cay"
) -> str:
    if not rounds:
        return "Bàn chưa có ván nào."
    banker_col = "Thắng" if game_type == "sam" else "Chương"
    header = ["Ván", "Giờ", *[p.name for p in seats], banker_col]
    rows = []
    for r in rounds:
        banker = next((p.name for p in seats if p.id == r.banker_id), "?")
        cells = [fmt_signed(r.scores[p.id]) if p.id in r.scores else "-" for p in seats]
        rows.append([fmt.row_label("Ván", r.seq), _hhmm(r.created_at), *cells, banker])
    note = f"\nĐã xóa: ván {', '.join(map(str, voided))}" if voided else ""
    return fmt.wide_table(header, rows) + note


def lifetime(fmt, stats: list[dict], game_type: str = "3cay") -> str:
    if not stats:
        return "Chưa có dữ liệu nào."
    banker_col = "Thắng" if game_type == "sam" else "Chương"
    rows = [
        [s["name"], fmt_signed(s["total"]), str(s["rounds"]), str(s["banker_rounds"])]
        for s in stats
    ]
    return fmt.b("Xếp hạng tích lũy") + fmt.wide_table(["Người", "Tổng", "Ván", banker_col], rows)
