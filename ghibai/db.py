"""Lop truy cap SQLite. Diem cua tung nguoi trong 1 van luon tong = 0 (xem scoring.py).

chat_key la khoa dinh danh 1 phong chat, dang "<platform>:<id goc>", vi du
"telegram:-1004429201251" hoac "zalo:6ede9afa66b88fe6d6a9". Zalo dung id dang chuoi
nen khong the dung INTEGER nhu ban dau; prefix platform cung tranh 2 nen tang trung id.
"""

import json
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .text import normalize

SCHEMA_VERSION = 5

# Bo 0/O/1/I/L de doc qua dien thoai khong nham; ma nay nam trong link chia se nen phai
# de doc lai bang mat.
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 6

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS chats (
        chat_key   TEXT PRIMARY KEY,
        platform   TEXT NOT NULL,
        native_id  TEXT NOT NULL,
        title      TEXT,
        sheet_url  TEXT,
        web_token  TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS players (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_key   TEXT NOT NULL REFERENCES chats(chat_key) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        norm_name  TEXT NOT NULL,
        seat       INTEGER NOT NULL,
        active     INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        UNIQUE (chat_key, norm_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_key   TEXT NOT NULL REFERENCES chats(chat_key) ON DELETE CASCADE,
        game_type  TEXT NOT NULL DEFAULT '3cay',
        note       TEXT,
        seats      TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at   TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rounds (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        seq        INTEGER NOT NULL,
        banker_id  INTEGER NOT NULL REFERENCES players(id),
        raw_input  TEXT NOT NULL,
        tg_user    TEXT,
        voided     INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        edited_at  TEXT,
        UNIQUE (session_id, seq)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS round_scores (
        round_id  INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
        player_id INTEGER NOT NULL REFERENCES players(id),
        score     INTEGER NOT NULL,
        is_banker INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (round_id, player_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bot_users (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        platform       TEXT NOT NULL,
        native_user_id TEXT NOT NULL,
        display_name   TEXT,
        username       TEXT,
        ref_code       TEXT NOT NULL UNIQUE,
        referred_by    INTEGER REFERENCES bot_users(id),
        ref_source     TEXT,
        ref_confidence TEXT,
        referred_at    TEXT,
        first_chat_key TEXT,
        first_seen_at  TEXT NOT NULL,
        last_seen_at   TEXT NOT NULL,
        msg_count      INTEGER NOT NULL DEFAULT 0,
        UNIQUE (platform, native_user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_members (
        chat_key      TEXT NOT NULL REFERENCES chats(chat_key) ON DELETE CASCADE,
        user_id       INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
        first_seen_at TEXT NOT NULL,
        last_seen_at  TEXT NOT NULL,
        msg_count     INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (chat_key, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage_events (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        at       TEXT NOT NULL,
        day      TEXT NOT NULL,
        hour     INTEGER NOT NULL,
        platform TEXT NOT NULL,
        chat_key TEXT,
        user_id  INTEGER REFERENCES bot_users(id) ON DELETE SET NULL,
        kind     TEXT NOT NULL,
        command  TEXT,
        ok       INTEGER NOT NULL DEFAULT 1,
        ms       INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ref_clicks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_code   TEXT NOT NULL,
        at         TEXT NOT NULL,
        ua_hash    TEXT,
        claimed_by INTEGER REFERENCES bot_users(id),
        claimed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds(session_id, seq)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_web_token ON chats(web_token) "
    "WHERE web_token IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_sessions_chat ON sessions(chat_key, ended_at)",
    "CREATE INDEX IF NOT EXISTS idx_users_referred_by ON bot_users(referred_by)",
    "CREATE INDEX IF NOT EXISTS idx_usage_day ON usage_events(day, platform)",
    "CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_events(user_id, at)",
    "CREATE INDEX IF NOT EXISTS idx_clicks_open ON ref_clicks(claimed_by, at)",
]


def chat_key(platform: str, native_id: object) -> str:
    return f"{platform}:{native_id}"


@dataclass(frozen=True)
class Player:
    id: int
    name: str
    norm_name: str
    seat: int


@dataclass(frozen=True)
class Session:
    id: int
    chat_key: str
    game_type: str
    note: str | None
    seat_ids: list[int]
    started_at: str
    ended_at: str | None


@dataclass(frozen=True)
class Round:
    id: int
    seq: int
    banker_id: int
    created_at: str
    raw_input: str
    scores: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class BotUser:
    id: int
    platform: str
    native_user_id: str
    display_name: str | None
    ref_code: str
    referred_by: int | None
    ref_source: str | None
    ref_confidence: str | None
    first_chat_key: str | None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# So sanh moc thoi gian bang chuoi ISO: chi dung duoc khi moi moc cung offset, nen moc
# cat luon phai di qua dung ham nay chu khong tu ghep tay.
def _ago(**delta) -> str:
    moment = datetime.now(timezone.utc).astimezone() - timedelta(**delta)
    return moment.isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.conn.close()

    # --- SCHEMA ---

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version < SCHEMA_VERSION:
            if self._is_legacy_v1():
                self._upgrade_v1_to_v2()
            self._add_web_token_column()
            self._add_game_type_column()
            self._apply_schema()
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        # Chay ca khi user_version da moi nhat: DB dinh bug FK duoi day van dang o dung version.
        self._repair_dangling_refs()
        self.conn.commit()

    # only: chi chay cau lenh cua may bang duoc liet ke (khi va DB, de khong dung toi
    # phan schema con lai co the dang cu hon).
    def _apply_schema(self, only: set[str] | None = None) -> None:
        for statement in SCHEMA:
            head = statement.split("(")[0]
            if only is None or any(f" {table}" in head for table in only):
                self.conn.execute(statement)

    # DB v2 chua co cot nay; chay truoc _apply_schema vi index web_token can cot da ton tai.
    def _add_web_token_column(self) -> None:
        columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(chats)")}
        if columns and "web_token" not in columns:
            self.conn.execute("ALTER TABLE chats ADD COLUMN web_token TEXT")

    def _add_game_type_column(self) -> None:
        columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(sessions)")}
        if columns and "game_type" not in columns:
            self.conn.execute("ALTER TABLE sessions ADD COLUMN game_type TEXT NOT NULL DEFAULT '3cay'")

    # v1 dung chat_id INTEGER va chi co Telegram.
    def _is_legacy_v1(self) -> bool:
        exists = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chats'"
        ).fetchone()
        if not exists:
            return False
        columns = {r["name"] for r in self.conn.execute("PRAGMA table_info(chats)")}
        return "chat_id" in columns and "chat_key" not in columns

    # Du lieu cu deu la Telegram nen chat_key = "telegram:" + chat_id. Giu nguyen id cua
    # players/sessions vi rounds va round_scores tro toi chung.
    def _upgrade_v1_to_v2(self) -> None:
        self.conn.execute("PRAGMA foreign_keys = OFF")
        # Mac dinh RENAME se sua luon FK cua rounds/round_scores thanh REFERENCES
        # "players_v1"; drop bang _v1 xong la FK tro vao bang khong ton tai. legacy_alter_table
        # giu nguyen FK cua cac bang khac - dung y o day vi ta tao lai bang cung ten.
        self.conn.execute("PRAGMA legacy_alter_table = ON")
        self.conn.execute("BEGIN")
        try:
            for table in ("chats", "players", "sessions"):
                self.conn.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")
            self._apply_schema()

            self.conn.execute(
                "INSERT INTO chats (chat_key, platform, native_id, title, sheet_url, created_at) "
                "SELECT 'telegram:' || chat_id, 'telegram', CAST(chat_id AS TEXT), "
                "       title, sheet_url, created_at FROM chats_v1"
            )
            self.conn.execute(
                "INSERT INTO players (id, chat_key, name, norm_name, seat, active, created_at) "
                "SELECT id, 'telegram:' || chat_id, name, norm_name, seat, active, created_at "
                "FROM players_v1"
            )
            self.conn.execute(
                "INSERT INTO sessions (id, chat_key, note, seats, started_at, ended_at) "
                "SELECT id, 'telegram:' || chat_id, note, seats, started_at, ended_at "
                "FROM sessions_v1"
            )
            for table in ("chats_v1", "players_v1", "sessions_v1"):
                self.conn.execute(f"DROP TABLE {table}")
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.execute("PRAGMA legacy_alter_table = OFF")
            self.conn.execute("PRAGMA foreign_keys = ON")

    # Va cho DB da bi ban migration cu lam hong: rounds/round_scores con tro toi players_v1
    # va sessions_v1 (da bi drop), nen moi lan ghi van deu chet "no such table".
    def _repair_dangling_refs(self) -> None:
        broken = [
            r["name"]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('rounds', 'round_scores') AND sql LIKE '%\\_v1%' ESCAPE '\\'"
            )
        ]
        if not broken:
            return

        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.conn.execute("PRAGMA legacy_alter_table = ON")
        self.conn.execute("BEGIN")
        try:
            # round_scores tro toi rounds nen phai dung lai theo dung thu tu nay.
            for table in ("round_scores", "rounds"):
                if table in broken:
                    self.conn.execute(f"ALTER TABLE {table} RENAME TO {table}_broken")
            self._apply_schema(only=set(broken))
            for table in ("rounds", "round_scores"):
                if table in broken:
                    columns = ", ".join(
                        r["name"] for r in self.conn.execute(f"PRAGMA table_info({table})")
                    )
                    self.conn.execute(
                        f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {table}_broken"
                    )
                    self.conn.execute(f"DROP TABLE {table}_broken")
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self.conn.execute("PRAGMA legacy_alter_table = OFF")
            self.conn.execute("PRAGMA foreign_keys = ON")

    # --- CHAT ---

    def ensure_chat(self, key: str, platform: str, native_id: object, title: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO chats (chat_key, platform, native_id, title, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(chat_key) DO UPDATE SET title = COALESCE(excluded.title, chats.title)",
            (key, platform, str(native_id), title, _now()),
        )
        self.conn.commit()

    def get_sheet_url(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT sheet_url FROM chats WHERE chat_key = ?", (key,)
        ).fetchone()
        return row["sheet_url"] if row else None

    def set_sheet_url(self, key: str, url: str) -> None:
        self.conn.execute("UPDATE chats SET sheet_url = ? WHERE chat_key = ?", (url, key))
        self.conn.commit()

    # --- WEB TOKEN ---

    # Token nam trong link chia se nen phai kho doan; moi chat mot token rieng.
    def get_or_create_web_token(self, key: str) -> str:
        row = self.conn.execute(
            "SELECT web_token FROM chats WHERE chat_key = ?", (key,)
        ).fetchone()
        if row is not None and row["web_token"]:
            return row["web_token"]
        return self.reset_web_token(key)

    def reset_web_token(self, key: str) -> str:
        token = secrets.token_urlsafe(18)
        self.conn.execute("UPDATE chats SET web_token = ? WHERE chat_key = ?", (token, key))
        self.conn.commit()
        return token

    def chat_by_web_token(self, token: str) -> dict | None:
        row = self.conn.execute(
            "SELECT chat_key, platform, title FROM chats WHERE web_token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None

    # --- PLAYERS ---

    def get_roster(self, key: str) -> list[Player]:
        rows = self.conn.execute(
            "SELECT id, name, norm_name, seat FROM players "
            "WHERE chat_key = ? AND active = 1 ORDER BY seat",
            (key,),
        ).fetchall()
        return [Player(r["id"], r["name"], r["norm_name"], r["seat"]) for r in rows]

    def get_players_by_ids(self, ids: list[int]) -> dict[int, Player]:
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT id, name, norm_name, seat FROM players WHERE id IN ({marks})", ids
        ).fetchall()
        return {r["id"]: Player(r["id"], r["name"], r["norm_name"], r["seat"]) for r in rows}

    # Thay toan bo roster; thu tu `names` chinh la thu tu cho ngoi dung cho cu phap nhap theo vi tri.
    def set_roster(self, key: str, names: list[str]) -> list[Player]:
        keep: list[str] = []
        for seat, name in enumerate(names):
            norm = normalize(name)
            keep.append(norm)
            self.conn.execute(
                "INSERT INTO players (chat_key, name, norm_name, seat, active, created_at) "
                "VALUES (?, ?, ?, ?, 1, ?) "
                "ON CONFLICT(chat_key, norm_name) DO UPDATE SET name = excluded.name, "
                "seat = excluded.seat, active = 1",
                (key, name.strip(), norm, seat, _now()),
            )
        marks = ",".join("?" * len(keep)) or "''"
        self.conn.execute(
            f"UPDATE players SET active = 0 WHERE chat_key = ? AND norm_name NOT IN ({marks})",
            [key, *keep],
        )
        self.conn.commit()
        return self.get_roster(key)

    def add_player(self, key: str, name: str) -> Player:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(seat), -1) + 1 AS next FROM players WHERE chat_key = ?", (key,)
        ).fetchone()
        self.conn.execute(
            "INSERT INTO players (chat_key, name, norm_name, seat, active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?) "
            "ON CONFLICT(chat_key, norm_name) DO UPDATE SET name = excluded.name, active = 1",
            (key, name.strip(), normalize(name), row["next"], _now()),
        )
        self.conn.commit()
        norm = normalize(name)
        return next(p for p in self.get_roster(key) if p.norm_name == norm)

    def deactivate_player(self, key: str, name: str) -> Player | None:
        norm = normalize(name)
        player = next((p for p in self.get_roster(key) if p.norm_name == norm), None)
        if player is None:
            return None
        self.conn.execute("UPDATE players SET active = 0 WHERE id = ?", (player.id,))
        self.conn.commit()
        return player

    # --- SESSIONS ---

    def active_session(self, key: str) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE chat_key = ? AND ended_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (key,),
        ).fetchone()
        return self._to_session(row) if row else None

    def latest_session(self, key: str) -> Session | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE chat_key = ? ORDER BY id DESC LIMIT 1", (key,)
        ).fetchone()
        return self._to_session(row) if row else None

    def open_session(
        self, key: str, seat_ids: list[int], note: str | None = None, game_type: str = "3cay"
    ) -> Session:
        cur = self.conn.execute(
            "INSERT INTO sessions (chat_key, game_type, note, seats, started_at) VALUES (?, ?, ?, ?, ?)",
            (key, game_type, note, json.dumps(seat_ids), _now()),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._to_session(row)

    def set_session_seats(self, session_id: int, seat_ids: list[int]) -> None:
        self.conn.execute(
            "UPDATE sessions SET seats = ? WHERE id = ?", (json.dumps(seat_ids), session_id)
        )
        self.conn.commit()

    def close_session(self, session_id: int) -> None:
        self.conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (_now(), session_id))
        self.conn.commit()

    @staticmethod
    def _to_session(row: sqlite3.Row) -> Session:
        keys = row.keys()
        return Session(
            id=row["id"],
            chat_key=row["chat_key"],
            game_type=row["game_type"] if "game_type" in keys else "3cay",
            note=row["note"],
            seat_ids=json.loads(row["seats"]),
            started_at=row["started_at"],
            ended_at=row["ended_at"],
        )

    # --- ROUNDS ---

    def add_round(
        self,
        session_id: int,
        banker_id: int,
        scores: dict[int, int],
        raw_input: str,
        author: str | None = None,
    ) -> Round:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM rounds WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        cur = self.conn.execute(
            "INSERT INTO rounds (session_id, seq, banker_id, raw_input, tg_user, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, row["next"], banker_id, raw_input, author, _now()),
        )
        self._write_scores(cur.lastrowid, banker_id, scores)
        self.conn.commit()
        return self.get_round(cur.lastrowid)

    # Ghi lai 1 van da co, giu nguyen so van de moi nguoi con doi chieu duoc voi so tay.
    def replace_round(
        self, session_id: int, seq: int, banker_id: int, scores: dict[int, int], raw_input: str
    ) -> Round | None:
        row = self.conn.execute(
            "SELECT id FROM rounds WHERE session_id = ? AND seq = ? AND voided = 0",
            (session_id, seq),
        ).fetchone()
        if row is None:
            return None
        self.conn.execute("DELETE FROM round_scores WHERE round_id = ?", (row["id"],))
        self.conn.execute(
            "UPDATE rounds SET banker_id = ?, raw_input = ?, edited_at = ? WHERE id = ?",
            (banker_id, raw_input, _now(), row["id"]),
        )
        self._write_scores(row["id"], banker_id, scores)
        self.conn.commit()
        return self.get_round(row["id"])

    def _write_scores(self, round_id: int, banker_id: int, scores: dict[int, int]) -> None:
        self.conn.executemany(
            "INSERT INTO round_scores (round_id, player_id, score, is_banker) VALUES (?, ?, ?, ?)",
            [(round_id, pid, sc, int(pid == banker_id)) for pid, sc in scores.items()],
        )

    def void_last_round(self, session_id: int) -> Round | None:
        row = self.conn.execute(
            "SELECT id FROM rounds WHERE session_id = ? AND voided = 0 ORDER BY seq DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        rnd = self.get_round(row["id"])
        self.conn.execute("UPDATE rounds SET voided = 1 WHERE id = ?", (row["id"],))
        self.conn.commit()
        return rnd

    def void_round(self, session_id: int, seq: int) -> Round | None:
        row = self.conn.execute(
            "SELECT id FROM rounds WHERE session_id = ? AND seq = ? AND voided = 0",
            (session_id, seq),
        ).fetchone()
        if row is None:
            return None
        rnd = self.get_round(row["id"])
        self.conn.execute("UPDATE rounds SET voided = 1 WHERE id = ?", (row["id"],))
        self.conn.commit()
        return rnd

    def unvoid_round(self, session_id: int, seq: int) -> Round | None:
        row = self.conn.execute(
            "SELECT id FROM rounds WHERE session_id = ? AND seq = ? AND voided = 1",
            (session_id, seq),
        ).fetchone()
        if row is None:
            return None
        self.conn.execute("UPDATE rounds SET voided = 0 WHERE id = ?", (row["id"],))
        self.conn.commit()
        return self.get_round(row["id"])

    def void_all_rounds(self, session_id: int) -> int:
        cur = self.conn.execute(
            "UPDATE rounds SET voided = 1 WHERE session_id = ? AND voided = 0", (session_id,)
        )
        self.conn.commit()
        return cur.rowcount

    def voided_seqs(self, session_id: int) -> list[int]:
        rows = self.conn.execute(
            "SELECT seq FROM rounds WHERE session_id = ? AND voided = 1 ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [r["seq"] for r in rows]

    def get_round(self, round_id: int) -> Round:
        row = self.conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
        scores = self.conn.execute(
            "SELECT player_id, score FROM round_scores WHERE round_id = ?", (round_id,)
        ).fetchall()
        return Round(
            id=row["id"],
            seq=row["seq"],
            banker_id=row["banker_id"],
            created_at=row["created_at"],
            raw_input=row["raw_input"],
            scores={s["player_id"]: s["score"] for s in scores},
        )

    def get_rounds(self, session_id: int) -> list[Round]:
        rows = self.conn.execute(
            "SELECT id FROM rounds WHERE session_id = ? AND voided = 0 ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [self.get_round(r["id"]) for r in rows]

    def session_totals(self, session_id: int) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT rs.player_id, SUM(rs.score) AS total FROM round_scores rs "
            "JOIN rounds r ON r.id = rs.round_id "
            "WHERE r.session_id = ? AND r.voided = 0 GROUP BY rs.player_id",
            (session_id,),
        ).fetchall()
        return {r["player_id"]: r["total"] for r in rows}

    # Tong hop moi buoi da choi trong chat, dung cho /xh.
    def lifetime_stats(self, key: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT p.name, COUNT(*) AS rounds, SUM(rs.score) AS total, "
            "       SUM(rs.is_banker) AS banker_rounds "
            "FROM round_scores rs "
            "JOIN rounds r ON r.id = rs.round_id AND r.voided = 0 "
            "JOIN sessions s ON s.id = r.session_id "
            "JOIN players p ON p.id = rs.player_id "
            "WHERE s.chat_key = ? GROUP BY p.id ORDER BY total DESC",
            (key,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- TRACKING: NGUOI DUNG ---

    # Tra ve (user, la_nguoi_moi). Co la_nguoi_moi vi luat gan nguon gioi thieu chi chay
    # dung mot lan, ngay lan dau thay user do.
    def upsert_user(
        self,
        platform: str,
        native_user_id: str,
        display_name: str | None = None,
        username: str | None = None,
        chat_key: str | None = None,
    ) -> tuple[BotUser, bool]:
        row = self.conn.execute(
            "SELECT * FROM bot_users WHERE platform = ? AND native_user_id = ?",
            (platform, native_user_id),
        ).fetchone()

        if row is not None:
            # COALESCE: Zalo doi khi khong gui display_name, khong de tin thieu ghi de ten cu.
            self.conn.execute(
                "UPDATE bot_users SET last_seen_at = ?, msg_count = msg_count + 1, "
                "display_name = COALESCE(?, display_name), username = COALESCE(?, username) "
                "WHERE id = ?",
                (_now(), display_name, username, row["id"]),
            )
            self.conn.commit()
            return self._to_user(self.conn.execute(
                "SELECT * FROM bot_users WHERE id = ?", (row["id"],)
            ).fetchone()), False

        cur = self.conn.execute(
            "INSERT INTO bot_users (platform, native_user_id, display_name, username, ref_code, "
            "                       first_chat_key, first_seen_at, last_seen_at, msg_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                platform,
                native_user_id,
                display_name,
                username,
                self._new_ref_code(),
                chat_key,
                _now(),
                _now(),
            ),
        )
        self.conn.commit()
        return self.user(cur.lastrowid), True

    def user(self, user_id: int) -> BotUser | None:
        row = self.conn.execute("SELECT * FROM bot_users WHERE id = ?", (user_id,)).fetchone()
        return self._to_user(row) if row else None

    def user_by_code(self, code: str) -> BotUser | None:
        row = self.conn.execute(
            "SELECT * FROM bot_users WHERE ref_code = ?", (code.strip().upper(),)
        ).fetchone()
        return self._to_user(row) if row else None

    def user_by_native_id(self, platform: str, native_user_id: str) -> BotUser | None:
        row = self.conn.execute(
            "SELECT * FROM bot_users WHERE platform = ? AND native_user_id = ?",
            (platform, native_user_id),
        ).fetchone()
        return self._to_user(row) if row else None

    def set_referrer(self, user_id: int, inviter_id: int, source: str, confidence: str) -> None:
        self.conn.execute(
            "UPDATE bot_users SET referred_by = ?, ref_source = ?, ref_confidence = ?, "
            "referred_at = ? WHERE id = ?",
            (inviter_id, source, confidence, _now(), user_id),
        )
        self.conn.commit()

    def count_invited(self, user_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM bot_users WHERE referred_by = ?", (user_id,)
        ).fetchone()
        return row["n"]

    def _new_ref_code(self) -> str:
        for _ in range(20):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            taken = self.conn.execute(
                "SELECT 1 FROM bot_users WHERE ref_code = ?", (code,)
            ).fetchone()
            if taken is None:
                return code
        raise RuntimeError("Không sinh được mã giới thiệu mới sau 20 lần thử.")

    @staticmethod
    def _to_user(row: sqlite3.Row) -> BotUser:
        return BotUser(
            id=row["id"],
            platform=row["platform"],
            native_user_id=row["native_user_id"],
            display_name=row["display_name"],
            ref_code=row["ref_code"],
            referred_by=row["referred_by"],
            ref_source=row["ref_source"],
            ref_confidence=row["ref_confidence"],
            first_chat_key=row["first_chat_key"],
        )

    # --- TRACKING: THANH VIEN CHAT ---

    def touch_member(self, chat_key: str, user_id: int) -> None:
        self.conn.execute(
            "INSERT INTO chat_members (chat_key, user_id, first_seen_at, last_seen_at, msg_count) "
            "VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT(chat_key, user_id) DO UPDATE SET last_seen_at = excluded.last_seen_at, "
            "msg_count = chat_members.msg_count + 1",
            (chat_key, user_id, _now(), _now()),
        )
        self.conn.commit()

    # Nguoi dung bot som nhat trong chat nay. Trong nhom day chinh la nguoi da mang bot
    # vao (ho luon la nguoi go lenh dau tien), nen dung lam nguoi gioi thieu suy doan.
    def earliest_member(self, chat_key: str, exclude_user_id: int | None = None) -> int | None:
        row = self.conn.execute(
            "SELECT user_id FROM chat_members WHERE chat_key = ? AND user_id IS NOT ? "
            "ORDER BY first_seen_at, user_id LIMIT 1",
            (chat_key, exclude_user_id),
        ).fetchone()
        return row["user_id"] if row else None

    # --- TRACKING: LOG LUU LUONG ---

    def log_event(
        self,
        platform: str,
        kind: str,
        chat_key: str | None = None,
        user_id: int | None = None,
        command: str | None = None,
        ok: bool = True,
        ms: int | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).astimezone()
        self.conn.execute(
            "INSERT INTO usage_events (at, day, hour, platform, chat_key, user_id, kind, "
            "                          command, ok, ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                now.isoformat(timespec="seconds"),
                now.strftime("%Y-%m-%d"),
                now.hour,
                platform,
                chat_key,
                user_id,
                kind,
                command,
                int(ok),
                ms,
            ),
        )
        self.conn.commit()

    def prune_events(self, days: int) -> int:
        cur = self.conn.execute("DELETE FROM usage_events WHERE at < ?", (_ago(days=days),))
        self.conn.commit()
        return cur.rowcount

    # --- TRACKING: CLICK LINK MOI ---

    def add_click(self, ref_code: str, ua_hash: str | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO ref_clicks (ref_code, at, ua_hash) VALUES (?, ?, ?)",
            (ref_code.strip().upper(), _now(), ua_hash),
        )
        self.conn.commit()
        return cur.lastrowid

    # Cac ma da duoc bam trong cua so thoi gian ma chua ai nhan. Tra ve nhieu hon 1 ma
    # nghia la nhap nhang - ben goi phai tu bo qua chu khong duoc doan bua.
    def pending_click_codes(self, window_min: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT ref_code FROM ref_clicks "
            "WHERE claimed_by IS NULL AND at >= ? ORDER BY ref_code",
            (_ago(minutes=window_min),),
        ).fetchall()
        return [r["ref_code"] for r in rows]

    def claim_click(self, ref_code: str, user_id: int, window_min: int) -> None:
        self.conn.execute(
            "UPDATE ref_clicks SET claimed_by = ?, claimed_at = ? "
            "WHERE claimed_by IS NULL AND ref_code = ? AND at >= ?",
            (user_id, _now(), ref_code.strip().upper(), _ago(minutes=window_min)),
        )
        self.conn.commit()
