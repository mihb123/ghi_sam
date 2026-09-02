"""Chuan hoa chuoi tieng Viet de so ten nguoi choi khong phu thuoc dau/hoa-thuong."""

import re
import unicodedata

# NFD khong tach duoc d-gach-ngang nen phai map tay truoc khi bo dau.
_DSTROKE = str.maketrans({"đ": "d", "Đ": "d"})


def normalize(s: str) -> str:
    s = s.translate(_DSTROKE)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def fmt_signed(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


_LEADING_WORD = re.compile(r"\s*(\S+)")


# Tag bot trong group Zalo chen "@Ten Bot " vao dau text, lam lenh khong con bat dau bang
# '#' nen core.Engine coi nhu chat thuong roi im lang. Ten bot co dau va co nhieu tu nen
# phai an tung tu theo dang da chuan hoa.
def strip_bot_mention(text: str, bot_name: str | None) -> str:
    stripped = text.lstrip()
    if not bot_name or not stripped.startswith("@"):
        return text

    rest = stripped[1:]
    for word in normalize(bot_name).split():
        matched = _LEADING_WORD.match(rest)
        if not matched or normalize(matched.group(1)) != word:
            return text  # tag nguoi khac, giu nguyen
        rest = rest[matched.end():]
    return rest.lstrip()
