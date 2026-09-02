"""Test Engine dung chung cho ca 2 nen tang: Telegram prefix '/', Zalo prefix '#'."""

import asyncio
import re

import pytest

from ghibai.core import Engine, Incoming
from ghibai.db import Database
from ghibai.render import TelegramFmt, ZaloFmt
from ghibai.sheets import SheetExporter

TG_CHAT = "-1004429201251"
ZL_CHAT = "6ede9afa66b88fe6d6a9"


def plain(text: str) -> str:
    return re.sub(r"</?(b|i|u|s|pre|code)>", "", text)


@pytest.fixture
def engine(tmp_path):
    db = Database(tmp_path / "core.db")
    exporter = SheetExporter(tmp_path / "missing_sa.json", "Chi tiet van")
    yield Engine(db, exporter, default_sheet_url=None)
    db.close()


def say_raw(engine, text, platform="telegram", chat=None, author="Hương"):
    fmt = TelegramFmt() if platform == "telegram" else ZaloFmt()
    chat_id = chat or (TG_CHAT if platform == "telegram" else ZL_CHAT)
    return asyncio.run(
        engine.handle(
            Incoming(
                platform=platform,
                native_chat_id=chat_id,
                chat_title="Ghi sổ",
                text=text,
                author=author,
            ),
            fmt,
        )
    )


def say(engine, text, platform="telegram", chat=None, author="Hương"):
    return [plain(r) for r in say_raw(engine, text, platform, chat, author)]


def setup_ban(engine, platform="telegram"):
    p = "/" if platform == "telegram" else "#"
    say(engine, f"{p}nguoichoi Hương, Hằng, Toàn, Thu", platform)


# --- 1. PREFIX THEO NEN TANG ---

def test_zalo_dung_dau_thang(engine):
    out = say(engine, "#help", "zalo")[0]
    assert "#nguoichoi" in out and "#export" in out
    assert "/nguoichoi" not in out


def test_telegram_dung_dau_gach_cheo(engine):
    out = say(engine, "/help", "telegram")[0]
    assert "/nguoichoi" in out and "/export" in out
    assert "#nguoichoi" not in out


def test_ca_hai_prefix_deu_chay_o_moi_nen_tang(engine):
    setup_ban(engine, "zalo")
    assert "Nguoi choi" in say(engine, "/dsnguoi", "zalo")[0]
    setup_ban(engine, "telegram")
    assert "Nguoi choi" in say(engine, "#dsnguoi", "telegram")[0]


def test_lenh_khong_ton_tai(engine):
    out = say(engine, "#abcxyz", "zalo")[0]
    assert "Khong co lenh #abcxyz" in out and "#help" in out


# --- 2. GHI VAN ---

def test_ghi_van_tren_zalo(engine):
    setup_ban(engine, "zalo")
    out = say(engine, "-5, 5, , 6", "zalo")[0]
    assert "Da ghi van 1" in out
    assert "Toàn* -6" in out


def test_ghi_van_tu_dong_mo_ban(engine):
    setup_ban(engine)
    assert "tu mo ban moi" in say(engine, "-5, 5, , 6")[0]


def test_lenh_v_voi_ca_hai_prefix(engine):
    setup_ban(engine)
    assert "Da ghi van 1" in say(engine, "/v -5, 5, , 6")[0]
    assert "Da ghi van 2" in say(engine, "#v 3, -4, , 1")[0]


def test_ghi_van_phan_hoi_gon_2_dong(engine):
    say(engine, "/nguoichoi Huong, Hang, Toan, Thu", "telegram")
    say(engine, "1, -1, , 0", "telegram")
    out_tg = say(engine, "10,10,,-40", "telegram")[0]
    assert out_tg == "✅ Da ghi van 2\nHuong +10 | Hang +10 | Toan* +20 | Thu -40"

    say(engine, "#nguoichoi Huong, Hang, Toan, Thu", "zalo")
    say(engine, "1, -1, , 0", "zalo")
    out_zl = say(engine, "10,10,,-40", "zalo")[0]
    assert out_zl == "✅ Da ghi van 2\nHuong +10 | Hang +10 | Toan* +20 | Thu -40"


def test_chat_thuong_bi_bo_qua(engine):
    setup_ban(engine, "zalo")
    for noise in ["tối nay đánh tiếp không", "Hương thắng đậm quá", "ok", "5"]:
        assert say(engine, noise, "zalo") == []


def test_chua_khai_bao_nguoi_choi(engine):
    assert "Khai bao nguoi choi truoc" in say(engine, "#v -5, 5, , 6", "zalo")[0]


def test_nhap_sai_bao_loi_ro(engine):
    setup_ban(engine, "zalo")
    assert "4 cho nhung ban nhap 3 o" in say(engine, "#v -5, 5, ", "zalo")[0]


# --- 3. XOA / SUA ---

def test_undo_va_xoa_va_khoi_phuc(engine):
    setup_ban(engine, "zalo")
    for text in ["-5, 5, , 6", "3, -4, , 1", "1, 1, , 1"]:
        say(engine, text, "zalo")

    assert "Da xoa van 3" in say(engine, "#undo", "zalo")[0]
    assert "Da xoa van 1" in say(engine, "#xoa 1", "zalo")[0]
    assert "Da khoi phuc van 1" in say(engine, "#khoiphuc 1", "zalo")[0]
    assert "Van dang bi xoa: 3" in say(engine, "#khoiphuc", "zalo")[0]


def test_sua_van(engine):
    setup_ban(engine, "zalo")
    say(engine, "-5, 5, , 6", "zalo")
    out = say(engine, "#sua 1 1, 1, , 1", "zalo")[0]
    assert "Da sua van 1" in out and "Hương +1" in out


def test_xoaban_can_xac_nhan(engine):
    setup_ban(engine, "zalo")
    say(engine, "-5, 5, , 6", "zalo")
    assert "neu chac chan" in say(engine, "#xoaban", "zalo")[0]
    assert "Da xoa 1 van" in say(engine, "#xoaban xacnhan", "zalo")[0]


# --- 4. TACH BIET GIUA NEN TANG ---

def test_telegram_va_zalo_hoan_toan_doc_lap(engine):
    setup_ban(engine, "telegram")
    say(engine, "/nguoichoi An, Binh", "telegram")
    say(engine, "#nguoichoi Hương, Hằng, Toàn, Thu", "zalo")

    assert "An" in say(engine, "/dsnguoi", "telegram")[0]
    assert "Hương" in say(engine, "#dsnguoi", "zalo")[0]
    assert "An" not in say(engine, "#dsnguoi", "zalo")[0]


def test_allowlist_bao_kem_chat_id_that(tmp_path):
    db = Database(tmp_path / "a.db")
    engine = Engine(
        db,
        SheetExporter(tmp_path / "none.json", "t"),
        allowed_chats={"zalo": frozenset({"chi-chat-nay"})},
    )
    out = say(engine, "#help", "zalo")[0]
    assert "chua duoc phep" in out
    assert ZL_CHAT in out and "ZALO_CHAT_ID" in out
    assert say(engine, "-5, 5, , 6", "zalo") == []  # chat thuong thi im lang
    assert "Bot ghi diem" in say(engine, "#help", "zalo", chat="chi-chat-nay")[0]
    db.close()


# --- 5. GOOGLE SHEET ---

def test_export_chua_co_ban(engine):
    setup_ban(engine, "zalo")
    assert "Khong co ban nao dang mo" in say(engine, "#export", "zalo")[0]


def test_sheet_link_sai(engine):
    assert "khong hop le" in say(engine, "#sheet abc", "zalo")[0]


def test_sheet_luu_link_va_nhac_share(engine):
    url = "https://docs.google.com/spreadsheets/d/1KsAUkCFLH4OmQWvEjjLazITxtsb0-gK3Fd2LE9pi6Uw/edit"
    assert "Da luu link sheet" in say(engine, f"#sheet {url}", "zalo")[0]
    assert url in say(engine, "#sheet", "zalo")[0]


def test_telegram_html_entities_hop_le(engine):
    import xml.etree.ElementTree as ET

    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "code", "pre", "blockquote", "root"}

    def validate_tg_html(html: str):
        # Telegram HTML requires valid XML-like tags among allowed tags
        root = ET.fromstring(f"<root>{html}</root>")
        for elem in root.iter():
            assert elem.tag in allowed_tags, f"Tag khong hop le trong Telegram: <{elem.tag}>"

    # Test all common commands in Telegram format
    commands = [
        "/help",
        "/nguoichoi Hương, Hằng, Toàn, Thu",
        "/dsnguoi",
        "/themnguoi Nam",
        "/xoanguoi Nam",
        "/banmoi",
        "-5, 5, , 6",
        "/v 3, -4, , 1",
        "/sua 1 -5, 5, , 6",
        "/bang",
        "/lichsu",
        "/xh",
        "/xoaban",
        "/xoa 1",
        "/khoiphuc",
        "/sheet",
        "/export",
    ]
    for cmd in commands:
        for reply in say_raw(engine, cmd, platform="telegram"):
            validate_tg_html(reply)

