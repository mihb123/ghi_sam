"""Chay Telegram (long polling) va Zalo (webhook) trong cung 1 tien trinh.

Bat ky nen tang nao cung tuy chon: co token nao thi bat nen tang do. HTTP server duoc mo
khi can webhook Zalo hoac khi bat trang web (WEB_UI).
"""

import asyncio
import contextlib
import logging
import signal

from . import webserver
from .adapters import telegram_adapter
from .adapters.zalo_adapter import ZaloClient, ZaloError, ZaloWebhook
from .config import Config, load_config
from .core import Engine
from .db import Database
from .sheets import SheetExporter
from .webapi import WebApi

logger = logging.getLogger(__name__)


async def run(config: Config) -> None:
    db = Database(config.db_path)
    exporter = SheetExporter(config.sa_json_path, config.sheet_tab_name)
    engine = Engine(
        db, exporter, config.default_sheet_url, config.allowed_chats, config.web_public_url
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)

    telegram_app = None
    zalo_client = None
    zalo_webhook = None
    runner = None

    try:
        if config.telegram_token:
            telegram_app = telegram_adapter.build_application(config.telegram_token, engine)
            await telegram_app.initialize()
            await telegram_adapter.setup(telegram_app)
            await telegram_app.start()
            await telegram_app.updater.start_polling(drop_pending_updates=True)

        if config.zalo_token:
            zalo_client = ZaloClient(config.zalo_token)
            me = await _log_zalo_identity(zalo_client)
            zalo_webhook = ZaloWebhook(
                zalo_client, engine, config.zalo_secret_token, me.get("display_name")
            )

        if config.needs_webserver:
            api = WebApi(db) if config.web_ui else None
            runner = await webserver.start(
                webserver.build_app(zalo_webhook, api, _web_dist(config)),
                config.web_host,
                config.web_port,
            )

        if zalo_client and config.zalo_webhook_url:
            await _register_zalo_webhook(zalo_client, config)
        elif zalo_client:
            logger.warning(
                "Chưa đặt ZALO_WEBHOOK_URL nên bot không tự đăng ký webhook. "
                "Zalo chỉ gửi tin nhắn tới URL đã đăng ký."
            )

        logger.info("Đã sẵn sàng. Nền tảng đang bật: %s", ", ".join(config.platforms))
        await stop.wait()
    finally:
        logger.info("Đang dừng...")
        if runner is not None:
            await runner.cleanup()
        if zalo_webhook is not None:
            await zalo_webhook.drain()
        if zalo_client is not None:
            await zalo_client.close()
        if telegram_app is not None:
            if telegram_app.updater.running:
                await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
        db.close()


# Thieu ban build thi API van chay, chi khong co trang HTML de mo.
def _web_dist(config: Config):
    if not config.web_ui:
        return None
    if not config.web_dist.is_dir():
        logger.warning(
            "Bật WEB_UI nhưng không thấy bản build ở %s. Chạy: cd web && npm install && "
            "npm run build",
            config.web_dist,
        )
        return None
    if not config.web_public_url:
        logger.warning("Chưa đặt WEB_PUBLIC_URL nên lệnh /web không dựng được link để gửi.")
    return config.web_dist


async def _log_zalo_identity(client: ZaloClient) -> dict:
    try:
        me = await client.get_me()
    except ZaloError as exc:
        logger.error("Token Zalo không đúng hoặc không gọi được API: %s", exc)
        return {}
    logger.info(
        "Zalo: %s (id %s, loại %s, vào được group: %s)",
        me.get("account_name"),
        me.get("id"),
        me.get("account_type"),
        me.get("can_join_groups"),
    )
    return me


# Zalo van luu URL du verify that bai, nen chi canh bao chu khong dung bot.
async def _register_zalo_webhook(client: ZaloClient, config: Config) -> None:
    try:
        result = await client.set_webhook(config.zalo_webhook_url, config.zalo_secret_token)
    except ZaloError as exc:
        logger.error("Đăng ký webhook Zalo thất bại: %s", exc)
        return

    verification = result.get("verification") or {}
    if verification.get("ok"):
        logger.info(
            "Webhook Zalo OK: %s (%sms)", result.get("url"), verification.get("latency_ms")
        )
        return

    logger.warning(
        "Webhook Zalo đã lưu nhưng Zalo KHÔNG gọi được vào %s (status %s, %s). "
        "Kiểm tra: domain đã trỏ đúng server chưa, HTTPS còn hạn không, reverse proxy có "
        "forward %s tới cổng %s không.",
        result.get("url"),
        verification.get("status_code"),
        verification.get("outcome") or verification.get("hint"),
        webserver.ZALO_WEBHOOK_PATH,
        config.web_port,
    )


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s - %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    logger.info("DB: %s", config.db_path)
    for platform, allowed in config.allowed_chats.items():
        logger.info(
            "Chat được phép (%s): %s", platform, ", ".join(sorted(allowed)) or "tất cả"
        )

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(config))
