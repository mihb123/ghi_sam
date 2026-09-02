import re

import pytest

from ghibai.db import Player, Round
from ghibai.text import strip_bot_mention
from ghibai import render
from ghibai.render import TelegramFmt

SEATS = [
    Player(1, "Hương", "huong", 0),
    Player(2, "Hằng", "hang", 1),
    Player(3, "Toàn", "toan", 2),
    Player(4, "Thu", "thu", 3),
]


def plain(html: str) -> str:
    return re.sub(r"</?(b|code|pre)>", "", html)


def test_van_binh_thuong_hien_du_4_nguoi():
    rnd = Round(1, 7, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , 6", {1: -5, 2: 5, 3: -6, 4: 6})
    out = plain(render.round_saved(TelegramFmt(), rnd, SEATS, {1: -5, 2: 5, 3: -6, 4: 6}, 7))
    assert "ván 7" in out
    assert "Hương -5 | Hằng +5 | Toàn* -6 | Thu +6" in out


def test_nguoi_bo_van_van_duoc_neu_ten():
    rnd = Round(1, 1, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , x", {1: -5, 2: 5, 3: 0})
    assert "Thu (bỏ ván)" in plain(render.round_saved(TelegramFmt(), rnd, SEATS, {1: -5, 2: 5, 3: 0}, 1))


def test_bang_diem_co_newline_truoc_bang():
    out = plain(render.standings(TelegramFmt(), SEATS, {1: -5, 2: 5, 3: -6, 4: 6}, 3))
    assert "sau 3 ván\nNgười" in out
    assert out.index("Thu") < out.index("Hương")  # xep theo diem giam dan


def test_canh_bao_khi_tong_khac_0():
    assert "không bằng 0" in plain(render.standings(TelegramFmt(), SEATS, {1: 5, 2: 5}, 1))


def test_lichsu_danh_dau_van_da_xoa():
    rnd = Round(1, 1, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , 6", {1: -5, 2: 5, 3: -6, 4: 6})
    out = plain(render.history(TelegramFmt(), [rnd], SEATS, voided=[4, 5]))
    assert "Đã xóa: ván 4, 5" in out
    assert "20:14" in out


# --- ZALO: khong co <pre> nen layout phai khac han, khong chi doi tag ---

def test_zalo_khong_dung_pre_hay_code():
    from ghibai.render import ZaloFmt

    fmt = ZaloFmt()
    rnd = Round(1, 7, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , 6", {1: -5, 2: 5, 3: -6, 4: 6})
    out = render.round_saved(fmt, rnd, SEATS, {1: -5, 2: 5, 3: -6, 4: 6}, 7)
    out += render.history(fmt, [rnd], SEATS, [])
    out += render.roster(fmt, SEATS)
    assert "<pre>" not in out and "<code>" not in out
    assert "<b>" in out


def test_zalo_lichsu_gom_theo_van():
    from ghibai.render import ZaloFmt

    rnd = Round(1, 7, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , 6", {1: -5, 2: 5, 3: -6, 4: 6})
    out = render.history(ZaloFmt(), [rnd], SEATS, [])
    assert "Ván 7 · 20:14" in out
    assert "Hương -5" in out and "Toàn -6" in out


def test_prefix_lenh_theo_nen_tang():
    from ghibai.render import TelegramFmt, ZaloFmt

    assert TelegramFmt().prefix == "/"
    assert ZaloFmt().prefix == "#"


def test_cat_tin_theo_gioi_han():
    lines = "\n".join(f"dong so {i}" for i in range(500))
    chunks = render.split_message(lines, 200)
    assert all(len(c) <= 200 for c in chunks)
    assert "\n".join(chunks) == lines


def test_khong_cat_khi_du_ngan():
    assert render.split_message("ngan gon", 2000) == ["ngan gon"]


# --- BOC TAG BOT (group Zalo chen "@Ten Bot " vao dau lenh) ---

@pytest.mark.parametrize(
    "text, expected",
    [
        ("@Bot Ghi điểm #help", "#help"),
        ("@bot ghi diem #help", "#help"),          # khong dau, thuong
        ("@Bot Ghi điểm -5, 5, , 6", "-5, 5, , 6"),
        ("@Bot Ghi điểm", ""),
        ("#help", "#help"),                        # khong tag thi giu nguyen
        ("@Ai Do #help", "@Ai Do #help"),          # tag nguoi khac
        ("@Bot Ghi #help", "@Bot Ghi #help"),      # ten khong khop het
    ],
)
def test_strip_bot_mention(text, expected):
    assert strip_bot_mention(text, "Bot Ghi điểm") == expected


def test_strip_bot_mention_khong_biet_ten_bot():
    assert strip_bot_mention("@Bot Ghi điểm #help", None) == "@Bot Ghi điểm #help"


def test_roster_example_khop_so_cho_ngoi():
    from ghibai.render import TelegramFmt, example_round, roster

    fmt = TelegramFmt()
    for count in [2, 3, 4, 7, 9, 12]:
        seats = [Player(i, f"P{i}", f"p{i}", i) for i in range(1, count + 1)]
        out_3c = roster(fmt, seats, game_type="3cay")
        ex_3c = example_round(count, game_type="3cay")
        assert len(ex_3c.split(",")) == count
        assert "c" in [s.strip() for s in ex_3c.split(",")]
        assert ex_3c in out_3c
        assert "người cầm chương" in out_3c

        out_sam = roster(fmt, seats, game_type="sam")
        ex_sam = example_round(count, game_type="sam")
        assert len(ex_sam.split(",")) == count
        assert "c" in [s.strip() for s in ex_sam.split(",")]
        assert ex_sam in out_sam
        assert "người thắng" in out_sam
