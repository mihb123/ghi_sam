"""Schema v1 dung chat_id INTEGER (chi Telegram); v2 doi sang chat_key TEXT co prefix platform."""

import sqlite3

from ghibai.db import SCHEMA_VERSION, Database

V1_SCHEMA = """
CREATE TABLE chats (chat_id INTEGER PRIMARY KEY, title TEXT, sheet_url TEXT, created_at TEXT NOT NULL);
CREATE TABLE players (id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
    name TEXT NOT NULL, norm_name TEXT NOT NULL, seat INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, UNIQUE (chat_id, norm_name));
CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
    note TEXT, seats TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT);
CREATE TABLE rounds (id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL, banker_id INTEGER NOT NULL REFERENCES players(id),
    raw_input TEXT NOT NULL, tg_user TEXT,
    voided INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, edited_at TEXT,
    UNIQUE (session_id, seq));
CREATE TABLE round_scores (round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id),
    score INTEGER NOT NULL, is_banker INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (round_id, player_id));
"""


def make_v1(path):
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA)
    conn.execute("INSERT INTO chats VALUES (-1004429201251, 'Ghi sổ', 'https://sheet', 'now')")
    conn.executemany(
        "INSERT INTO players (id, chat_id, name, norm_name, seat, active, created_at) "
        "VALUES (?, -1004429201251, ?, ?, ?, 1, 'now')",
        [(1, "Hương", "huong", 0), (2, "Hằng", "hang", 1), (3, "Toàn", "toan", 2)],
    )
    conn.execute(
        "INSERT INTO sessions (id, chat_id, note, seats, started_at) "
        "VALUES (7, -1004429201251, 'tối thứ 7', '[1, 2, 3]', 'now')"
    )
    conn.execute(
        "INSERT INTO rounds (id, session_id, seq, banker_id, raw_input, created_at) "
        "VALUES (11, 7, 1, 3, '-5, 5, ', 'now')"
    )
    conn.executemany(
        "INSERT INTO round_scores VALUES (11, ?, ?, ?)", [(1, -5, 0), (2, 5, 0), (3, 0, 1)]
    )
    conn.commit()
    conn.close()


def test_du_lieu_telegram_cu_duoc_giu_nguyen(tmp_path):
    path = tmp_path / "v1.db"
    make_v1(path)
    db = Database(path)

    chats = [dict(r) for r in db.conn.execute("SELECT * FROM chats")]
    assert chats[0]["chat_key"] == "telegram:-1004429201251"
    assert chats[0]["platform"] == "telegram"
    assert chats[0]["native_id"] == "-1004429201251"
    assert chats[0]["title"] == "Ghi sổ"
    assert chats[0]["sheet_url"] == "https://sheet"

    key = "telegram:-1004429201251"
    assert [p.name for p in db.get_roster(key)] == ["Hương", "Hằng", "Toàn"]

    session = db.active_session(key)
    assert session.id == 7 and session.note == "tối thứ 7" and session.seat_ids == [1, 2, 3]

    rounds = db.get_rounds(session.id)
    assert len(rounds) == 1
    assert rounds[0].scores == {1: -5, 2: 5, 3: 0}
    assert sum(rounds[0].scores.values()) == 0
    db.close()


def test_bang_cu_duoc_don_va_version_duoc_ghi(tmp_path):
    path = tmp_path / "v1.db"
    make_v1(path)
    db = Database(path)
    tables = {
        r[0]
        for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert not any(t.endswith("_v1") for t in tables)
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    db.close()


def test_migrate_chay_lai_khong_lam_gi_them(tmp_path):
    path = tmp_path / "v1.db"
    make_v1(path)
    Database(path).close()
    db = Database(path)
    assert [p.name for p in db.get_roster("telegram:-1004429201251")] == ["Hương", "Hằng", "Toàn"]
    assert db.conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0] == 1
    db.close()


def test_db_moi_tao_thang_v2(tmp_path):
    db = Database(tmp_path / "fresh.db")
    columns = {r["name"] for r in db.conn.execute("PRAGMA table_info(chats)")}
    assert "chat_key" in columns and "chat_id" not in columns
    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    db.close()


# --- FK TREO SAU MIGRATION ---
# ALTER TABLE ... RENAME tu sua FK cua rounds/round_scores thanh REFERENCES "players_v1";
# drop bang _v1 xong thi moi lenh ghi van deu chet "no such table: main.players_v1".

def _fk_targets(conn, table):
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()[0]
    return sql


def test_migration_khong_de_lai_fk_tro_toi_bang_v1(tmp_path):
    path = tmp_path / "v1.db"
    make_v1(path)
    db = Database(path)
    for table in ("rounds", "round_scores"):
        assert "_v1" not in _fk_targets(db.conn, table)
    assert db.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_ghi_van_moi_sau_khi_migrate(tmp_path):
    path = tmp_path / "v1.db"
    make_v1(path)
    db = Database(path)

    key = "telegram:-1004429201251"
    session = db.active_session(key) or db.start_session(key, [p.id for p in db.get_roster(key)])
    rnd = db.add_round(session.id, 3, {1: -5, 2: 5, 3: 0}, "5,-5,,5", "Test")
    assert rnd.seq >= 1
    assert db.conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_va_db_da_hong_san(tmp_path):
    """DB da bi ban cu lam hong van dang o user_version moi nhat nen phai tu va khi mo lai."""
    path = tmp_path / "v1.db"
    make_v1(path)

    # Tai hien dung loi cu: rename co viet lai FK, roi drop bang _v1.
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = OFF")
    for table in ("chats", "players", "sessions"):
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_v1")
    conn.executescript(V1_SCHEMA.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "))
    for table in ("chats_v1", "players_v1", "sessions_v1"):
        conn.execute(f"DROP TABLE {table}")
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    assert "_v1" in conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'rounds'"
    ).fetchone()[0]
    conn.close()

    db = Database(path)
    assert "_v1" not in _fk_targets(db.conn, "rounds")
    assert "_v1" not in _fk_targets(db.conn, "round_scores")
    assert db.conn.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == 1


def test_migration_them_cot_game_type(tmp_path):
    path = tmp_path / "v3.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 3")
    conn.execute(
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_key TEXT NOT NULL, "
        "note TEXT, seats TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT)"
    )
    conn.execute(
        "INSERT INTO sessions (id, chat_key, note, seats, started_at) "
        "VALUES (1, 'telegram:123', 'test v3', '[1, 2]', 'now')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    columns = {r["name"] for r in db.conn.execute("PRAGMA table_info(sessions)")}
    assert "game_type" in columns
    session = db.latest_session("telegram:123")
    assert session is not None
    assert session.game_type == "3cay"
    db.close()


# --- V4 -> V5: THEM BANG TRACKING ---
# v5 chi them bang moi, khong sua bang cu, nen migration phai giu nguyen 100% du lieu game.

V4_SCHEMA = """
CREATE TABLE chats (chat_key TEXT PRIMARY KEY, platform TEXT NOT NULL, native_id TEXT NOT NULL,
    title TEXT, sheet_url TEXT, web_token TEXT, created_at TEXT NOT NULL);
CREATE TABLE players (id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL REFERENCES chats(chat_key) ON DELETE CASCADE,
    name TEXT NOT NULL, norm_name TEXT NOT NULL, seat INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, UNIQUE (chat_key, norm_name));
CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key TEXT NOT NULL REFERENCES chats(chat_key) ON DELETE CASCADE,
    game_type TEXT NOT NULL DEFAULT '3cay', note TEXT, seats TEXT NOT NULL,
    started_at TEXT NOT NULL, ended_at TEXT);
CREATE TABLE rounds (id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL, banker_id INTEGER NOT NULL REFERENCES players(id),
    raw_input TEXT NOT NULL, tg_user TEXT, voided INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, edited_at TEXT, UNIQUE (session_id, seq));
CREATE TABLE round_scores (round_id INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id),
    score INTEGER NOT NULL, is_banker INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (round_id, player_id));
"""

TRACKING_TABLES = {"bot_users", "chat_members", "usage_events", "ref_clicks"}


def make_v4(path):
    conn = sqlite3.connect(path)
    conn.executescript(V4_SCHEMA)
    conn.execute("PRAGMA user_version = 4")
    conn.execute(
        "INSERT INTO chats VALUES ('zalo:abc', 'zalo', 'abc', 'Nhóm Zalo', NULL, 'tok', 'now')"
    )
    conn.executemany(
        "INSERT INTO players (id, chat_key, name, norm_name, seat, active, created_at) "
        "VALUES (?, 'zalo:abc', ?, ?, ?, 1, 'now')",
        [(1, "Hương", "huong", 0), (2, "Hằng", "hang", 1), (3, "Toàn", "toan", 2)],
    )
    conn.execute(
        "INSERT INTO sessions (id, chat_key, game_type, note, seats, started_at) "
        "VALUES (5, 'zalo:abc', 'sam', 'tối chủ nhật', '[1, 2, 3]', 'now')"
    )
    conn.execute(
        "INSERT INTO rounds (id, session_id, seq, banker_id, raw_input, created_at) "
        "VALUES (9, 5, 1, 3, '-5, -10, c', 'now')"
    )
    conn.executemany(
        "INSERT INTO round_scores VALUES (9, ?, ?, ?)", [(1, -5, 0), (2, -10, 0), (3, 15, 1)]
    )
    conn.commit()
    conn.close()


def test_v4_len_v5_giu_nguyen_du_lieu_game(tmp_path):
    path = tmp_path / "v4.db"
    make_v4(path)
    db = Database(path)

    assert db.conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert [p.name for p in db.get_roster("zalo:abc")] == ["Hương", "Hằng", "Toàn"]

    session = db.active_session("zalo:abc")
    assert session.id == 5 and session.game_type == "sam" and session.note == "tối chủ nhật"

    rounds = db.get_rounds(session.id)
    assert rounds[0].scores == {1: -5, 2: -10, 3: 15}
    assert sum(rounds[0].scores.values()) == 0
    assert db.get_or_create_web_token("zalo:abc") == "tok"
    db.close()


def test_v4_len_v5_them_du_bang_tracking(tmp_path):
    path = tmp_path / "v4.db"
    make_v4(path)
    db = Database(path)

    tables = {
        r[0] for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert TRACKING_TABLES <= tables
    assert db.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()


def test_v4_len_v5_ghi_duoc_ngay_du_lieu_tracking(tmp_path):
    path = tmp_path / "v4.db"
    make_v4(path)
    db = Database(path)

    user, is_new = db.upsert_user("zalo", "user-1", "Hương", chat_key="zalo:abc")
    db.touch_member("zalo:abc", user.id)
    db.log_event(platform="zalo", kind="command", chat_key="zalo:abc", user_id=user.id)

    assert is_new and user.ref_code
    assert db.earliest_member("zalo:abc") == user.id
    assert db.conn.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()
