import pytest

from ghibai.db import Player, Round
from ghibai.sheets import SheetError, build_table, extract_key

SEATS = [
    Player(1, "Hương", "huong", 0),
    Player(2, "Hằng", "hang", 1),
    Player(3, "Toàn", "toan", 2),
    Player(4, "Thu", "thu", 3),
]


def test_lay_id_tu_link_that():
    url = (
        "https://docs.google.com/spreadsheets/d/"
        "1KsAUkCFLH4OmQWvEjjLazITxtsb0-gK3Fd2LE9pi6Uw/edit?usp=sharing"
    )
    assert extract_key(url) == "1KsAUkCFLH4OmQWvEjjLazITxtsb0-gK3Fd2LE9pi6Uw"


def test_lay_id_tu_key_tran():
    assert extract_key("1KsAUkCFLH4OmQWvEjjLazITxtsb0-gK3Fd2LE9pi6Uw").startswith("1KsAU")


@pytest.mark.parametrize("bad", ["", "abc", "https://example.com/foo", "not a link"])
def test_link_sai(bad):
    with pytest.raises(SheetError):
        extract_key(bad)


def test_bang_export_co_dong_tong_va_o_chuong():
    rounds = [
        Round(1, 1, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , 6",
              {1: -5, 2: 5, 3: -6, 4: 6}),
        Round(2, 2, 1, "2026-09-02T20:19:00+07:00", ", -4, 0, 2",
              {1: 2, 2: -4, 3: 0, 4: 2}),
    ]
    totals = {1: -3, 2: 1, 3: -6, 4: 8}
    title, header, rows, totals_row, banker_cells = build_table(SEATS, rounds, totals)

    assert header == ["Gio", "Hương", "Hằng", "Toàn", "Thu"]
    assert rows[0] == ["20:14", -5, 5, -6, 6]
    assert rows[1] == ["20:19", 2, -4, 0, 2]
    assert totals_row == ["TONG", -3, 1, -6, 8]
    assert "2026-09-02" in title and "2 van" in title

    # Van 1 -> dong 2 (0-based, sau tieu de + header), Toan -> cot 3
    assert banker_cells == [(2, 3), (3, 1)]


def test_nguoi_bo_van_de_o_trong():
    rounds = [Round(1, 1, 3, "2026-09-02T20:14:00+07:00", "-5, 5, , x", {1: -5, 2: 5, 3: 0})]
    _, _, rows, _, _ = build_table(SEATS, rounds, {1: -5, 2: 5, 3: 0})
    assert rows[0][-1] == ""
