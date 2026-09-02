"""Lop truy cap SQLite. Diem cua tung nguoi trong 1 van luon tong = 0 (xem scoring.py).

chat_key la khoa dinh danh 1 phong chat, dang "<platform>:<id goc>", vi du
"telegram:-1004429201251" hoac "zalo:6ede9afa66b88fe6d6a9". Zalo dung id dang chuoi
nen khong the dung INTEGER nhu ban dau; prefix platform cung tranh 2 nen tang trung id.
"""

import json
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .text import normalize

SCHEMA_VERSION = 3

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
    "CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds(session_id, seq)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_web_token ON chats(web_token) "
    "WHERE web_token IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_sessions_chat ON sessions(chat_key, ended_at)",
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


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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

    def open_session(self, key: str, seat_ids: list[int], note: str | None = None) -> Session:
        cur = self.conn.execute(
            "INSERT INTO sessions (chat_key, note, seats, started_at) VALUES (?, ?, ?, ?)",
            (key, note, json.dumps(seat_ids), _now()),
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
        return Session(
            id=row["id"],
            chat_key=row["chat_key"],
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
