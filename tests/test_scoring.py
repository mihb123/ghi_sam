import pytest

from ghibai.db import Player
from ghibai.parser import ParsedRound, parse_round
from ghibai.scoring import ScoringError, resolve_scores

SEATS = [Player(i, chr(64 + i), chr(96 + i), i - 1) for i in range(1, 5)]


def test_vi_du_ban_dau_A_B_C_D():
    """A -5, B 5, C -7, D  ->  D cam chuong, gianh +7."""
    scores = resolve_scores(parse_round("A -5, B 5, C -7, D", SEATS))
    assert scores == {1: -5, 2: 5, 3: -7, 4: 7}


def test_tong_luon_bang_0():
    for text in ["-5, 5, , 6", "1, 2, 3, ", ", -1, -2, -3", "0, 0, , 0"]:
        assert sum(resolve_scores(parse_round(text, SEATS)).values()) == 0


def test_chuong_co_the_net_bang_0():
    scores = resolve_scores(parse_round("-3, 5, -2, ", SEATS))
    assert scores[4] == 0


def test_chuong_nhap_diem_thi_loi():
    parsed = ParsedRound(banker_id=1, scores={1: 5, 2: -5}, mode="named")
    with pytest.raises(ScoringError, match="không được nhập điểm"):
        resolve_scores(parsed)
