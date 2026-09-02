"""CLI quan ly Zalo Bot, dung de kiem tra webhook ma khong phai chay ca bot.

    ghibai-zalo getme
    ghibai-zalo setwebhook [url]
    ghibai-zalo info
    ghibai-zalo delete
    ghibai-zalo send <chat_id> <noi dung>
"""

import argparse
import asyncio
import json
import sys

from .adapters.zalo_adapter import ZaloClient, ZaloError
from .config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ghibai-zalo", description="Quan ly Zalo Bot")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("getme", help="Kiem tra token con dung khong")
    set_hook = sub.add_parser("setwebhook", help="Dang ky webhook (mac dinh lay ZALO_WEBHOOK_URL)")
    set_hook.add_argument("url", nargs="?")
    sub.add_parser("info", help="Xem webhook dang dang ky")
    sub.add_parser("delete", help="Huy webhook")
    send = sub.add_parser("send", help="Gui 1 tin nhan thu")
    send.add_argument("chat_id")
    send.add_argument("text", nargs="+")

    args = parser.parse_args(argv)
    config = load_config()
    if not config.zalo_token:
        print("Chua co ZALO_BOT_TOKEN trong .env", file=sys.stderr)
        return 1

    return asyncio.run(_run(args, config))


async def _run(args, config) -> int:
    client = ZaloClient(config.zalo_token)
    try:
        if args.command == "getme":
            result = await client.get_me()
        elif args.command == "setwebhook":
            url = args.url or config.zalo_webhook_url
            if not url:
                print("Thieu url va ZALO_WEBHOOK_URL cung trong", file=sys.stderr)
                return 1
            result = await client.set_webhook(url, config.zalo_secret_token)
        elif args.command == "info":
            result = await client.get_webhook_info()
        elif args.command == "delete":
            result = await client.delete_webhook()
        else:
            result = await client.send_message(args.chat_id, " ".join(args.text))
    except ZaloError as exc:
        print(f"Loi: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
