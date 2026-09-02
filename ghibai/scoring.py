"""Luat tinh diem 3 cay: nguoi cam chuong an/tra voi tung nguoi nen tong 1 van luon = 0."""

from .parser import ParsedRound


class ScoringError(Exception):
    pass


# Diem chuong / nguoi thang = -(tong diem nhung nguoi con lai), nho vay tong ca van luon bang 0.
def resolve_scores(parsed: ParsedRound, game_type: str = "3cay") -> dict[int, int]:
    if parsed.banker_id in parsed.scores:
        role = "Người thắng" if game_type == "sam" else "Người cầm chương"
        raise ScoringError(f"{role} không được nhập điểm.")

    full = dict(parsed.scores)
    full[parsed.banker_id] = -sum(parsed.scores.values())

    if sum(full.values()) != 0:
        raise ScoringError(f"Tổng điểm ván phải bằng 0, đang là {sum(full.values())}.")
    return full
