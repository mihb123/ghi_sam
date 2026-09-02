import pytest

from ghibai.db import Player
from ghibai.parser import ParseError, looks_like_round, parse_round
from ghibai.scoring import resolve_scores

NAMES = ["Hương", "Hằng", "Toàn", "Thu"]
NORMS = ["huong", "hang", "toan", "thu"]
SEATS = [Player(i + 1, NAMES[i], NORMS[i], i) for i in range(4)]
HUONG, HANG, TOAN, THU = (p.id for p in SEATS)


def resolve(text, seats=SEATS):
    return resolve_scores(parse_round(text, seats))


# --- 1. CU PHAP THEO VI TRI ---

def test_vi_du_cua_user():
    """-5, 5, , 6  ->  Toan cam chuong va an -6 de tong ve 0."""
    parsed = parse_round("-5, 5, , 6", SEATS)
    assert parsed.mode == "positional"
    assert parsed.banker_id == TOAN
    assert resolve(" -5, 5, , 6 ") == {HUONG: -5, HANG: 5, TOAN: -6, THU: 6}


def test_o_trong_o_cuoi_va_o_dau():
    assert resolve("-5, 5, 6,")[THU] == -6
    assert resolve(", 5, -7, 6")[HUONG] == -4


def test_khong_khoang_trang_va_dau_cong():
    assert resolve("-5,5,,6") == resolve("-5, +5, , +6")


def test_chu_c_thay_cho_o_trong():
    assert resolve("-5, 5, c, 6")[TOAN] == -6
    assert resolve("-5, 5, C, 6")[TOAN] == -6


def test_diem_0_la_diem_that_khong_phai_dau_cam_chuong():
    scores = resolve("-5, 5, , 0")
    assert scores[THU] == 0
    assert scores[TOAN] == 0
    assert sum(scores.values()) == 0


def test_x_la_nguoi_bo_van():
    parsed = parse_round("-5, 5, , x", SEATS)
    assert parsed.sat_out == [THU]
    assert resolve("-5, 5, , x") == {HUONG: -5, HANG: 5, TOAN: 0}


def test_sai_so_o():
    with pytest.raises(ParseError, match="4 chỗ nhưng bạn nhập 3 ô"):
        parse_round("-5, 5, ", SEATS)


def test_hai_o_trong():
    with pytest.raises(ParseError, match="2 ô trống"):
        parse_round("-5, , , 6", SEATS)


def test_khong_co_o_trong():
    with pytest.raises(ParseError, match="Chưa đánh dấu người cầm chương"):
        parse_round("-5, 5, -7, 6", SEATS)


def test_o_rac():
    with pytest.raises(ParseError, match="không hiểu"):
        parse_round("-5, 5, ?, 6", SEATS)


# --- 2. CU PHAP THEO TEN ---

def test_ten_tran_la_cam_chuong():
    assert resolve("Hương -5, Hằng 5, Toàn, Thu 6")[TOAN] == -6


def test_ten_khong_dau_va_khong_phan_biet_hoa_thuong():
    assert resolve("huong -5, HANG 5, toan, thu 6")[TOAN] == -6


def test_dau_sao_danh_dau_chuong():
    parsed = parse_round("Toàn*, Hương -5, Hằng 5, Thu 6", SEATS)
    assert parsed.banker_id == TOAN


def test_tien_to_c():
    assert parse_round("c:Toàn Hương -5 Hằng 5 Thu 6", SEATS).banker_id == TOAN
    assert parse_round("chuong: Thu, Hương -5, Hằng 5, Toàn -7", SEATS).banker_id == THU


def test_suy_ra_nguoi_thieu_la_chuong():
    parsed = parse_round("Hương -5, Hằng 5, Thu 6", SEATS)
    assert parsed.banker_id == TOAN


def test_khong_khoang_trang_giua_ten_va_so():
    assert resolve("Hương -5 Hằng 5 Toàn Thu 6")[TOAN] == -6


def test_ai_cung_co_diem_thi_khong_ro_chuong():
    with pytest.raises(ParseError, match="không biết ai cầm chương"):
        parse_round("Hương -5, Hằng 5, Toàn -7, Thu 7", SEATS)


def test_thieu_2_nguoi_thi_hoi_lai():
    with pytest.raises(ParseError, match="Không rõ ai cầm chương"):
        parse_round("Hương -5, Hằng 5", SEATS)


def test_chuong_khong_duoc_dien_diem():
    with pytest.raises(ParseError, match="không điền điểm"):
        parse_round("Toàn* 3, Hương -5, Hằng 5, Thu 6", SEATS)


def test_hai_nguoi_cam_chuong():
    with pytest.raises(ParseError, match="2 người cầm chương"):
        parse_round("Toàn*, Thu*, Hương -5, Hằng 5", SEATS)


def test_ten_lap_lai():
    with pytest.raises(ParseError, match="2 lần"):
        parse_round("Hương -5, Hương 5, Toàn, Thu 6", SEATS)


def test_ten_la():
    with pytest.raises(ParseError, match="Không nhận ra"):
        parse_round("Hương -5, Nam 5, Toàn, Thu 6", SEATS)


def test_ten_nhieu_tu():
    seats = [
        Player(1, "Thu Hà", "thu ha", 0),
        Player(2, "Thu", "thu", 1),
        Player(3, "Toàn", "toan", 2),
    ]
    parsed = parse_round("Thu Hà -5, Thu 8, Toàn", seats)
    assert parsed.banker_id == 3
    assert parsed.scores == {1: -5, 2: 8}


# --- 3. NHAN DIEN TIN NHAN TRAN ---

@pytest.mark.parametrize(
    "text",
    ["-5, 5, , 6", "-5,5,,6", "0, 0, , 0", "Hương -5, Hằng 5, Toàn, Thu 6"],
)
def test_nhan_dien_la_van(text):
    assert looks_like_round(text, SEATS)


@pytest.mark.parametrize(
    "text",
    [
        "tối nay đánh tiếp không",
        "Hương thắng đậm quá",
        "ok",
        "5",
        "",
        "đi ăn đi mọi người",
        "https://docs.google.com/spreadsheets/d/abc123/edit",
    ],
)
def test_bo_qua_chat_thuong(text):
    assert not looks_like_round(text, SEATS)


def test_ban_2_nguoi():
    seats = [Player(1, "A", "a", 0), Player(2, "B", "b", 1)]
    assert resolve("-7,", seats) == {1: -7, 2: 7}
    assert resolve(", -7", seats) == {1: 7, 2: -7}
