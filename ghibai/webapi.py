"""API JSON cho trang web xem ban dang choi. Chi doc, khong sua gi trong DB.

Xac thuc bang token nam trong link (?k=...), moi chat mot token rieng, sinh boi lenh
/web. Khong co token hop le thi tra 404 chu khong 401: nguoi la khong can biet co ton
tai ban nao hay khong.

Tra ve dung 1 payload cho ca man hinh de trang web chi phai goi 1 request khi refresh.
"""

import hmac
from datetime import datetime, timezone

from aiohttp import web

from . import stats
from .db import Database, Player, Round, Session

TOKEN_QUERY = "k"


class WebApi:
    def __init__(self, db: Database, admin_token: str | None = None):
        self.db = db
        self.admin_token = admin_token

    # Luon tra du moi key (mang rong khi chua co ban) de trang web khong phai doan kieu.
    async def board(self, request: web.Request) -> web.Response:
        chat = self._authenticate(request)
        session = self.db.latest_session(chat["chat_key"])
        seats = self._seats(session) if session else []
        rounds = self.db.get_rounds(session.id) if session else []
        totals = self.db.session_totals(session.id) if session else {}

        return web.json_response(
            {
                "chat": _chat_payload(chat),
                "session": _session_payload(session, len(rounds)) if session else None,
                "players": [{"id": p.id, "name": p.name, "seat": p.seat} for p in seats],
                "standings": _standings(seats, rounds, totals),
                "rounds": [_round_payload(r) for r in rounds],
                "voidedSeqs": self.db.voided_seqs(session.id) if session else [],
                # Tong 1 van luon = 0 nen tong ca ban cung phai = 0; khac 0 la co van loi.
                "checksum": sum(totals.values()),
                "fetchedAt": _now(),
            }
        )

    # Cung 1 payload voi lenh /thongke (xem stats.overview) de hai cho khong lech so.
    async def stats(self, request: web.Request) -> web.Response:
        supplied = (request.query.get(TOKEN_QUERY) or "").strip()
        # Chua dat ADMIN_STATS_TOKEN = tat han endpoint. Tra 404 chu khong 401, giong
        # /api/board: nguoi la khong can biet endpoint nay co ton tai hay khong.
        if not self.admin_token or not hmac.compare_digest(supplied, self.admin_token):
            raise web.HTTPNotFound(
                text='{"error": "Không tìm thấy."}', content_type="application/json"
            )
        return web.json_response(stats.overview(self.db))

    def _authenticate(self, request: web.Request) -> dict:
        token = (request.query.get(TOKEN_QUERY) or "").strip()
        chat = self.db.chat_by_web_token(token) if token else None
        if chat is None:
            raise web.HTTPNotFound(
                text='{"error": "Link không đúng hoặc đã bị đổi. Gõ /web trong nhóm chat để lấy link mới."}',
                content_type="application/json",
            )
        return chat

    # Ghe ngoi la nguon su that cua ban; nguoi bi xoa khoi roster giua buoi van con trong seats.
    def _seats(self, session: Session) -> list[Player]:
        players = self.db.get_players_by_ids(session.seat_ids)
        return [players[pid] for pid in session.seat_ids if pid in players]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _chat_payload(chat: dict) -> dict:
    return {"title": chat["title"], "platform": chat["platform"]}


def _session_payload(session: Session, played: int) -> dict:
    return {
        "id": session.id,
        "gameType": getattr(session, "game_type", "3cay") or "3cay",
        "note": session.note,
        "startedAt": session.started_at,
        "endedAt": session.ended_at,
        "live": session.ended_at is None,
        "played": played,
    }


def _round_payload(rnd: Round) -> dict:
    return {
        "seq": rnd.seq,
        "at": rnd.created_at,
        "bankerId": rnd.banker_id,
        # Nguoi bo van khong co key o day, khac han voi diem 0.
        "scores": {str(pid): score for pid, score in rnd.scores.items()},
    }


def _standings(seats: list[Player], rounds: list[Round], totals: dict[int, int]) -> list[dict]:
    played = {p.id: 0 for p in seats}
    banked = {p.id: 0 for p in seats}
    for rnd in rounds:
        for pid in rnd.scores:
            if pid in played:
                played[pid] += 1
        if rnd.banker_id in banked:
            banked[rnd.banker_id] += 1

    ranked = sorted(
        (p for p in seats if p.id in totals), key=lambda p: totals[p.id], reverse=True
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "total": totals[p.id],
            "played": played[p.id],
            "banked": banked[p.id],
        }
        for p in ranked
    ]
