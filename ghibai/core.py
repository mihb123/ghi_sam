"""Toan bo logic lenh, khong biet gi ve Telegram hay Zalo.

Adapter nao goi cung tra ve list[str] la cac tin nhan can gui. Nho vay them nen tang moi
chi phai viet lop van chuyen, khong nhan ban logic.

Prefix lenh khac nhau theo nen tang (Telegram '/', Zalo '#') vi Zalo khong co menu lenh
dang '/'. Ca hai prefix deu duoc chap nhan o moi nen tang; rieng phan huong dan thi in
dung prefix cua nen tang dang dung.
"""

import asyncio
import re
from dataclasses import dataclass

from . import render
from .db import Database, Player, Round, Session, chat_key
from .parser import ParseError, looks_like_round, parse_round
from .scoring import ScoringError, resolve_scores
from .sheets import SheetError, SheetExporter, build_table, extract_key

from .text import normalize

_COMMAND = re.compile(r"^\s*[/#](?P<name>[0-9A-Za-z_]+)(?:@\S+)?\s*(?P<arg>.*)$", re.S)


@dataclass(frozen=True)
class Incoming:
    platform: str
    native_chat_id: str
    chat_title: str | None
    text: str
    author: str | None = None


@dataclass(frozen=True)
class Ctx:
    db: Database
    fmt: object
    key: str
    arg: str
    author: str | None

    def cmd(self, name: str) -> str:
        return self.fmt.code(f"{self.fmt.prefix}{name}")

    def plain_cmd(self, name: str) -> str:
        return f"{self.fmt.prefix}{name}"


def help_text(ctx: Ctx, game_type: str = "3cay") -> str:
    p = ctx.fmt.prefix
    b = ctx.fmt.b
    if game_type == "sam":
        return "\n".join(
            [
                b("Bot ghi điểm Sâm"),
                "",
                b("Người chơi"),
                f"{p}nguoichoi Hương, Hằng, Toàn, Thu - khai báo (thứ tự = thứ tự nhập điểm)",
                f"{p}dsnguoi - xem danh sách và thứ tự chỗ",
                f"{p}themnguoi Nam  ·  {p}xoanguoi Nam",
                "",
                b("Ghi ván"),
                "Gõ trần theo thứ tự chỗ, c = người thắng:",
                ctx.fmt.code("-5, -10, c, -20"),
                "Hoặc ghi rõ tên: " + ctx.fmt.code("Hương -5, Hằng -10, Toàn, Thu -20"),
                f"Thêm {p}v phía trước nếu muốn chắc chắn: " + ctx.fmt.code(f"{p}v -5, -10, c, -20"),
                "Dùng " + ctx.fmt.code("x") + " cho người bỏ ván: " + ctx.fmt.code("-5, -10, c, x"),
                "",
                b("Sửa / xóa khi nhập sai"),
                f"{p}undo - hủy ván vừa ghi",
                f"{p}xoa 3 - xóa ván số 3 (nhiều ván: {p}xoa 3 5 7)",
                f"{p}khoiphuc 3 - lấy lại ván đã xóa",
                f"{p}sua 3 -5, -10, c, -20 - nhập lại ván số 3",
                "",
                b("Xem"),
                f"{p}tong - điểm lũy kế bàn đang chơi",
                f"{p}lichsu 10 - 10 ván gần nhất",
                "",
                b("Bàn chơi"),
                f"{p}banmoi sam [ghi chú]  ·  {p}banmoi 3cay [ghi chú]  ·  {p}ketthuc",
                "",
                b("Trang web"),
                f"{p}web - link xem bàn đang chơi trên điện thoại",
                f"{p}web doilink - đổi link nếu bị lộ ra ngoài nhóm",
                "",
                b("Google Sheet"),
                f"{p}sheet [link] - lưu link sheet cho nhóm này",
                f"{p}export - ghi bàn đang chơi lên sheet",
                "",
                f"💡 Đang xem hướng dẫn chơi Sâm. Gõ {p}help 3cay để xem hướng dẫn 3 cây.",
            ]
        )
    return "\n".join(
        [
            b("Bot ghi điểm 3 cây"),
            "",
            b("Người chơi"),
            f"{p}nguoichoi Hương, Hằng, Toàn, Thu - khai báo (thứ tự = thứ tự nhập điểm)",
            f"{p}dsnguoi - xem danh sách và thứ tự chỗ",
            f"{p}themnguoi Nam  ·  {p}xoanguoi Nam",
            "",
            b("Ghi ván"),
            "Gõ trần theo thứ tự chỗ, c = người cầm chương:",
            ctx.fmt.code("-5, 5, c, 6"),
            "Hoặc ghi rõ tên: " + ctx.fmt.code("Hương -5, Hằng 5, Toàn, Thu 6"),
            f"Thêm {p}v phía trước nếu muốn chắc chắn: " + ctx.fmt.code(f"{p}v -5, 5, c, 6"),
            "Dùng " + ctx.fmt.code("x") + " cho người bỏ ván: " + ctx.fmt.code("-5, 5, c, x"),
            "",
            b("Sửa / xóa khi nhập sai"),
            f"{p}undo - hủy ván vừa ghi",
            f"{p}xoa 3 - xóa ván số 3 (nhiều ván: {p}xoa 3 5 7)",
            f"{p}khoiphuc 3 - lấy lại ván đã xóa",
            f"{p}sua 3 -5, 5, c, 6 - nhập lại ván số 3",
            "",
            b("Xem"),
            f"{p}tong - điểm lũy kế bàn đang chơi",
            f"{p}lichsu 10 - 10 ván gần nhất",
            "",
            b("Bàn chơi"),
            f"{p}banmoi 3cay [ghi chú]  ·  {p}banmoi sam [ghi chú]  ·  {p}ketthuc",
            "",
            b("Trang web"),
            f"{p}web - link xem bàn đang chơi trên điện thoại",
            f"{p}web doilink - đổi link nếu bị lộ ra ngoài nhóm",
            "",
            b("Google Sheet"),
            f"{p}sheet [link] - lưu link sheet cho nhóm này",
            f"{p}export - ghi bàn đang chơi lên sheet",
            "",
            f"💡 Đang xem hướng dẫn chơi 3 cây. Gõ {p}help sam để xem hướng dẫn Sâm.",
        ]
    )


class Engine:
    def __init__(
        self,
        db: Database,
        exporter: SheetExporter,
        default_sheet_url: str | None = None,
        allowed_chats: dict[str, frozenset[str]] | None = None,
        web_public_url: str | None = None,
    ):
        self.db = db
        self.exporter = exporter
        self.default_sheet_url = default_sheet_url
        self.allowed_chats = allowed_chats or {}
        self.web_public_url = web_public_url

    async def handle(self, msg: Incoming, fmt) -> list[str]:
        matched = _COMMAND.match(msg.text or "")
        name = matched.group("name").lower() if matched else None

        blocked = self._reject_reason(msg)
        if blocked:
            # Im lang voi chat thuong, chi tra loi khi user thuc su go lenh.
            return [blocked] if name else []

        key = chat_key(msg.platform, msg.native_chat_id)
        self.db.ensure_chat(key, msg.platform, msg.native_chat_id, msg.chat_title)
        ctx = Ctx(
            db=self.db,
            fmt=fmt,
            key=key,
            arg=matched.group("arg").strip() if matched else (msg.text or "").strip(),
            author=msg.author,
        )

        if name is None:
            roster = self.db.get_roster(key)
            if roster and looks_like_round(ctx.arg, roster):
                return await self._record(ctx, ctx.arg)
            return []

        handler = HANDLERS.get(name)
        if handler is None:
            return [
                f"Không có lệnh {ctx.plain_cmd(name)}. Gõ {ctx.plain_cmd('help')} để xem "
                "danh sách lệnh."
            ]
        return await handler(self, ctx)

    # None = duoc phep. Rong nghia la cho phep moi chat cua nen tang do.
    def _reject_reason(self, msg: Incoming) -> str | None:
        allowed = self.allowed_chats.get(msg.platform) or frozenset()
        if not allowed or str(msg.native_chat_id) in allowed:
            return None
        env = "TELEGRAM_CHAT_ID" if msg.platform == "telegram" else "ZALO_CHAT_ID"
        return (
            "⛔ Bot chưa được phép hoạt động trong chat này.\n"
            f"chat_id của chat này là: {msg.native_chat_id}\n"
            f"Thêm ID này vào {env} trong .env (cách nhau bằng dấu phẩy) rồi khởi động lại bot. "
            f"Để trống {env} = cho phép mọi chat."
        )

    # --- NGUOI CHOI ---

    async def cmd_start(self, ctx: Ctx) -> list[str]:
        game_type = "3cay"
        if ctx.arg:
            low = normalize(ctx.arg)
            if "sam" in low:
                game_type = "sam"
            elif "3cay" in low or "3 cay" in low or "ba cay" in low or "3c" in low:
                game_type = "3cay"
        else:
            session = self.db.active_session(ctx.key) or self.db.latest_session(ctx.key)
            if session:
                game_type = session.game_type
        return [help_text(ctx, game_type=game_type)]

    def _current_game_type(self, key: str) -> str:
        session = self.db.active_session(key) or self.db.latest_session(key)
        return session.game_type if session else "3cay"

    async def cmd_nguoichoi(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            return [render.roster(ctx.fmt, self.db.get_roster(ctx.key), game_type=self._current_game_type(ctx.key))]

        names = [n.strip() for n in ctx.arg.split(",") if n.strip()]
        if len(names) < 2:
            return ["Cần ít nhất 2 người chơi, cách nhau bằng dấu phẩy."]
        if len({n.lower() for n in names}) != len(names):
            return ["Có tên bị trùng. Mỗi người một tên khác nhau nhé."]

        seats = self.db.set_roster(ctx.key, names)
        note = "\n⚠️ Bàn đang chơi đã cập nhật theo thứ tự mới." if self._sync_seats(ctx.key) else ""
        return [render.roster(ctx.fmt, seats, game_type=self._current_game_type(ctx.key)) + note]

    async def cmd_dsnguoi(self, ctx: Ctx) -> list[str]:
        return [render.roster(ctx.fmt, self.db.get_roster(ctx.key), game_type=self._current_game_type(ctx.key))]

    async def cmd_themnguoi(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            return [f"Dùng: {ctx.plain_cmd('themnguoi')} Nam"]
        self.db.add_player(ctx.key, ctx.arg)
        active = self._sync_seats(ctx.key)
        seats = self.db.get_roster(ctx.key)
        note = (
            f"\n⚠️ Bàn đang chơi giờ có {len(seats)} chỗ, các ván sau nhập {len(seats)} ô."
            if active
            else ""
        )
        return [render.roster(ctx.fmt, seats, game_type=self._current_game_type(ctx.key)) + note]

    async def cmd_xoanguoi(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            return [f"Dùng: {ctx.plain_cmd('xoanguoi')} Nam"]
        removed = self.db.deactivate_player(ctx.key, ctx.arg)
        if removed is None:
            return [
                f"Không tìm thấy người chơi '{ctx.fmt.esc(ctx.arg)}'. "
                f"Xem {ctx.plain_cmd('dsnguoi')}"
            ]
        active = self._sync_seats(ctx.key)
        seats = self.db.get_roster(ctx.key)
        note = f"\n⚠️ Bàn đang chơi giờ có {len(seats)} chỗ." if active else ""
        return [
            f"Đã bỏ {ctx.fmt.b(removed.name)} khỏi danh sách.\n\n"
            + render.roster(ctx.fmt, seats, game_type=self._current_game_type(ctx.key))
            + note
        ]

    # Roster la nguon su that; ban dang choi phai khop lai khi roster doi giua buoi.
    def _sync_seats(self, key: str) -> Session | None:
        session = self.db.active_session(key)
        if session is None:
            return None
        self.db.set_session_seats(session.id, [p.id for p in self.db.get_roster(key)])
        return self.db.active_session(key)

    # --- BAN CHOI ---

    async def cmd_banmoi(self, ctx: Ctx) -> list[str]:
        seats = self.db.get_roster(ctx.key)
        if len(seats) < 2:
            return [self._need_roster(ctx)]
        if self.db.active_session(ctx.key) is not None:
            return [f"Đang có bàn chưa chốt. Gõ {ctx.plain_cmd('ketthuc')} để chốt bàn cũ trước."]

        arg = ctx.arg.strip()
        game_type, note = self._parse_game_type_and_note(arg)
        if game_type is None:
            note_hint = f" \"{ctx.fmt.esc(arg)}\"" if arg else ""
            p = ctx.plain_cmd("banmoi")
            return [
                f"🎴 Bạn muốn mở bàn{note_hint} chơi {ctx.fmt.b('3 cây')} hay {ctx.fmt.b('Sâm')}?\n\n"
                f"• Chơi 3 cây: {ctx.fmt.code(f'{p} 3cay' + (f' {arg}' if arg else ''))} (hoặc {ctx.fmt.code(ctx.plain_cmd('3cay'))})\n"
                f"• Chơi Sâm: {ctx.fmt.code(f'{p} sam' + (f' {arg}' if arg else ''))} (hoặc {ctx.fmt.code(ctx.plain_cmd('sam'))})"
            ]

        session = self.db.open_session(ctx.key, [p.id for p in seats], note, game_type=game_type)
        game_name = "Sâm" if game_type == "sam" else "3 cây"
        note_str = f"\nGhi chú: {ctx.fmt.esc(session.note)}" if session.note else ""
        return [
            f"🎴 {ctx.fmt.b(f'Đã mở bàn mới ({game_name})')}{note_str}\n\n"
            + render.roster(ctx.fmt, seats, game_type=game_type)
        ]

    async def cmd_3cay(self, ctx: Ctx) -> list[str]:
        seats = self.db.get_roster(ctx.key)
        if len(seats) < 2:
            return [self._need_roster(ctx)]
        if self.db.active_session(ctx.key) is not None:
            return [f"Đang có bàn chưa chốt. Gõ {ctx.plain_cmd('ketthuc')} để chốt bàn cũ trước."]
        session = self.db.open_session(ctx.key, [p.id for p in seats], ctx.arg or None, game_type="3cay")
        note_str = f"\nGhi chú: {ctx.fmt.esc(session.note)}" if session.note else ""
        return [
            f"🎴 {ctx.fmt.b('Đã mở bàn mới (3 cây)')}{note_str}\n\n"
            + render.roster(ctx.fmt, seats, game_type="3cay")
        ]

    async def cmd_sam(self, ctx: Ctx) -> list[str]:
        seats = self.db.get_roster(ctx.key)
        if len(seats) < 2:
            return [self._need_roster(ctx)]
        if self.db.active_session(ctx.key) is not None:
            return [f"Đang có bàn chưa chốt. Gõ {ctx.plain_cmd('ketthuc')} để chốt bàn cũ trước."]
        session = self.db.open_session(ctx.key, [p.id for p in seats], ctx.arg or None, game_type="sam")
        note_str = f"\nGhi chú: {ctx.fmt.esc(session.note)}" if session.note else ""
        return [
            f"🎴 {ctx.fmt.b('Đã mở bàn mới (Sâm)')}{note_str}\n\n"
            + render.roster(ctx.fmt, seats, game_type="sam")
        ]

    def _parse_game_type_and_note(self, text: str) -> tuple[str | None, str | None]:
        if not text:
            return None, None
        low = normalize(text)
        words = low.split()
        first = words[0]
        if first in ("sam", "samloc"):
            note = text[len(text.split()[0]):].strip()
            return "sam", (note or None)
        if first in ("3cay", "3c", "bacay", "3-cay"):
            note = text[len(text.split()[0]):].strip()
            return "3cay", (note or None)
        if len(words) >= 2 and f"{words[0]} {words[1]}" in ("3 cay", "ba cay", "sam loc"):
            match_len = len(text.split()[0]) + 1 + len(text.split()[1])
            gtype = "sam" if "sam" in words[0] else "3cay"
            note = text[match_len:].strip()
            return gtype, (note or None)
        return "3cay", (text or None)

    async def cmd_ketthuc(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở."]

        rounds = self.db.get_rounds(session.id)
        totals = self.db.session_totals(session.id)
        self.db.close_session(session.id)
        body = render.standings(
            ctx.fmt, self._seats(session), totals, len(rounds), title="KẾT QUẢ CUỐI BÀN", game_type=session.game_type
        )
        game_name = "Sâm" if session.game_type == "sam" else "3 cây"
        return [f"🏁 {ctx.fmt.b(f'Đã chốt bàn ({game_name})')}\n\n{body}"]

    # --- GHI VAN ---

    async def cmd_v(self, ctx: Ctx) -> list[str]:
        return await self._record(ctx, ctx.arg)

    async def _record(self, ctx: Ctx, text: str) -> list[str]:
        roster = self.db.get_roster(ctx.key)
        if len(roster) < 2:
            return [self._need_roster(ctx)]

        prefix = ""
        session = self.db.active_session(ctx.key)
        if session is None:
            latest = self.db.latest_session(ctx.key)
            game_type = latest.game_type if latest else "3cay"
            session = self.db.open_session(ctx.key, [p.id for p in roster], game_type=game_type)
            game_name = "Sâm" if game_type == "sam" else "3 cây"
            other_name = "sam" if game_type == "3cay" else "3cay"
            prefix = (
                f"🎴 Chưa có bàn nào mở nên tôi tự mở bàn mới ({game_name}). "
                f"(Đổi trò: {ctx.plain_cmd('banmoi')} {other_name})\n\n"
            )

        seats = self._seats(session)
        try:
            parsed = parse_round(text, seats, game_type=session.game_type)
            scores = resolve_scores(parsed, game_type=session.game_type)
        except (ParseError, ScoringError) as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]

        rnd = self.db.add_round(session.id, parsed.banker_id, scores, text, ctx.author)
        return [prefix + self._round_message(ctx, session, rnd)]

    async def cmd_sua(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở."]

        matched = re.match(r"^(\d+)\s+(.+)$", ctx.arg, re.S)
        if not matched:
            return [
                f"Dùng: {ctx.fmt.code(ctx.plain_cmd('sua') + ' 3 -5, 5, , 6')}  "
                "(3 là số ván cần sửa)"
            ]

        seq, text = int(matched.group(1)), matched.group(2).strip()
        seats = self._seats(session)
        try:
            parsed = parse_round(text, seats, game_type=session.game_type)
            scores = resolve_scores(parsed, game_type=session.game_type)
        except (ParseError, ScoringError) as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]

        rnd = self.db.replace_round(session.id, seq, parsed.banker_id, scores, text)
        if rnd is None:
            return [f"Không tìm thấy ván {seq} trong bàn này (có thể đã bị xóa)."]
        return [self._round_message(ctx, session, rnd, edited=True)]

    def _round_message(self, ctx: Ctx, session: Session, rnd: Round, edited: bool = False) -> str:
        return render.round_saved(
            ctx.fmt,
            rnd,
            self._seats(session),
            self.db.session_totals(session.id),
            len(self.db.get_rounds(session.id)),
            edited=edited,
        )

    # --- XOA / KHOI PHUC ---

    async def cmd_undo(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở."]
        rnd = self.db.void_last_round(session.id)
        if rnd is None:
            return ["Bàn chưa có ván nào để hủy."]
        return [self._deleted_message(ctx, session, [rnd.seq])]

    async def cmd_xoa(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở."]

        seqs = [int(t) for t in re.findall(r"\d+", ctx.arg)]
        if not seqs:
            return [
                f"Dùng: {ctx.fmt.code(ctx.plain_cmd('xoa') + ' 3')} hoặc "
                f"{ctx.fmt.code(ctx.plain_cmd('xoa') + ' 3 5 7')}. "
                f"Xem số ván bằng {ctx.plain_cmd('lichsu')}"
            ]

        done = [s for s in sorted(set(seqs)) if self.db.void_round(session.id, s) is not None]
        missing = sorted(set(seqs) - set(done))
        if not done:
            return [f"Không tìm thấy ván {', '.join(map(str, missing))} trong bàn này."]
        note = f"\nKhông thấy ván: {', '.join(map(str, missing))}" if missing else ""
        return [self._deleted_message(ctx, session, done) + note]

    async def cmd_khoiphuc(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở."]

        seqs = [int(t) for t in re.findall(r"\d+", ctx.arg)]
        if not seqs:
            voided = self.db.voided_seqs(session.id)
            hint = ", ".join(map(str, voided)) if voided else "không có ván nào"
            return [
                f"Dùng: {ctx.fmt.code(ctx.plain_cmd('khoiphuc') + ' 3')}\n"
                f"Ván đang bị xóa: {hint}"
            ]

        done = [s for s in sorted(set(seqs)) if self.db.unvoid_round(session.id, s) is not None]
        if not done:
            return ["Không có ván nào khớp (chỉ khôi phục được ván đang bị xóa)."]
        body = render.standings(
            ctx.fmt,
            self._seats(session),
            self.db.session_totals(session.id),
            len(self.db.get_rounds(session.id)),
            game_type=session.game_type,
        )
        return [f"♻️ Đã khôi phục ván {', '.join(map(str, done))}\n\n{body}"]

    def _deleted_message(self, ctx: Ctx, session: Session, seqs: list[int]) -> str:
        played = len(self.db.get_rounds(session.id))
        body = (
            render.standings(
                ctx.fmt, self._seats(session), self.db.session_totals(session.id), played, game_type=session.game_type
            )
            if played
            else "Bàn không còn ván nào."
        )
        label = ", ".join(map(str, seqs))
        return (
            f"🗑 Đã xóa ván {label} "
            f"(lấy lại: {ctx.plain_cmd('khoiphuc')} {seqs[0]})\n\n{body}"
        )

    # --- XEM ---

    async def cmd_tong(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return [
                f"Không có bàn nào đang mở. Gõ {ctx.plain_cmd('banmoi')} hoặc ghi ván đầu tiên."
            ]
        return [
            render.standings(
                ctx.fmt,
                self._seats(session),
                self.db.session_totals(session.id),
                len(self.db.get_rounds(session.id)),
                game_type=session.game_type,
            )
        ]

    async def cmd_lichsu(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở."]
        limit = int(next(iter(re.findall(r"\d+", ctx.arg)), 15))
        rounds = self.db.get_rounds(session.id)
        return [
            render.history(
                ctx.fmt,
                rounds[-limit:],
                self._seats(session),
                self.db.voided_seqs(session.id),
                game_type=session.game_type,
            )
        ]

    # --- TRANG WEB ---

    async def cmd_web(self, ctx: Ctx) -> list[str]:
        if not self.web_public_url:
            return [
                "Chưa bật trang web. Đặt WEB_PUBLIC_URL trong .env "
                f"(ví dụ {ctx.fmt.code('https://sam.mihb.site')}) rồi khởi động lại bot."
            ]

        if ctx.arg.lower().replace(" ", "").startswith("doilink"):
            token = self.db.reset_web_token(ctx.key)
            head = "🔄 Đã đổi link. Link cũ không còn vào được."
        else:
            token = self.db.get_or_create_web_token(ctx.key)
            head = "📱 Xem bàn đang chơi trên điện thoại:"

        url = f"{self.web_public_url.rstrip('/')}/?k={token}"
        return [
            f"{head}\n{ctx.fmt.esc(url)}\n\n"
            "Link chỉ để xem, không sửa được điểm. Ai có link đều vào được nên đừng đưa ra "
            f"ngoài nhóm; lỡ lộ thì gõ {ctx.plain_cmd('web')} doilink."
        ]

    # --- GOOGLE SHEET ---

    async def cmd_sheet(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            current = self.db.get_sheet_url(ctx.key) or self.default_sheet_url or "chưa đặt"
            return [
                f"Sheet hiện tại: {ctx.fmt.esc(current)}\n\n"
                f"Đổi bằng: {ctx.fmt.code(ctx.plain_cmd('sheet') + ' [link]')}\n"
                f"Nhớ Share sheet cho: {ctx.fmt.code(self.exporter.service_account_email)} (Editor)"
            ]
        try:
            extract_key(ctx.arg)
        except SheetError as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]

        self.db.set_sheet_url(ctx.key, ctx.arg)
        return [
            "✅ Đã lưu link sheet cho nhóm này.\n"
            f"Nhớ Share sheet cho {ctx.fmt.code(self.exporter.service_account_email)} với quyền "
            f"{ctx.fmt.b('Editor')}, rồi gõ {ctx.plain_cmd('export')}."
        ]

    async def cmd_export(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Không có bàn nào đang mở nên chưa có gì để ghi."]

        rounds = self.db.get_rounds(session.id)
        if not rounds:
            return ["Bàn đang chơi chưa có ván nào."]

        url = ctx.arg or self.db.get_sheet_url(ctx.key) or self.default_sheet_url
        if not url:
            return [
                f"Chưa có link sheet. Đặt bằng: "
                f"{ctx.fmt.code(ctx.plain_cmd('sheet') + ' [link]')}"
            ]

        seats = self._seats(session)
        table = build_table(seats, rounds, self.db.session_totals(session.id), game_type=session.game_type)
        try:
            link = await asyncio.to_thread(self.exporter.export, url, *table)
        except SheetError as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]
        except Exception as exc:
            return [f"❌ Lỗi không mong đợi khi ghi sheet: {ctx.fmt.esc(exc)}"]

        if ctx.arg:
            self.db.set_sheet_url(ctx.key, url)
        return [f"✅ Đã ghi {ctx.fmt.b(f'{len(rounds)} ván')} lên sheet.\n{link}"]

    # --- HELPER ---

    def _seats(self, session: Session) -> list[Player]:
        players = self.db.get_players_by_ids(session.seat_ids)
        return [players[pid] for pid in session.seat_ids if pid in players]

    def _need_roster(self, ctx: Ctx) -> str:
        return "Khai báo người chơi trước:\n" + ctx.fmt.code(
            f"{ctx.fmt.prefix}nguoichoi Hương, Hằng, Toàn, Thu"
        )


HANDLERS = {
    "start": Engine.cmd_start,
    "help": Engine.cmd_start,
    "huongdan": Engine.cmd_start,
    "nguoichoi": Engine.cmd_nguoichoi,
    "dsnguoi": Engine.cmd_dsnguoi,
    "themnguoi": Engine.cmd_themnguoi,
    "xoanguoi": Engine.cmd_xoanguoi,
    "banmoi": Engine.cmd_banmoi,
    "3cay": Engine.cmd_3cay,
    "sam": Engine.cmd_sam,
    "ketthuc": Engine.cmd_ketthuc,
    "v": Engine.cmd_v,
    "van": Engine.cmd_v,
    "sua": Engine.cmd_sua,
    "undo": Engine.cmd_undo,
    "xoa": Engine.cmd_xoa,
    "khoiphuc": Engine.cmd_khoiphuc,
    "tong": Engine.cmd_tong,
    "bang": Engine.cmd_tong,
    "lichsu": Engine.cmd_lichsu,
    "web": Engine.cmd_web,
    "link": Engine.cmd_web,
    "sheet": Engine.cmd_sheet,
    "export": Engine.cmd_export,
}
