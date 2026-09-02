"""Luat tinh diem 3 cay: nguoi cam chuong an/tra voi tung nguoi nen tong 1 van luon = 0."""

from .parser import ParsedRound


class ScoringError(Exception):
    pass


# Diem chuong = -(tong diem nhung nguoi con lai), nho vay tong ca van luon bang 0.
def resolve_scores(parsed: ParsedRound) -> dict[int, int]:
    if parsed.banker_id in parsed.scores:
        raise ScoringError("Nguoi cam chuong khong duoc nhap diem.")

    full = dict(parsed.scores)
    full[parsed.banker_id] = -sum(parsed.scores.values())

    if sum(full.values()) != 0:
        raise ScoringError(f"Tong diem van phai bang 0, dang la {sum(full.values())}.")
    return full
