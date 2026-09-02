"""Test tong hop so lieu: DAU/MAU, K-factor, top nguoi moi, chuoi 30 ngay."""

from datetime import datetime, timedelta, timezone

import pytest

from ghibai import stats
from ghibai.db import Database


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "stats.db")
    yield database
    database.close()


def add_user(db, native_id, name, platform="telegram", days_ago=0):
    user, _ = db.upsert_user(platform, native_id, name)
    if days_ago:
        moment = (
            datetime.now(timezone.utc).astimezone() - timedelta(days=days_ago)
        ).isoformat(timespec="seconds")
        db.conn.execute(
            "UPDATE bot_users SET first_seen_at = ? WHERE id = ?", (moment, user.id)
        )
        db.conn.commit()
    return db.user(user.id)


# Log 1 luot dung roi doi ngay ve qua khu: cac chi so theo ngay deu doc cot `day`.
def add_event(db, user_id, days_ago=0, command="tong", platform="telegram"):
    db.log_event(platform=platform, kind="command", user_id=user_id, command=command)
    if days_ago:
        moment = datetime.now(timezone.utc).astimezone() - timedelta(days=days_ago)
        db.conn.execute(
            "UPDATE usage_events SET day = ?, at = ? WHERE id = (SELECT MAX(id) FROM usage_events)",
            (moment.strftime("%Y-%m-%d"), moment.isoformat(timespec="seconds")),
        )
        db.conn.commit()


def test_dau_wau_mau_tach_dung_theo_moc_thoi_gian(db):
    hom_nay = add_user(db, "1", "Minh")
    tuan_nay = add_user(db, "2", "Nam")
    thang_nay = add_user(db, "3", "Cuong")
    add_user(db, "4", "Lâu rồi")

    add_event(db, hom_nay.id)
    add_event(db, tuan_nay.id, days_ago=3)
    add_event(db, thang_nay.id, days_ago=20)

    data = stats.overview(db)["users"]
    assert (data["dau"], data["wau"], data["mau"]) == (1, 2, 3)


def test_user_moi_dem_theo_ngay_dang_ky(db):
    add_user(db, "1", "Hôm nay")
    add_user(db, "2", "3 ngày trước", days_ago=3)
    add_user(db, "3", "40 ngày trước", days_ago=40)

    data = stats.overview(db)["users"]
    assert data["newToday"] == 1
    assert data["new7d"] == 2
    assert data["new30d"] == 2


def test_k_factor_va_top_nguoi_moi(db):
    a = add_user(db, "1", "Minh")
    b = add_user(db, "2", "Nam")
    c = add_user(db, "3", "Cuong")
    d = add_user(db, "4", "Dung")

    db.set_referrer(b.id, a.id, "link", "exact")
    db.set_referrer(c.id, a.id, "group", "inferred")
    db.set_referrer(d.id, b.id, "link", "exact")

    refs = stats.overview(db)["referrals"]
    assert refs["attributed"] == 3
    assert (refs["exact"], refs["inferred"]) == (2, 1)
    # 3 nguoi co nguon / 2 nguoi tung moi duoc = 1.5
    assert (refs["inviters"], refs["kFactor"]) == (2, 1.5)
    assert [r["name"] for r in refs["topReferrers"]] == ["Minh", "Nam"]
    assert refs["topReferrers"][0]["invited"] == 2


def test_k_factor_bang_0_khi_chua_ai_moi_duoc(db):
    add_user(db, "1", "Minh")
    assert stats.overview(db)["referrals"]["kFactor"] == 0


def test_nguon_gan_gan_day_xep_moi_truoc(db):
    a = add_user(db, "1", "Minh")
    b = add_user(db, "2", "Nam")
    db.set_referrer(b.id, a.id, "landing", "inferred")

    recent = stats.overview(db)["referrals"]["recent"]
    assert recent[0]["invitee"] == "Nam"
    assert recent[0]["inviter"] == "Minh"
    assert recent[0]["confidence"] == "inferred"


def test_chuoi_ngay_luon_du_30_diem_va_ket_thuc_o_hom_nay(db):
    user = add_user(db, "1", "Minh")
    add_event(db, user.id)
    add_event(db, user.id, days_ago=5)

    daily = stats.overview(db)["daily"]
    hom_nay = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    assert len(daily) == 30
    assert daily[-1]["day"] == hom_nay
    assert daily[-1]["events"] == 1
    assert daily[-6]["events"] == 1
    assert sum(point["events"] for point in daily) == 2


def test_gio_luon_du_24_diem(db):
    assert [p["hour"] for p in stats.overview(db)["hourly"]] == list(range(24))


def test_cat_theo_nen_tang(db):
    add_user(db, "1", "Minh", platform="telegram")
    add_user(db, "z1", "Zalo A", platform="zalo")
    add_user(db, "z2", "Zalo B", platform="zalo")

    by_platform = {p["platform"]: p for p in stats.overview(db)["byPlatform"]}
    assert by_platform["zalo"]["users"] == 2
    assert by_platform["telegram"]["users"] == 1


def test_top_lenh_va_top_nhom(db):
    db.ensure_chat("telegram:-100", "telegram", "-100", "Nhóm A")
    user = add_user(db, "1", "Minh")
    db.touch_member("telegram:-100", user.id)
    for _ in range(3):
        db.log_event(platform="telegram", kind="command", chat_key="telegram:-100",
                     user_id=user.id, command="tong")
    db.log_event(platform="telegram", kind="command", chat_key="telegram:-100",
                 user_id=user.id, command="web")

    data = stats.overview(db)
    assert data["topCommands"][0] == {"command": "tong", "count": 3}
    assert data["topChats"][0]["title"] == "Nhóm A"
    assert data["topChats"][0]["members"] == 1


def test_db_trong_van_tra_ve_du_khoa(db):
    data = stats.overview(db)
    assert data["totals"]["users"] == 0
    assert data["referrals"]["topReferrers"] == []
    assert len(data["daily"]) == 30
