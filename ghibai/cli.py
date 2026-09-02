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
    parser = argparse.ArgumentParser(prog="ghibai-zalo", description="Quản lý Zalo Bot")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("getme", help="Kiểm tra token còn đúng không")
    set_hook = sub.add_parser("setwebhook", help="Đăng ký webhook (mặc định lấy ZALO_WEBHOOK_URL)")
    set_hook.add_argument("url", nargs="?")
    sub.add_parser("info", help="Xem webhook đang đăng ký")
    sub.add_parser("delete", help="Hủy webhook")
    send = sub.add_parser("send", help="Gửi 1 tin nhắn thử")
    send.add_argument("chat_id")
    send.add_argument("text", nargs="+")

    args = parser.parse_args(argv)
    config = load_config()
    if not config.zalo_token:
        print("Chưa có ZALO_BOT_TOKEN trong .env", file=sys.stderr)
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
                print("Thiếu url và ZALO_WEBHOOK_URL cũng trống", file=sys.stderr)
                return 1
            result = await client.set_webhook(url, config.zalo_secret_token)
        elif args.command == "info":
            result = await client.get_webhook_info()
        elif args.command == "delete":
            result = await client.delete_webhook()
        else:
            result = await client.send_message(args.chat_id, " ".join(args.text))
    except ZaloError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
