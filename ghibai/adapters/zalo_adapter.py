"""Client va webhook cho Zalo Bot.

API: POST https://bot-api.zaloplatforms.com/bot<TOKEN>/<method>
Payload webhook:
    {"event_name": "message.text.received",
     "message": {"from": {...}, "chat": {"id", "chat_type"}, "text", "message_id", "date"}}
Zalo gui kem header X-Bot-Api-Secret-Token, phai doi chieu truoc khi xu ly.
"""

import asyncio
import hmac
import json
import logging
from collections import deque

import aiohttp
from aiohttp import web

from ..core import Engine, Incoming
from ..render import ZaloFmt, split_message
from ..text import strip_bot_mention

logger = logging.getLogger(__name__)

API_BASE = "https://bot-api.zaloplatforms.com"
TEXT_EVENT = "message.text.received"
SECRET_HEADER = "X-Bot-Api-Secret-Token"


# Webhook gui event o goc, nhung API response lai boc trong {"ok":..,"result":{..}}.
# Nhan ca hai de khoi phu thuoc vao Zalo doi dinh dang.
def _unwrap(body: object) -> dict:
    if not isinstance(body, dict):
        return {}
    inner = body.get("result")
    return inner if isinstance(inner, dict) and "event_name" in inner else body


def _preview(body: object, limit: int = 500) -> str:
    try:
        text = json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        text = repr(body)
    return text[:limit]


class ZaloError(Exception):
    pass


class ZaloClient:
    def __init__(self, token: str, timeout: float = 30.0):
        self.token = token
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _post(self, method: str, payload: dict | None = None) -> dict:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

        url = f"{API_BASE}/bot{self.token}/{method}"
        try:
            async with self._session.post(url, json=payload or {}) as response:
                body = await response.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise ZaloError(f"Khong goi duoc {method}: {exc}") from exc

        if not isinstance(body, dict) or not body.get("ok"):
            raise ZaloError(f"{method} that bai: {body}")
        return body.get("result") or {}

    async def get_me(self) -> dict:
        return await self._post("getMe")

    # Zalo gioi han 1-2000 ky tu moi tin nhan.
    async def send_message(self, chat_id: str, text: str, parse_mode: str = "html") -> dict:
        return await self._post(
            "sendMessage", {"chat_id": str(chat_id), "text": text, "parse_mode": parse_mode}
        )

    async def set_webhook(self, url: str, secret_token: str) -> dict:
        return await self._post("setWebhook", {"url": url, "secret_token": secret_token})

    async def get_webhook_info(self) -> dict:
        return await self._post("getWebhookInfo")

    async def delete_webhook(self) -> dict:
        return await self._post("deleteWebhook")


# Zalo co the gui lai cung 1 update khi endpoint tra loi cham; ghi trung se lam sai so diem
# nen phai chan theo message_id.
class SeenMessages:
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self._order: deque[str] = deque()
        self._seen: set[str] = set()

    def add_if_new(self, message_id: str | None) -> bool:
        if not message_id:
            return True
        if message_id in self._seen:
            return False
        self._seen.add(message_id)
        self._order.append(message_id)
        if len(self._order) > self.capacity:
            self._seen.discard(self._order.popleft())
        return True


class ZaloWebhook:
    def __init__(
        self, client: ZaloClient, engine: Engine, secret_token: str, bot_name: str | None = None
    ):
        self.client = client
        self.engine = engine
        self.secret_token = secret_token
        self.bot_name = bot_name
        self.seen = SeenMessages()
        self._tasks: set[asyncio.Task] = set()

    # Tra 200 ngay roi xu ly nen: /export goi Google Sheet mat vai giay, de Zalo cho
    # se bi timeout va gui lai update -> ghi trung van.
    async def handle(self, request: web.Request) -> web.Response:
        supplied = request.headers.get(SECRET_HEADER, "")
        if not hmac.compare_digest(supplied, self.secret_token):
            logger.warning("Webhook Zalo bi tu choi: secret token khong khop")
            return web.json_response({"ok": False, "error": "invalid secret token"}, status=401)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)

        result = _unwrap(body)
        event = result.get("event_name")
        if event != TEXT_EVENT:
            # Event anh, sticker, vao/roi group... In ca body de con biet bot nhan duoc gi
            # khi no "im lang".
            logger.info("Bo qua event Zalo: %s | body=%s", event, _preview(body))
            return web.json_response({"ok": True})

        message = result.get("message") or {}
        if self.seen.add_if_new(message.get("message_id")):
            chat = message.get("chat") or {}
            logger.info(
                "Zalo <- chat %s (%s): %r",
                chat.get("id"),
                chat.get("chat_type"),
                message.get("text"),
            )
            task = asyncio.create_task(self._process(message))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return web.json_response({"ok": True})

    async def _process(self, message: dict) -> None:
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = chat.get("id")
        text = strip_bot_mention(message.get("text") or "", self.bot_name)
        if not chat_id or not text:
            return

        fmt = ZaloFmt()
        try:
            replies = await self.engine.handle(
                Incoming(
                    platform="zalo",
                    native_chat_id=str(chat_id),
                    chat_title=sender.get("display_name") if chat.get("chat_type") == "PRIVATE" else None,
                    text=text,
                    author=sender.get("display_name"),
                ),
                fmt,
            )
            for reply in replies:
                for chunk in split_message(reply, fmt.limit):
                    await self.client.send_message(chat_id, chunk)
        except Exception:
            logger.exception("Xu ly tin nhan Zalo loi (chat %s)", chat_id)

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
