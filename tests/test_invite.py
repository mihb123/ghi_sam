"""Test trang moi /i/<ma>: ghi log click, chuyen tiep dung bot, va endpoint /api/stats."""

import asyncio

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ghibai import webserver
from ghibai.db import Database
from ghibai.invite import InvitePages
from ghibai.tracking import Tracker
from ghibai.webapi import WebApi

ADMIN_TOKEN = "token-admin-de-test"
ZALO_LINK = "https://zalo.me/bot/ghibai"


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "invite.db")
    yield database
    database.close()


@pytest.fixture
def owner(db):
    user, _ = db.upsert_user("telegram", "111", "Minh")
    return user


def app_with(db, **invite_kwargs):
    tracker = Tracker(db)
    return lambda: webserver.build_app(
        api=WebApi(db, ADMIN_TOKEN), invite=InvitePages(tracker, **invite_kwargs)
    )


async def _get(app, path):
    async with TestClient(TestServer(app)) as client:
        async with client.get(path, allow_redirects=False) as response:
            return response.status, response.headers.get("Location"), await response.text()


# Moi request mot Application moi: aiohttp gan Application vao event loop dau tien dung
# no, ma moi asyncio.run lai tao mot loop khac (giong test_webapi.py).
def get(build, path):
    return asyncio.run(_get(build(), path))


# --- TRANG MOI ---


def test_chi_bat_telegram_thi_chuyen_thang_kem_ma(db, owner):
    app = app_with(db, telegram_username="ghibai_bot")
    status, location, _ = get(app, f"/i/{owner.ref_code}")

    assert status == 302
    assert location == f"https://t.me/ghibai_bot?start=r_{owner.ref_code}"


def test_bat_ca_hai_thi_hien_trang_cho_chon(db, owner):
    app = app_with(db, telegram_username="ghibai_bot", zalo_bot_link=ZALO_LINK)
    status, location, body = get(app, f"/i/{owner.ref_code}")

    assert status == 200
    assert location is None
    assert f"?start=r_{owner.ref_code}" in body
    assert ZALO_LINK in body


def test_ma_khong_phan_biet_chu_hoa_chu_thuong(db, owner):
    app = app_with(db, telegram_username="ghibai_bot")
    status, _, _ = get(app, f"/i/{owner.ref_code.lower()}")
    assert status == 302


def test_ma_sai_tra_404(db, owner):
    app = app_with(db, telegram_username="ghibai_bot")
    status, _, body = get(app, "/i/KHONGCO")

    assert status == 404
    assert "không còn dùng được" in body


def test_chua_cau_hinh_bot_nao_thi_tra_404(db, owner):
    status, _, _ = get(app_with(db), f"/i/{owner.ref_code}")
    assert status == 404


# --- LOG CLICK ---


def test_mo_trang_la_ghi_mot_click_chua_ai_nhan(db, owner):
    app = app_with(db, telegram_username="ghibai_bot")
    get(app, f"/i/{owner.ref_code}")

    row = db.conn.execute("SELECT ref_code, claimed_by, ua_hash FROM ref_clicks").fetchone()
    assert row["ref_code"] == owner.ref_code
    assert row["claimed_by"] is None
    assert row["ua_hash"]
    assert db.pending_click_codes(30) == [owner.ref_code]


def test_ma_sai_khong_ghi_click(db, owner):
    get(app_with(db, telegram_username="ghibai_bot"), "/i/KHONGCO")
    assert db.conn.execute("SELECT COUNT(*) FROM ref_clicks").fetchone()[0] == 0


# --- API THONG KE ---


def test_stats_can_dung_token(db, owner):
    app = app_with(db, telegram_username="ghibai_bot")
    assert get(app, "/api/stats")[0] == 404
    assert get(app, "/api/stats?k=sai")[0] == 404
    assert get(app, f"/api/stats?k={ADMIN_TOKEN}")[0] == 200


def test_stats_tra_du_khoa_cho_trang_admin(db, owner):
    app = app_with(db, telegram_username="ghibai_bot")
    _, _, body = get(app, f"/api/stats?k={ADMIN_TOKEN}")

    import json

    data = json.loads(body)
    assert set(data) == {
        "generatedAt",
        "totals",
        "users",
        "byPlatform",
        "daily",
        "hourly",
        "referrals",
        "topCommands",
        "topChats",
    }
    assert data["totals"]["users"] == 1


def test_chua_dat_token_thi_tat_han_endpoint(db, owner):
    assert get(lambda: webserver.build_app(api=WebApi(db, None)), "/api/stats?k=bat-ky")[0] == 404
