import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

TELEGRAM = "telegram"
ZALO = "zalo"


@dataclass(frozen=True)
class Config:
    telegram_token: str | None
    zalo_token: str | None
    zalo_secret_token: str | None
    zalo_webhook_url: str | None
    web_host: str
    web_port: int
    web_ui: bool
    web_dist: Path
    web_public_url: str | None
    sa_json_path: Path
    db_path: Path
    default_sheet_url: str | None
    sheet_tab_name: str
    allowed_chats: dict[str, frozenset[str]]

    @property
    def platforms(self) -> list[str]:
        active = []
        if self.telegram_token:
            active.append(TELEGRAM)
        if self.zalo_token:
            active.append(ZALO)
        return active

    # Webhook Zalo va trang web deu can HTTP server; tat ca hai thi khong mo port nao.
    @property
    def needs_webserver(self) -> bool:
        return bool(self.zalo_token) or self.web_ui


def load_config(env_file: str | os.PathLike[str] | None = None) -> Config:
    load_dotenv(env_file, override=False)

    telegram_token = _clean("TELEGRAM_BOT_TOKEN")
    zalo_token = _clean("ZALO_BOT_TOKEN")
    if not telegram_token and not zalo_token:
        raise SystemExit(
            "Chưa có token nào. Điền TELEGRAM_BOT_TOKEN và/hoặc ZALO_BOT_TOKEN trong .env.\n"
            "  Telegram: @BotFather -> /newbot\n"
            "  Zalo    : https://zalo.me/s/botcreator/"
        )

    zalo_secret = _clean("ZALO_SECRET_TOKEN")
    if zalo_token and not zalo_secret:
        raise SystemExit(
            "Có ZALO_BOT_TOKEN nhưng thiếu ZALO_SECRET_TOKEN.\n"
            "Zalo gửi khóa này trong header X-Bot-Api-Secret-Token để xác thực webhook, "
            "thiếu nó thì bất kỳ ai cũng gọi được webhook của bạn.\n"
            "Tạo 1 khóa 8-256 ký tự:  openssl rand -hex 24"
        )
    if zalo_secret and not 8 <= len(zalo_secret) <= 256:
        raise SystemExit(
            f"ZALO_SECRET_TOKEN dài {len(zalo_secret)} ký tự, Zalo yêu cầu 8-256 ký tự."
        )

    db_path = Path(os.getenv("DB_PATH") or "./data/ghibai.db").expanduser()
    _ensure_writable(db_path)

    return Config(
        telegram_token=telegram_token,
        zalo_token=zalo_token,
        zalo_secret_token=zalo_secret,
        zalo_webhook_url=_clean("ZALO_WEBHOOK_URL"),
        web_host=_clean("WEB_HOST") or "0.0.0.0",
        web_port=int(_clean("WEB_PORT") or 8080),
        web_ui=_flag("WEB_UI", default=True),
        web_dist=Path(os.getenv("WEB_DIST") or "./web/dist").expanduser(),
        web_public_url=_clean("WEB_PUBLIC_URL"),
        sa_json_path=Path(
            os.getenv("GOOGLE_SA_JSON") or "./secrets/service_account.json"
        ).expanduser(),
        db_path=db_path,
        default_sheet_url=_clean("DEFAULT_SHEET_URL"),
        sheet_tab_name=_clean("SHEET_TAB_NAME") or "Chi tiết ván",
        allowed_chats={
            TELEGRAM: _parse_chat_ids("TELEGRAM_CHAT_ID"),
            ZALO: _parse_chat_ids("ZALO_CHAT_ID"),
        },
    )


def _clean(name: str) -> str | None:
    return (os.getenv(name) or "").strip() or None


def _flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off", "tat", "tắt")


# Rong = cho phep moi chat cua platform do.
def _parse_chat_ids(name: str) -> frozenset[str]:
    raw = (os.getenv(name) or "").replace(";", ",")
    return frozenset(token.strip() for token in raw.split(",") if token.strip())


# Sai UID trong Docker chi bao "unable to open database file" nen kiem tra som cho ro rang.
def _ensure_writable(db_path: Path) -> None:
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(f"Không tạo được thư mục {db_path.parent}: {exc}")

    if not os.access(db_path.parent, os.W_OK):
        raise SystemExit(
            f"Không có quyền ghi vào {db_path.parent} (đang chạy bằng uid {os.getuid()}).\n"
            "Nếu chạy bằng Docker: đặt DOCKER_UID và DOCKER_GID trong .env cho khớp với host\n"
            '  echo "DOCKER_UID=$(id -u)" >> .env && echo "DOCKER_GID=$(id -g)" >> .env\n'
            "rồi chạy lại: docker compose up -d --force-recreate"
        )
