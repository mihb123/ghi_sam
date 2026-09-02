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

_COMMAND = re.compile(r"^\s*[/#](?P<name>[A-Za-z_]+)(?:@\S+)?\s*(?P<arg>.*)$", re.S)


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


def help_text(ctx: Ctx) -> str:
    p = ctx.fmt.prefix
    b = ctx.fmt.b
    return "\n".join(
        [
            b("Bot ghi diem 3 cay"),
            "",
            b("Nguoi choi"),
            f"{p}nguoichoi Huong, Hang, Toan, Thu - khai bao (thu tu = thu tu nhap diem)",
            f"{p}dsnguoi - xem danh sach va thu tu cho",
            f"{p}themnguoi Nam  ·  {p}xoanguoi Nam",
            "",
            b("Ghi van"),
            "Go tran theo thu tu cho, o trong = nguoi cam chuong:",
            ctx.fmt.code("-5, 5, , 6"),
            "Hoac ghi ro ten: " + ctx.fmt.code("Huong -5, Hang 5, Toan, Thu 6"),
            f"Them {p}v phia truoc neu muon chac chan: " + ctx.fmt.code(f"{p}v -5, 5, , 6"),
            "Dung " + ctx.fmt.code("x") + " cho nguoi bo van: " + ctx.fmt.code("-5, 5, , x"),
            "",
            b("Sua / xoa khi nhap sai"),
            f"{p}undo - huy van vua ghi",
            f"{p}xoa 3 - xoa van so 3 (nhieu van: {p}xoa 3 5 7)",
            f"{p}khoiphuc 3 - lay lai van da xoa",
            f"{p}sua 3 -5, 5, , 6 - nhap lai van so 3",
            f"{p}xoaban xacnhan - xoa sach ban dang choi",
            "",
            b("Xem"),
            f"{p}bang - diem luy ke ban dang choi",
            f"{p}lichsu 10 - 10 van gan nhat",
            f"{p}xh - xep hang tich luy moi ban",
            "",
            b("Ban choi"),
            f"{p}banmoi [ghi chu]  ·  {p}ketthuc",
            "",
            b("Trang web"),
            f"{p}web - link xem ban dang choi tren dien thoai",
            f"{p}web doilink - doi link neu bi lo ra ngoai nhom",
            "",
            b("Google Sheet"),
            f"{p}sheet [link] - luu link sheet cho nhom nay",
            f"{p}export - ghi ban dang choi len sheet",
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
                f"Khong co lenh {ctx.plain_cmd(name)}. Go {ctx.plain_cmd('help')} de xem "
                "danh sach lenh."
            ]
        return await handler(self, ctx)

    # None = duoc phep. Rong nghia la cho phep moi chat cua nen tang do.
    def _reject_reason(self, msg: Incoming) -> str | None:
        allowed = self.allowed_chats.get(msg.platform) or frozenset()
        if not allowed or str(msg.native_chat_id) in allowed:
            return None
        env = "TELEGRAM_CHAT_ID" if msg.platform == "telegram" else "ZALO_CHAT_ID"
        return (
            "⛔ Bot chua duoc phep hoat dong trong chat nay.\n"
            f"chat_id cua chat nay la: {msg.native_chat_id}\n"
            f"Them ID nay vao {env} trong .env (cach nhau bang dau phay) roi khoi dong lai bot. "
            f"De trong {env} = cho phep moi chat."
        )

    # --- NGUOI CHOI ---

    async def cmd_start(self, ctx: Ctx) -> list[str]:
        return [help_text(ctx)]

    async def cmd_nguoichoi(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            return [render.roster(ctx.fmt, self.db.get_roster(ctx.key))]

        names = [n.strip() for n in ctx.arg.split(",") if n.strip()]
        if len(names) < 2:
            return ["Can it nhat 2 nguoi choi, cach nhau bang dau phay."]
        if len({n.lower() for n in names}) != len(names):
            return ["Co ten bi trung. Moi nguoi mot ten khac nhau nhe."]

        seats = self.db.set_roster(ctx.key, names)
        note = "\n⚠️ Ban dang choi da cap nhat theo thu tu moi." if self._sync_seats(ctx.key) else ""
        return [render.roster(ctx.fmt, seats) + note]

    async def cmd_dsnguoi(self, ctx: Ctx) -> list[str]:
        return [render.roster(ctx.fmt, self.db.get_roster(ctx.key))]

    async def cmd_themnguoi(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            return [f"Dung: {ctx.plain_cmd('themnguoi')} Nam"]
        self.db.add_player(ctx.key, ctx.arg)
        active = self._sync_seats(ctx.key)
        seats = self.db.get_roster(ctx.key)
        note = (
            f"\n⚠️ Ban dang choi gio co {len(seats)} cho, cac van sau nhap {len(seats)} o."
            if active
            else ""
        )
        return [render.roster(ctx.fmt, seats) + note]

    async def cmd_xoanguoi(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            return [f"Dung: {ctx.plain_cmd('xoanguoi')} Nam"]
        removed = self.db.deactivate_player(ctx.key, ctx.arg)
        if removed is None:
            return [
                f"Khong tim thay nguoi choi '{ctx.fmt.esc(ctx.arg)}'. "
                f"Xem {ctx.plain_cmd('dsnguoi')}"
            ]
        active = self._sync_seats(ctx.key)
        seats = self.db.get_roster(ctx.key)
        note = f"\n⚠️ Ban dang choi gio co {len(seats)} cho." if active else ""
        return [
            f"Da bo {ctx.fmt.b(removed.name)} khoi danh sach.\n\n"
            + render.roster(ctx.fmt, seats)
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
            return [f"Dang co ban chua chot. Go {ctx.plain_cmd('ketthuc')} de chot ban cu truoc."]

        session = self.db.open_session(ctx.key, [p.id for p in seats], ctx.arg or None)
        note = f"\nGhi chu: {ctx.fmt.esc(session.note)}" if session.note else ""
        return [f"🎴 {ctx.fmt.b('Da mo ban moi')}{note}\n\n" + render.roster(ctx.fmt, seats)]

    async def cmd_ketthuc(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo."]

        rounds = self.db.get_rounds(session.id)
        totals = self.db.session_totals(session.id)
        self.db.close_session(session.id)
        body = render.standings(
            ctx.fmt, self._seats(session), totals, len(rounds), title="KET QUA CUOI BAN"
        )
        return [f"🏁 {ctx.fmt.b('Da chot ban')}\n\n{body}"]

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
            session = self.db.open_session(ctx.key, [p.id for p in roster])
            prefix = "🎴 Chua co ban nao mo nen toi tu mo ban moi.\n\n"

        seats = self._seats(session)
        try:
            parsed = parse_round(text, seats)
            scores = resolve_scores(parsed)
        except (ParseError, ScoringError) as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]

        rnd = self.db.add_round(session.id, parsed.banker_id, scores, text, ctx.author)
        return [prefix + self._round_message(ctx, session, rnd)]

    async def cmd_sua(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo."]

        matched = re.match(r"^(\d+)\s+(.+)$", ctx.arg, re.S)
        if not matched:
            return [
                f"Dung: {ctx.fmt.code(ctx.plain_cmd('sua') + ' 3 -5, 5, , 6')}  "
                "(3 la so van can sua)"
            ]

        seq, text = int(matched.group(1)), matched.group(2).strip()
        seats = self._seats(session)
        try:
            parsed = parse_round(text, seats)
            scores = resolve_scores(parsed)
        except (ParseError, ScoringError) as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]

        rnd = self.db.replace_round(session.id, seq, parsed.banker_id, scores, text)
        if rnd is None:
            return [f"Khong tim thay van {seq} trong ban nay (co the da bi xoa)."]
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
            return ["Khong co ban nao dang mo."]
        rnd = self.db.void_last_round(session.id)
        if rnd is None:
            return ["Ban chua co van nao de huy."]
        return [self._deleted_message(ctx, session, [rnd.seq])]

    async def cmd_xoa(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo."]

        seqs = [int(t) for t in re.findall(r"\d+", ctx.arg)]
        if not seqs:
            return [
                f"Dung: {ctx.fmt.code(ctx.plain_cmd('xoa') + ' 3')} hoac "
                f"{ctx.fmt.code(ctx.plain_cmd('xoa') + ' 3 5 7')}. "
                f"Xem so van bang {ctx.plain_cmd('lichsu')}"
            ]

        done = [s for s in sorted(set(seqs)) if self.db.void_round(session.id, s) is not None]
        missing = sorted(set(seqs) - set(done))
        if not done:
            return [f"Khong tim thay van {', '.join(map(str, missing))} trong ban nay."]
        note = f"\nKhong thay van: {', '.join(map(str, missing))}" if missing else ""
        return [self._deleted_message(ctx, session, done) + note]

    async def cmd_khoiphuc(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo."]

        seqs = [int(t) for t in re.findall(r"\d+", ctx.arg)]
        if not seqs:
            voided = self.db.voided_seqs(session.id)
            hint = ", ".join(map(str, voided)) if voided else "khong co van nao"
            return [
                f"Dung: {ctx.fmt.code(ctx.plain_cmd('khoiphuc') + ' 3')}\n"
                f"Van dang bi xoa: {hint}"
            ]

        done = [s for s in sorted(set(seqs)) if self.db.unvoid_round(session.id, s) is not None]
        if not done:
            return ["Khong co van nao khop (chi khoi phuc duoc van dang bi xoa)."]
        body = render.standings(
            ctx.fmt,
            self._seats(session),
            self.db.session_totals(session.id),
            len(self.db.get_rounds(session.id)),
        )
        return [f"♻️ Da khoi phuc van {', '.join(map(str, done))}\n\n{body}"]

    async def cmd_xoaban(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo."]

        played = len(self.db.get_rounds(session.id))
        if "xacnhan" not in ctx.arg.lower():
            return [
                f"⚠️ Se xoa toan bo {ctx.fmt.b(f'{played} van')} cua ban dang choi.\n"
                f"Go {ctx.fmt.code(ctx.plain_cmd('xoaban') + ' xacnhan')} neu chac chan.\n"
                f"(Van chi bi an, con lay lai duoc bang {ctx.plain_cmd('khoiphuc')} [so van])"
            ]

        count = self.db.void_all_rounds(session.id)
        return [
            f"🗑 Da xoa {count} van. Lay lai tung van bang "
            f"{ctx.plain_cmd('khoiphuc')} [so van]"
        ]

    def _deleted_message(self, ctx: Ctx, session: Session, seqs: list[int]) -> str:
        played = len(self.db.get_rounds(session.id))
        body = (
            render.standings(ctx.fmt, self._seats(session), self.db.session_totals(session.id), played)
            if played
            else "Ban khong con van nao."
        )
        label = ", ".join(map(str, seqs))
        return (
            f"🗑 Da xoa van {label} "
            f"(lay lai: {ctx.plain_cmd('khoiphuc')} {seqs[0]})\n\n{body}"
        )

    # --- XEM ---

    async def cmd_bang(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return [
                f"Khong co ban nao dang mo. Go {ctx.plain_cmd('banmoi')} hoac ghi van dau tien."
            ]
        return [
            render.standings(
                ctx.fmt,
                self._seats(session),
                self.db.session_totals(session.id),
                len(self.db.get_rounds(session.id)),
            )
        ]

    async def cmd_lichsu(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo."]
        limit = int(next(iter(re.findall(r"\d+", ctx.arg)), 15))
        rounds = self.db.get_rounds(session.id)
        return [
            render.history(
                ctx.fmt, rounds[-limit:], self._seats(session), self.db.voided_seqs(session.id)
            )
        ]

    async def cmd_xh(self, ctx: Ctx) -> list[str]:
        return [render.lifetime(ctx.fmt, self.db.lifetime_stats(ctx.key))]

    # --- TRANG WEB ---

    async def cmd_web(self, ctx: Ctx) -> list[str]:
        if not self.web_public_url:
            return [
                "Chua bat trang web. Dat WEB_PUBLIC_URL trong .env "
                f"(vi du {ctx.fmt.code('https://sam.mihb.site')}) roi khoi dong lai bot."
            ]

        if ctx.arg.lower().replace(" ", "").startswith("doilink"):
            token = self.db.reset_web_token(ctx.key)
            head = "🔄 Da doi link. Link cu khong con vao duoc."
        else:
            token = self.db.get_or_create_web_token(ctx.key)
            head = "📱 Xem ban dang choi tren dien thoai:"

        url = f"{self.web_public_url.rstrip('/')}/?k={token}"
        return [
            f"{head}\n{ctx.fmt.esc(url)}\n\n"
            "Link chi de xem, khong sua duoc diem. Ai co link deu vao duoc nen dung dua ra "
            f"ngoai nhom; lo lot thi go {ctx.plain_cmd('web')} doilink."
        ]

    # --- GOOGLE SHEET ---

    async def cmd_sheet(self, ctx: Ctx) -> list[str]:
        if not ctx.arg:
            current = self.db.get_sheet_url(ctx.key) or self.default_sheet_url or "chua dat"
            return [
                f"Sheet hien tai: {ctx.fmt.esc(current)}\n\n"
                f"Doi bang: {ctx.fmt.code(ctx.plain_cmd('sheet') + ' [link]')}\n"
                f"Nho Share sheet cho: {ctx.fmt.code(self.exporter.service_account_email)} (Editor)"
            ]
        try:
            extract_key(ctx.arg)
        except SheetError as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]

        self.db.set_sheet_url(ctx.key, ctx.arg)
        return [
            "✅ Da luu link sheet cho nhom nay.\n"
            f"Nho Share sheet cho {ctx.fmt.code(self.exporter.service_account_email)} voi quyen "
            f"{ctx.fmt.b('Editor')}, roi go {ctx.plain_cmd('export')}."
        ]

    async def cmd_export(self, ctx: Ctx) -> list[str]:
        session = self.db.active_session(ctx.key)
        if session is None:
            return ["Khong co ban nao dang mo nen chua co gi de ghi."]

        rounds = self.db.get_rounds(session.id)
        if not rounds:
            return ["Ban dang choi chua co van nao."]

        url = ctx.arg or self.db.get_sheet_url(ctx.key) or self.default_sheet_url
        if not url:
            return [
                f"Chua co link sheet. Dat bang: "
                f"{ctx.fmt.code(ctx.plain_cmd('sheet') + ' [link]')}"
            ]

        seats = self._seats(session)
        table = build_table(seats, rounds, self.db.session_totals(session.id))
        try:
            link = await asyncio.to_thread(self.exporter.export, url, *table)
        except SheetError as exc:
            return [f"❌ {ctx.fmt.esc(exc)}"]
        except Exception as exc:
            return [f"❌ Loi khong mong doi khi ghi sheet: {ctx.fmt.esc(exc)}"]

        if ctx.arg:
            self.db.set_sheet_url(ctx.key, url)
        return [f"✅ Da ghi {ctx.fmt.b(f'{len(rounds)} van')} len sheet.\n{link}"]

    # --- HELPER ---

    def _seats(self, session: Session) -> list[Player]:
        players = self.db.get_players_by_ids(session.seat_ids)
        return [players[pid] for pid in session.seat_ids if pid in players]

    def _need_roster(self, ctx: Ctx) -> str:
        return "Khai bao nguoi choi truoc:\n" + ctx.fmt.code(
            f"{ctx.fmt.prefix}nguoichoi Huong, Hang, Toan, Thu"
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
    "ketthuc": Engine.cmd_ketthuc,
    "v": Engine.cmd_v,
    "van": Engine.cmd_v,
    "sua": Engine.cmd_sua,
    "undo": Engine.cmd_undo,
    "xoa": Engine.cmd_xoa,
    "khoiphuc": Engine.cmd_khoiphuc,
    "xoaban": Engine.cmd_xoaban,
    "bang": Engine.cmd_bang,
    "lichsu": Engine.cmd_lichsu,
    "xh": Engine.cmd_xh,
    "web": Engine.cmd_web,
    "link": Engine.cmd_web,
    "sheet": Engine.cmd_sheet,
    "export": Engine.cmd_export,
}
