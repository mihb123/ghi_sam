"""Test 3 luat gan nguon gioi thieu + cac guard chong sai du lieu.

Xem ghibai/tracking.py: link (exact) > cung nhom (inferred) > click trang moi (inferred).
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone

import pytest

from ghibai.core import Engine, Incoming
from ghibai.db import Database
from ghibai.render import TelegramFmt, ZaloFmt
from ghibai.sheets import SheetExporter
from ghibai.tracking import Tracker, split_payload

TG_GROUP = "-1004429201251"
ZL_CHAT = "6ede9afa66b88fe6d6a9"


@pytest.fixture
def engine(tmp_path):
    db = Database(tmp_path / "track.db")
    exporter = SheetExporter(tmp_path / "missing_sa.json", "Chi tiet van")
    yield Engine(
        db,
        exporter,
        tracker=Tracker(db, click_window_min=30),
        bot_username="ghibai_bot",
        web_public_url="https://sam.mihb.site",
        admin_ids={"telegram": frozenset({"1"})},
    )
    db.close()


def say(engine, text, uid, chat, name="Ai do", platform="telegram"):
    fmt = TelegramFmt() if platform == "telegram" else ZaloFmt()
    return asyncio.run(
        engine.handle(
            Incoming(
                platform=platform,
                native_chat_id=chat,
                chat_title="Nhom",
                text=text,
                author=name,
                native_user_id=uid,
            ),
            fmt,
        )
    )


def plain(text: str) -> str:
    return re.sub(r"</?(b|i|u|s|pre|code)>", "", text)


def user(engine, uid, platform="telegram"):
    return engine.db.user_by_native_id(platform, uid)


def code_of(engine, uid, platform="telegram"):
    return user(engine, uid, platform).ref_code


# --- TACH MA KHOI /start ---


def test_split_payload_nhan_ca_gach_duoi_va_gach_ngang():
    assert split_payload("r_ab12cd") == ("AB12CD", "")
    assert split_payload("r-AB12CD") == ("AB12CD", "")
    assert split_payload("r_AB12CD sam") == ("AB12CD", "sam")


def test_split_payload_bo_qua_arg_thuong():
    assert split_payload("sam") == (None, "sam")
    assert split_payload("") == (None, "")


def test_start_kem_ma_van_ra_huong_dan(engine):
    say(engine, "/chiase", "1", "1")
    replies = say(engine, f"/start r_{code_of(engine, '1')}", "2", "2")
    assert "Bot ghi điểm 3 cây" in plain(replies[0])


# --- LUAT 1: LINK CHIA SE ---


def test_deep_link_gan_dung_nguoi_gioi_thieu(engine):
    say(engine, "/chiase", "1", "1", name="Minh")
    say(engine, f"/start r_{code_of(engine, '1')}", "2", "2", name="Nam")

    invitee = user(engine, "2")
    assert invitee.referred_by == user(engine, "1").id
    assert (invitee.ref_source, invitee.ref_confidence) == ("link", "exact")


def test_ma_khong_ton_tai_thi_khong_gan_ai(engine):
    say(engine, "/start r_KHONGCO", "2", "2")
    assert user(engine, "2").referred_by is None


def test_ma_trong_nhom_van_bat_duoc(engine):
    # Deep link ?startgroup= gui '/start@bot r_XXX' vao nhom; regex lenh da bo phan @bot.
    say(engine, "/chiase", "1", "1")
    say(engine, f"/start@ghibai_bot r_{code_of(engine, '1')}", "2", TG_GROUP)
    assert user(engine, "2").ref_source == "link"


# --- LUAT 2: CUNG NHOM ---


def test_nguoi_moi_trong_nhom_quy_ve_nguoi_som_nhat(engine):
    say(engine, "/start", "1", TG_GROUP, name="Minh")
    say(engine, "/tong", "2", TG_GROUP, name="Nam")

    invitee = user(engine, "2")
    assert invitee.referred_by == user(engine, "1").id
    assert (invitee.ref_source, invitee.ref_confidence) == ("group", "inferred")


def test_nguoi_dau_tien_cua_nhom_khong_co_nguon(engine):
    say(engine, "/start", "1", TG_GROUP)
    assert user(engine, "1").referred_by is None


# --- LUAT 3: CLICK TRANG MOI ---


def test_click_duy_nhat_gan_cho_user_moi(engine):
    say(engine, "/chiase", "1", "1")
    engine.tracker.note_click(code_of(engine, "1"))

    say(engine, "#start", "zalo-9", ZL_CHAT, platform="zalo")
    invitee = user(engine, "zalo-9", "zalo")
    assert invitee.referred_by == user(engine, "1").id
    assert (invitee.ref_source, invitee.ref_confidence) == ("landing", "inferred")


def test_click_da_nhan_thi_khong_gan_cho_nguoi_tiep_theo(engine):
    say(engine, "/chiase", "1", "1")
    engine.tracker.note_click(code_of(engine, "1"))
    say(engine, "#start", "zalo-9", ZL_CHAT, platform="zalo")

    say(engine, "#start", "zalo-8", "chat-khac", platform="zalo")
    assert user(engine, "zalo-8", "zalo").referred_by is None


def test_hai_ma_cung_cua_so_thi_bo_qua(engine):
    say(engine, "/chiase", "1", "1")
    say(engine, "/chiase", "2", "2")
    engine.tracker.note_click(code_of(engine, "1"))
    engine.tracker.note_click(code_of(engine, "2"))

    say(engine, "#start", "zalo-9", ZL_CHAT, platform="zalo")
    assert user(engine, "zalo-9", "zalo").referred_by is None


def test_click_qua_cua_so_thoi_gian_thi_bo_qua(engine):
    say(engine, "/chiase", "1", "1")
    engine.tracker.note_click(code_of(engine, "1"))
    old = (datetime.now(timezone.utc).astimezone() - timedelta(hours=2)).isoformat(
        timespec="seconds"
    )
    engine.db.conn.execute("UPDATE ref_clicks SET at = ?", (old,))
    engine.db.conn.commit()

    say(engine, "#start", "zalo-9", ZL_CHAT, platform="zalo")
    assert user(engine, "zalo-9", "zalo").referred_by is None


def test_note_click_ma_sai_khong_ghi_gi(engine):
    assert engine.tracker.note_click("KHONGCO") is None
    assert engine.db.conn.execute("SELECT COUNT(*) FROM ref_clicks").fetchone()[0] == 0


# --- GUARD ---


def test_khong_tu_gioi_thieu_chinh_minh(engine):
    say(engine, "/chiase", "1", "1")
    say(engine, f"/start r_{code_of(engine, '1')}", "1", "1")
    assert user(engine, "1").referred_by is None


def test_khong_tao_vong_trong_cay(engine):
    say(engine, "/chiase", "1", "1")
    say(engine, f"/start r_{code_of(engine, '1')}", "2", "2")
    say(engine, "/chiase", "2", "2")

    # 1 bam link cua 2, nhung 2 da la con cua 1 -> gan vao la thanh vong.
    say(engine, f"/start r_{code_of(engine, '2')}", "1", "1")
    assert user(engine, "1").referred_by is None


def test_nang_cap_tu_suy_doan_len_chac_chan(engine):
    say(engine, "/start", "1", TG_GROUP)
    say(engine, "/tong", "2", TG_GROUP)
    assert user(engine, "2").ref_confidence == "inferred"

    say(engine, "/chiase", "3", "3")
    say(engine, f"/start r_{code_of(engine, '3')}", "2", "2")

    invitee = user(engine, "2")
    assert invitee.referred_by == user(engine, "3").id
    assert (invitee.ref_source, invitee.ref_confidence) == ("link", "exact")


def test_khong_ghi_de_nguon_da_chac_chan(engine):
    say(engine, "/chiase", "1", "1")
    say(engine, f"/start r_{code_of(engine, '1')}", "2", "2")
    first = user(engine, "2").referred_by

    say(engine, "/chiase", "3", "3")
    say(engine, f"/start r_{code_of(engine, '3')}", "2", "2")
    assert user(engine, "2").referred_by == first


# --- KHONG CO USER ID ---


def test_thieu_user_id_thi_bot_van_chay_binh_thuong(engine):
    replies = asyncio.run(
        engine.handle(
            Incoming("telegram", TG_GROUP, "Nhom", "/nguoichoi Huong, Hang", "Huong"),
            TelegramFmt(),
        )
    )
    assert "Người chơi" in plain(replies[0])
    assert engine.db.conn.execute("SELECT COUNT(*) FROM bot_users").fetchone()[0] == 0


# --- LENH /chiase ---


def test_chiase_tra_deep_link_telegram(engine):
    reply = plain(say(engine, "/chiase", "1", "1")[0])
    assert f"https://t.me/ghibai_bot?start=r_{code_of(engine, '1')}" in reply


def test_chiase_tra_link_trang_moi_cho_zalo(engine):
    reply = plain(say(engine, "#chiase", "zalo-1", ZL_CHAT, platform="zalo")[0])
    code = code_of(engine, "zalo-1", "zalo")
    assert f"https://sam.mihb.site/i/{code}" in reply


def test_chiase_dem_so_nguoi_da_moi(engine):
    say(engine, "/chiase", "1", "1")
    say(engine, f"/start r_{code_of(engine, '1')}", "2", "2")
    assert "1 người" in plain(say(engine, "/chiase", "1", "1")[0])


def test_chiase_thieu_username_thi_huong_dan_dat_env(tmp_path):
    db = Database(tmp_path / "no-name.db")
    engine = Engine(
        db,
        SheetExporter(tmp_path / "missing_sa.json", "x"),
        tracker=Tracker(db),
    )
    assert "TELEGRAM_BOT_USERNAME" in plain(say(engine, "/chiase", "1", "1")[0])
    db.close()


# --- LENH /thongke ---


def test_thongke_chan_nguoi_thuong_va_chi_ra_user_id(engine):
    reply = plain(say(engine, "/thongke", "999", "999")[0])
    assert "chỉ dành cho người quản trị" in reply
    assert "999" in reply


def test_thongke_cho_admin_thay_so_lieu(engine):
    say(engine, "/start", "1", TG_GROUP)
    reply = plain(say(engine, "/thongke", "1", TG_GROUP)[0])
    assert "Thống kê bot" in reply
    assert "Giới thiệu" in reply


# --- LOG LUU LUONG ---


def test_chi_ghi_log_khi_bot_thuc_su_lam_gi(engine):
    say(engine, "/tong", "1", TG_GROUP)
    say(engine, "chuyện ngoài lề trong nhóm", "1", TG_GROUP)

    rows = engine.db.conn.execute("SELECT kind, command FROM usage_events").fetchall()
    assert [tuple(r) for r in rows] == [("command", "tong")]
    # Tin nhan tan gau van tinh vao msg_count de biet nguoi do con hoat dong.
    assert engine.db.conn.execute(
        "SELECT msg_count FROM bot_users WHERE native_user_id = '1'"
    ).fetchone()[0] == 2


def test_ghi_log_van_va_lenh_sai(engine):
    say(engine, "/nguoichoi Huong, Hang, Toan", "1", TG_GROUP)
    say(engine, "/banmoi 3cay", "1", TG_GROUP)
    say(engine, "-5, 5, c", "1", TG_GROUP)
    say(engine, "/khonghecolenhnay", "1", TG_GROUP)

    kinds = {
        r["kind"]: r["ok"]
        for r in engine.db.conn.execute("SELECT DISTINCT kind, ok FROM usage_events")
    }
    assert kinds["round"] == 1
    assert kinds["unknown_command"] == 0
