import pytest

from ghibai.db import Database, chat_key
from ghibai.parser import parse_round
from ghibai.scoring import resolve_scores

CHAT = chat_key("telegram", -100123)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.ensure_chat(CHAT, "telegram", -100123, "Bàn nhà Hương")
    yield database
    database.close()


@pytest.fixture
def session(db):
    seats = db.set_roster(CHAT, ["Hương", "Hằng", "Toàn", "Thu"])
    return db.open_session(CHAT, [p.id for p in seats])


def ghi(db, session, text):
    seats = [db.get_players_by_ids(session.seat_ids)[i] for i in session.seat_ids]
    parsed = parse_round(text, seats)
    return db.add_round(session.id, parsed.banker_id, resolve_scores(parsed), text)


def test_chat_key_gom_platform():
    assert chat_key("telegram", -100123) == "telegram:-100123"
    assert chat_key("zalo", "6ede9afa66b88fe6d6a9") == "zalo:6ede9afa66b88fe6d6a9"


def test_roster_giu_thu_tu_cho(db):
    seats = db.set_roster(CHAT, ["Hương", "Hằng", "Toàn", "Thu"])
    assert [p.name for p in seats] == ["Hương", "Hằng", "Toàn", "Thu"]
    assert [p.seat for p in seats] == [0, 1, 2, 3]


def test_doi_thu_tu_roster(db):
    db.set_roster(CHAT, ["Hương", "Hằng", "Toàn", "Thu"])
    seats = db.set_roster(CHAT, ["Thu", "Toàn", "Hằng", "Hương"])
    assert [p.name for p in seats] == ["Thu", "Toàn", "Hằng", "Hương"]


def test_xoa_roi_them_lai_nguoi_choi(db):
    db.set_roster(CHAT, ["Hương", "Hằng"])
    db.deactivate_player(CHAT, "hang")
    assert [p.name for p in db.get_roster(CHAT)] == ["Hương"]
    db.add_player(CHAT, "Hằng")
    assert [p.name for p in db.get_roster(CHAT)] == ["Hương", "Hằng"]


def test_ghi_van_va_tong_diem(db, session):
    ghi(db, session, "-5, 5, , 6")
    ghi(db, session, "3, -4, , 1")
    totals = db.session_totals(session.id)
    assert sum(totals.values()) == 0
    assert totals[session.seat_ids[0]] == -2
    assert totals[session.seat_ids[2]] == -6


def test_so_van_tang_dan(db, session):
    assert [ghi(db, session, "-5, 5, , 6").seq for _ in range(3)] == [1, 2, 3]


def test_undo(db, session):
    ghi(db, session, "-5, 5, , 6")
    ghi(db, session, "3, -4, , 1")
    assert db.void_last_round(session.id).seq == 2
    assert len(db.get_rounds(session.id)) == 1
    assert db.session_totals(session.id)[session.seat_ids[0]] == -5


def test_xoa_va_khoi_phuc_van(db, session):
    for _ in range(3):
        ghi(db, session, "-5, 5, , 6")
    assert db.void_round(session.id, 2) is not None
    assert [r.seq for r in db.get_rounds(session.id)] == [1, 3]
    assert db.voided_seqs(session.id) == [2]

    assert db.unvoid_round(session.id, 2) is not None
    assert [r.seq for r in db.get_rounds(session.id)] == [1, 2, 3]
    assert db.voided_seqs(session.id) == []


def test_xoa_van_khong_ton_tai(db, session):
    ghi(db, session, "-5, 5, , 6")
    assert db.void_round(session.id, 99) is None
    assert db.unvoid_round(session.id, 1) is None


def test_xoa_ca_ban(db, session):
    for _ in range(4):
        ghi(db, session, "-5, 5, , 6")
    assert db.void_all_rounds(session.id) == 4
    assert db.get_rounds(session.id) == []
    assert db.session_totals(session.id) == {}


def test_sua_van_giu_nguyen_so_van(db, session):
    ghi(db, session, "-5, 5, , 6")
    ghi(db, session, "3, -4, , 1")
    seats = [db.get_players_by_ids(session.seat_ids)[i] for i in session.seat_ids]
    parsed = parse_round("1, 1, , 1", seats)
    fixed = db.replace_round(session.id, 1, parsed.banker_id, resolve_scores(parsed), "1, 1, , 1")

    assert fixed.seq == 1
    assert len(db.get_rounds(session.id)) == 2
    assert db.session_totals(session.id)[session.seat_ids[0]] == 4


def test_khong_sua_duoc_van_da_xoa(db, session):
    ghi(db, session, "-5, 5, , 6")
    db.void_round(session.id, 1)
    assert db.replace_round(session.id, 1, session.seat_ids[2], {}, "x") is None


def test_telegram_va_zalo_cung_id_van_tach_biet(db, session):
    """Zalo va Telegram co the trung id goc; prefix platform phai giu chung rieng nhau."""
    zalo = chat_key("zalo", -100123)
    db.ensure_chat(zalo, "zalo", -100123, "Nhóm Zalo")
    seats = db.set_roster(zalo, ["X", "Y"])
    zalo_session = db.open_session(zalo, [p.id for p in seats])

    ghi(db, session, "-5, 5, , 6")
    assert db.get_rounds(zalo_session.id) == []
    assert [p.name for p in db.get_roster(zalo)] == ["X", "Y"]
    assert [p.name for p in db.get_roster(CHAT)] == ["Hương", "Hằng", "Toàn", "Thu"]


def test_chot_ban_roi_mo_ban_moi(db, session):
    ghi(db, session, "-5, 5, , 6")
    db.close_session(session.id)
    assert db.active_session(CHAT) is None

    second = db.open_session(CHAT, [p.id for p in db.get_roster(CHAT)])
    assert second.id != session.id
    assert db.get_rounds(second.id) == []


def test_xep_hang_tich_luy_cong_don_nhieu_ban(db, session):
    ghi(db, session, "-5, 5, , 6")
    db.close_session(session.id)
    second = db.open_session(CHAT, [p.id for p in db.get_roster(CHAT)])
    ghi(db, second, "-5, 5, , 6")

    stats = {s["name"]: s for s in db.lifetime_stats(CHAT)}
    assert stats["Hương"]["total"] == -10
    assert stats["Hương"]["rounds"] == 2
    assert stats["Toàn"]["banker_rounds"] == 2
    assert sum(s["total"] for s in stats.values()) == 0
