"""Test API cho trang web: token trong link, payload, va phuc vu file build."""

import asyncio
import json
import re

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ghibai import webserver
from ghibai.core import Engine, Incoming
from ghibai.db import Database
from ghibai.render import TelegramFmt
from ghibai.sheets import SheetExporter
from ghibai.webapi import WebApi

CHAT = "-1004429201251"
OTHER_CHAT = "-1009999999999"


@pytest.fixture
def engine(tmp_path):
    db = Database(tmp_path / "web.db")
    exporter = SheetExporter(tmp_path / "missing_sa.json", "Chi tiet van")
    yield Engine(db, exporter, web_public_url="https://sam.mihb.site")
    db.close()


def say(engine, text, chat=CHAT):
    return asyncio.run(
        engine.handle(
            Incoming("telegram", chat, "Ghi so", text, "Huong"), TelegramFmt()
        )
    )


def seed(engine, chat=CHAT):
    say(engine, "/nguoichoi Huong, Hang, Toan, Thu", chat)
    say(engine, "/banmoi toi thu 7", chat)
    say(engine, "-5, 5, , 6", chat)
    say(engine, "-2, -3, 4, ", chat)


def token_of(engine, chat=CHAT):
    return engine.db.get_or_create_web_token(f"telegram:{chat}")


async def get(app, path):
    async with TestClient(TestServer(app)) as client:
        async with client.get(path) as response:
            return response.status, await response.read()


# Moi request mot Application moi: aiohttp gan Application vao event loop dau tien
# dung no, ma moi asyncio.run lai tao mot loop khac.
def call(build, path):
    return asyncio.run(get(build(), path))


def api_app(engine, dist=None):
    return lambda: webserver.build_app(api=WebApi(engine.db), dist=dist)


def dist_app(dist):
    return lambda: webserver.build_app(dist=dist)


def board(engine):
    status, body = call(api_app(engine), f"/api/board?k={token_of(engine)}")
    return status, json.loads(body)


# --- TOKEN ---


def test_lenh_web_tra_link_kem_token(engine):
    say(engine, "/nguoichoi Huong, Hang")
    reply = say(engine, "/web")[0]
    match = re.search(r"https://sam\.mihb\.site/\?k=(\S+)", reply)
    assert match
    assert match.group(1) == token_of(engine)


def test_token_khong_doi_giua_cac_lan_goi(engine):
    say(engine, "/nguoichoi Huong, Hang")
    assert say(engine, "/web")[0] == say(engine, "/web")[0]


def test_doilink_sinh_token_moi_va_bo_token_cu(engine):
    say(engine, "/nguoichoi Huong, Hang")
    old = token_of(engine)
    say(engine, "/web doilink")
    new = token_of(engine)
    assert new != old
    assert engine.db.chat_by_web_token(old) is None


def test_khong_co_web_public_url_thi_bao_cach_bat(tmp_path):
    db = Database(tmp_path / "nourl.db")
    quiet = Engine(db, SheetExporter(tmp_path / "sa.json", "Tab"))
    assert "WEB_PUBLIC_URL" in say(quiet, "/web")[0]
    db.close()


def test_moi_chat_mot_token_rieng(engine):
    say(engine, "/nguoichoi Huong, Hang", CHAT)
    say(engine, "/nguoichoi Nam, Binh", OTHER_CHAT)
    assert token_of(engine, CHAT) != token_of(engine, OTHER_CHAT)


# --- API ---


def test_thieu_token_hoac_token_sai_deu_tra_404(engine):
    seed(engine)
    assert call(lambda: webserver.build_app(api=WebApi(engine.db)), "/api/board")[0] == 404
    assert call(lambda: webserver.build_app(api=WebApi(engine.db)), "/api/board?k=khong-ton-tai")[0] == 404


def test_token_chi_thay_ban_cua_chinh_nhom_do(engine):
    seed(engine, CHAT)
    seed(engine, OTHER_CHAT)
    say(engine, "-1, 1, , 0", OTHER_CHAT)

    _, body = call(api_app(engine), f"/api/board?k={token_of(engine, CHAT)}")
    assert json.loads(body)["session"]["played"] == 2


def test_payload_du_thong_tin_cho_dashboard(engine):
    seed(engine)
    status, data = board(engine)

    assert status == 200
    assert data["chat"]["title"] == "Ghi so"
    assert data["session"]["live"] is True
    assert data["session"]["note"] == "toi thu 7"
    assert data["session"]["played"] == 2
    assert [p["name"] for p in data["players"]] == ["Huong", "Hang", "Toan", "Thu"]
    # Tong 1 van luon = 0 nen tong ca ban phai = 0.
    assert data["checksum"] == 0
    assert sum(s["total"] for s in data["standings"]) == 0


def test_standings_sap_theo_diem_giam_dan_va_dem_lan_cam_chuong(engine):
    seed(engine)
    _, data = board(engine)

    totals = [s["total"] for s in data["standings"]]
    assert totals == sorted(totals, reverse=True)
    banked = {s["name"]: s["banked"] for s in data["standings"]}
    assert banked == {"Huong": 0, "Hang": 0, "Toan": 1, "Thu": 1}


def test_nguoi_bo_van_khong_co_diem_trong_van_do(engine):
    say(engine, "/nguoichoi Huong, Hang, Toan, Thu")
    say(engine, "-5, 5, , x")
    _, data = board(engine)

    scores = data["rounds"][0]["scores"]
    thu = next(p["id"] for p in data["players"] if p["name"] == "Thu")
    assert str(thu) not in scores
    assert sum(scores.values()) == 0


def test_van_bi_xoa_khong_tinh_diem_nhung_van_bao_da_xoa(engine):
    seed(engine)
    say(engine, "/xoa 2")
    _, data = board(engine)

    assert data["voidedSeqs"] == [2]
    assert [r["seq"] for r in data["rounds"]] == [1]
    assert data["session"]["played"] == 1


def test_ban_da_chot_van_xem_duoc(engine):
    seed(engine)
    say(engine, "/ketthuc")
    _, data = board(engine)

    assert data["session"]["live"] is False
    assert data["session"]["endedAt"]


def test_nhom_chua_choi_van_nao_tra_session_none(engine):
    say(engine, "/nguoichoi Huong, Hang")
    _, data = board(engine)

    assert data["session"] is None
    # Van du moi key de trang web khong phai doan kieu du lieu.
    assert data["standings"] == [] and data["rounds"] == [] and data["players"] == []


# --- FILE BUILD ---


def test_duong_dan_la_tra_ve_index_html_cho_spa(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html>trang")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)")

    app = dist_app(dist)
    assert call(app, "/khong-co-trang-nay") == (200, b"<!doctype html>trang")
    assert call(app, "/assets/app-abc123.js")[1] == b"console.log(1)"


def test_khong_doc_duoc_file_ngoai_thu_muc_build(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("trang")
    (tmp_path / "bimat.txt").write_text("token that")

    assert call(dist_app(dist), "/../bimat.txt") == (200, b"trang")


def test_api_khong_bi_route_spa_nuot(engine, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("trang")
    seed(engine)

    status, body = call(api_app(engine, dist), f"/api/board?k={token_of(engine)}")
    assert status == 200
    assert json.loads(body)["session"]["played"] == 2


def test_payload_game_type_sam(engine):
    say(engine, "/nguoichoi Huong, Hang, Toan, Thu")
    say(engine, "/banmoi sam toi nay")
    say(engine, "-5, -10, , -20")
    status, data = board(engine)
    assert status == 200
    assert data["session"]["gameType"] == "sam"
    assert data["session"]["note"] == "toi nay"
