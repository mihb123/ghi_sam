"""Dinh danh nguoi dung va gan nguon gioi thieu, khong hoi nguoi dung mot cau nao.

Nguoi share go /chiase -> bot tra dung 1 link chua ma rieng cua ho. Nguoi moi bam link
roi dung bot binh thuong; bot tu suy ra nguon theo 3 luat, uu tien tu tren xuong:

  1. link    (exact)    /start r_AB12CD  - deep link Telegram, chinh xac tuyet doi.
  2. group   (inferred) nguoi moi nhan lan dau trong chat da co nguoi dung bot truoc
                        -> quy ve nguoi som nhat cua chat do (thuc te la nguoi da mang
                        bot vao nhom, vi ho luon la nguoi go lenh dau tien).
  3. landing (inferred) Zalo khong co deep link kem tham so, nen link chia se cua nguoi
                        dung Zalo tro ve trang /i/<ma>; ghi log click roi ghep voi user
                        moi xuat hien trong cua so thoi gian. Chi ghep khi trong cua so
                        do co dung 1 ma - nhieu hon la nhap nhang, tha bo hon doan bua.

Luat 2 va 3 chi chay cho nguoi hoan toan moi. Luat 1 chay ca voi nguoi cu de nang cap
mot ban ghi tu inferred len exact khi ho bam link that.
"""

import hashlib
import logging
import re
from dataclasses import dataclass

from .db import BotUser, Database

logger = logging.getLogger(__name__)

# Payload deep link Telegram chi duoc chua A-Z a-z 0-9 _ - (toi da 64 ky tu), nen prefix
# 'r_' la an toan va giup phan biet payload voi moi thu khac go sau /start.
PAYLOAD = re.compile(r"^r[_-](?P<code>[0-9A-Za-z]{4,16})$")

# Do sau toi da khi di len cay gioi thieu de do vong lap.
MAX_CHAIN = 20


@dataclass(frozen=True)
class Seen:
    user: BotUser
    is_new: bool


# Tach ma moi khoi arg cua /start. Khong tach thi cmd_start se coi 'r_AB12CD' la ten
# the loai game.
def split_payload(arg: str) -> tuple[str | None, str]:
    parts = arg.split()
    if not parts:
        return None, arg
    matched = PAYLOAD.match(parts[0])
    if matched is None:
        return None, arg
    return matched.group("code").upper(), " ".join(parts[1:])


# Bam UA + IP thay vi luu ban goc: chi can biet 2 click co phai cung mot may hay khong.
def fingerprint(user_agent: str | None, ip: str | None) -> str:
    raw = f"{user_agent or ''}|{ip or ''}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class Tracker:
    def __init__(self, db: Database, click_window_min: int = 30):
        self.db = db
        self.click_window_min = click_window_min

    # None = payload khong co user id (event la, hoac nen tang khong gui). Moi buoc phia
    # sau bo qua, bot van chay y nhu truoc khi co tracking.
    def see(self, msg, key: str) -> Seen | None:
        if not msg.native_user_id:
            return None

        user, is_new = self.db.upsert_user(
            platform=msg.platform,
            native_user_id=msg.native_user_id,
            display_name=msg.author,
            username=msg.username,
            chat_key=key,
        )
        self.db.touch_member(key, user.id)
        return Seen(user=user, is_new=is_new)

    def attribute(self, seen: Seen, key: str, payload: str | None = None) -> None:
        found = self._by_payload(payload)
        if found is None and seen.is_new:
            found = self._by_chat(key, seen.user) or self._by_click(seen.user)
        if found is None:
            return

        inviter_id, source, confidence = found
        if self._accept(seen.user, inviter_id, confidence):
            self.db.set_referrer(seen.user.id, inviter_id, source, confidence)
            if source == "landing":
                self.db.claim_click(
                    self.db.user(inviter_id).ref_code, seen.user.id, self.click_window_min
                )
            logger.info(
                "Nguon gioi thieu: %s (%s) <- %s [%s/%s]",
                seen.user.display_name,
                seen.user.platform,
                inviter_id,
                source,
                confidence,
            )

    def note_click(self, code: str, ua_hash: str | None = None) -> BotUser | None:
        owner = self.db.user_by_code(code)
        if owner is None:
            return None
        self.db.add_click(owner.ref_code, ua_hash)
        return owner

    # --- 3 LUAT ---

    def _by_payload(self, payload: str | None) -> tuple[int, str, str] | None:
        if not payload:
            return None
        owner = self.db.user_by_code(payload)
        return (owner.id, "link", "exact") if owner else None

    def _by_chat(self, key: str, user: BotUser) -> tuple[int, str, str] | None:
        owner_id = self.db.earliest_member(key, exclude_user_id=user.id)
        return (owner_id, "group", "inferred") if owner_id else None

    def _by_click(self, user: BotUser) -> tuple[int, str, str] | None:
        codes = self.db.pending_click_codes(self.click_window_min)
        if len(codes) != 1:
            return None
        owner = self.db.user_by_code(codes[0])
        return (owner.id, "landing", "inferred") if owner else None

    # --- GUARD ---

    def _accept(self, user: BotUser, inviter_id: int, confidence: str) -> bool:
        if inviter_id == user.id:
            return False
        # Da co nguon thi khong ghi de, tru khi nang inferred len exact.
        if user.referred_by is not None:
            if user.ref_confidence == "exact" or confidence != "exact":
                return False
        return not self._is_descendant(inviter_id, user.id)

    # A khong the duoc gioi thieu boi chinh nguoi ma A da gioi thieu (truc tiep hay qua
    # nhieu bac): cay se thanh vong, moi thong ke di len cay se treo.
    def _is_descendant(self, candidate_id: int, ancestor_id: int) -> bool:
        seen: set[int] = set()
        current = self.db.user(candidate_id)
        for _ in range(MAX_CHAIN):
            if current is None or current.referred_by is None:
                return False
            if current.referred_by == ancestor_id:
                return True
            if current.referred_by in seen:
                return False
            seen.add(current.referred_by)
            current = self.db.user(current.referred_by)
        return False
