"""Tong hop so lieu tu bot_users / chat_members / usage_events.

Chi doc, khong sua gi. Tra ve dung mot dict dung chung cho ca lenh /thongke (render.stats)
va API /api/stats (trang /admin), de hai cho khong bao gio lech so nhau.

Dinh nghia "active": co it nhat 1 dong trong usage_events, tuc la nguoi do thuc su go
lenh hoac ghi van - khong tinh tin nhan tan gau trong nhom.
"""

from datetime import datetime, timedelta, timezone

from .db import Database

DAILY_DAYS = 30
TOP_LIMIT = 10


def _local_now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def _day(offset: int = 0) -> str:
    return (_local_now() - timedelta(days=offset)).strftime("%Y-%m-%d")


def _iso_ago(days: int) -> str:
    return (_local_now() - timedelta(days=days)).isoformat(timespec="seconds")


def overview(db: Database, days: int = DAILY_DAYS) -> dict:
    conn = db.conn
    return {
        "generatedAt": _local_now().isoformat(timespec="seconds"),
        "totals": _totals(conn),
        "users": _users(conn),
        "byPlatform": _by_platform(conn),
        "daily": _daily(conn, days),
        "hourly": _hourly(conn, days),
        "referrals": _referrals(conn),
        "topCommands": _top_commands(conn, days),
        "topChats": _top_chats(conn),
    }


# --- TONG QUAN ---


def _totals(conn) -> dict:
    def scalar(sql: str) -> int:
        return conn.execute(sql).fetchone()[0] or 0

    return {
        "users": scalar("SELECT COUNT(*) FROM bot_users"),
        "chats": scalar("SELECT COUNT(*) FROM chats"),
        "sessions": scalar("SELECT COUNT(*) FROM sessions"),
        "rounds": scalar("SELECT COUNT(*) FROM rounds WHERE voided = 0"),
        "events": scalar("SELECT COUNT(*) FROM usage_events"),
    }


def _users(conn) -> dict:
    def new_since(days: int) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM bot_users WHERE first_seen_at >= ?", (_iso_ago(days),)
        ).fetchone()[0]

    def active_since(days: int) -> int:
        return conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM usage_events "
            "WHERE user_id IS NOT NULL AND day >= ?",
            (_day(days - 1),),
        ).fetchone()[0]

    return {
        "newToday": conn.execute(
            "SELECT COUNT(*) FROM bot_users WHERE substr(first_seen_at, 1, 10) = ?", (_day(),)
        ).fetchone()[0],
        "new7d": new_since(7),
        "new30d": new_since(30),
        "dau": active_since(1),
        "wau": active_since(7),
        "mau": active_since(30),
    }


def _by_platform(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT u.platform, COUNT(*) AS users, "
        "       SUM(CASE WHEN u.first_seen_at >= ? THEN 1 ELSE 0 END) AS new7d "
        "FROM bot_users u GROUP BY u.platform ORDER BY users DESC",
        (_iso_ago(7),),
    ).fetchall()

    chats = dict(
        conn.execute("SELECT platform, COUNT(*) FROM chats GROUP BY platform").fetchall()
    )
    dau = dict(
        conn.execute(
            "SELECT platform, COUNT(DISTINCT user_id) FROM usage_events "
            "WHERE user_id IS NOT NULL AND day = ? GROUP BY platform",
            (_day(),),
        ).fetchall()
    )
    return [
        {
            "platform": r["platform"],
            "users": r["users"],
            "new7d": r["new7d"],
            "chats": chats.get(r["platform"], 0),
            "dau": dau.get(r["platform"], 0),
        }
        for r in rows
    ]


# --- CHUOI NGAY & GIO ---


# Tra ve du `days` ngay ke ca ngay khong co du lieu: bieu do cot khong bi co lai.
def _daily(conn, days: int) -> list[dict]:
    since = _day(days - 1)
    events = {
        r["day"]: (r["events"], r["active"])
        for r in conn.execute(
            "SELECT day, COUNT(*) AS events, COUNT(DISTINCT user_id) AS active "
            "FROM usage_events WHERE day >= ? GROUP BY day",
            (since,),
        ).fetchall()
    }
    joined = dict(
        conn.execute(
            "SELECT substr(first_seen_at, 1, 10) AS day, COUNT(*) FROM bot_users "
            "WHERE substr(first_seen_at, 1, 10) >= ? GROUP BY day",
            (since,),
        ).fetchall()
    )

    series = []
    for offset in range(days - 1, -1, -1):
        day = _day(offset)
        count, active = events.get(day, (0, 0))
        series.append(
            {"day": day, "events": count, "activeUsers": active, "newUsers": joined.get(day, 0)}
        )
    return series


def _hourly(conn, days: int) -> list[dict]:
    counts = dict(
        conn.execute(
            "SELECT hour, COUNT(*) FROM usage_events WHERE day >= ? GROUP BY hour",
            (_day(days - 1),),
        ).fetchall()
    )
    return [{"hour": h, "events": counts.get(h, 0)} for h in range(24)]


# --- GIOI THIEU ---


def _referrals(conn) -> dict:
    attributed = conn.execute(
        "SELECT COUNT(*) FROM bot_users WHERE referred_by IS NOT NULL"
    ).fetchone()[0]
    exact = conn.execute(
        "SELECT COUNT(*) FROM bot_users WHERE ref_confidence = 'exact'"
    ).fetchone()[0]
    inviters = conn.execute(
        "SELECT COUNT(DISTINCT referred_by) FROM bot_users WHERE referred_by IS NOT NULL"
    ).fetchone()[0]

    by_source = [
        {"source": r["ref_source"], "count": r["n"]}
        for r in conn.execute(
            "SELECT ref_source, COUNT(*) AS n FROM bot_users WHERE ref_source IS NOT NULL "
            "GROUP BY ref_source ORDER BY n DESC"
        ).fetchall()
    ]

    top = [
        {
            "name": r["display_name"],
            "platform": r["platform"],
            "code": r["ref_code"],
            "invited": r["invited"],
        }
        for r in conn.execute(
            "SELECT u.display_name, u.platform, u.ref_code, COUNT(i.id) AS invited "
            "FROM bot_users u JOIN bot_users i ON i.referred_by = u.id "
            "GROUP BY u.id ORDER BY invited DESC, u.first_seen_at LIMIT ?",
            (TOP_LIMIT,),
        ).fetchall()
    ]

    recent = [
        {
            "invitee": r["invitee"],
            "inviter": r["inviter"],
            "platform": r["platform"],
            "source": r["ref_source"],
            "confidence": r["ref_confidence"],
            "at": r["referred_at"],
        }
        for r in conn.execute(
            "SELECT i.display_name AS invitee, u.display_name AS inviter, i.platform, "
            "       i.ref_source, i.ref_confidence, i.referred_at "
            "FROM bot_users i JOIN bot_users u ON u.id = i.referred_by "
            "ORDER BY i.referred_at DESC LIMIT ?",
            (TOP_LIMIT,),
        ).fetchall()
    ]

    return {
        "attributed": attributed,
        "exact": exact,
        "inferred": attributed - exact,
        "inviters": inviters,
        # K-factor: trung binh moi nguoi tung moi duoc it nhat 1 nguoi thi keo ve bao
        # nhieu nguoi. Chua co ai moi duoc thi de 0 chu khong chia cho 0.
        "kFactor": round(attributed / inviters, 2) if inviters else 0,
        "bySource": by_source,
        "topReferrers": top,
        "recent": recent,
    }


# --- LENH & NHOM ---


def _top_commands(conn, days: int) -> list[dict]:
    rows = conn.execute(
        "SELECT command, COUNT(*) AS n FROM usage_events "
        "WHERE command IS NOT NULL AND day >= ? GROUP BY command ORDER BY n DESC LIMIT ?",
        (_day(days - 1), TOP_LIMIT),
    ).fetchall()
    return [{"command": r["command"], "count": r["n"]} for r in rows]


def _top_chats(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT c.chat_key, c.platform, c.title, "
        "       (SELECT COUNT(*) FROM chat_members m WHERE m.chat_key = c.chat_key) AS members, "
        "       (SELECT COUNT(*) FROM rounds r JOIN sessions s ON s.id = r.session_id "
        "        WHERE s.chat_key = c.chat_key AND r.voided = 0) AS rounds, "
        "       (SELECT MAX(at) FROM usage_events e WHERE e.chat_key = c.chat_key) AS last_at "
        "FROM chats c ORDER BY rounds DESC, members DESC LIMIT ?",
        (TOP_LIMIT,),
    ).fetchall()
    return [
        {
            "title": r["title"],
            "platform": r["platform"],
            "members": r["members"],
            "rounds": r["rounds"],
            "lastActiveAt": r["last_at"],
        }
        for r in rows
    ]
