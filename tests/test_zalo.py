"""Test webhook Zalo: xac thuc secret, chong ghi trung khi Zalo gui lai, doc dung payload."""

import asyncio

import pytest

from ghibai.adapters.zalo_adapter import SECRET_HEADER, SeenMessages, ZaloWebhook
from ghibai.core import Engine
from ghibai.db import Database
from ghibai.sheets import SheetExporter

SECRET = "khoa-bi-mat-du-dai-8-ky-tu"
CHAT = "6ede9afa66b88fe6d6a9"


def payload(text: str, message_id: str = "m1", chat_type: str = "GROUP") -> dict:
    return {
        "ok": True,
        "result": {
            "message": {
                "from": {"id": "u1", "display_name": "Ted", "is_bot": False},
                "chat": {"id": CHAT, "chat_type": chat_type},
                "text": text,
                "message_id": message_id,
                "date": 1750316131602,
            },
            "event_name": "message.text.received",
        },
    }


class FakeRequest:
    def __init__(self, body, secret=SECRET):
        self.headers = {SECRET_HEADER: secret} if secret is not None else {}
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("bad json")
        return self._body


class FakeClient:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, chat_id, text, parse_mode="html"):
        self.sent.append((str(chat_id), text))
        return {"message_id": "x"}


@pytest.fixture
def hook(tmp_path):
    db = Database(tmp_path / "z.db")
    engine = Engine(db, SheetExporter(tmp_path / "none.json", "t"))
    client = FakeClient()
    yield ZaloWebhook(client, engine, SECRET), client
    db.close()


async def post(webhook, body, secret=SECRET):
    response = await webhook.handle(FakeRequest(body, secret))
    await webhook.drain()
    return response


# --- 1. XAC THUC ---

def test_sai_secret_bi_tu_choi(hook):
    webhook, client = hook
    response = asyncio.run(post(webhook, payload("#help"), secret="sai-secret"))
    assert response.status == 401
    assert client.sent == []


def test_thieu_header_secret_bi_tu_choi(hook):
    webhook, client = hook
    response = asyncio.run(post(webhook, payload("#help"), secret=None))
    assert response.status == 401
    assert client.sent == []


def test_dung_secret_thi_xu_ly(hook):
    webhook, client = hook
    assert asyncio.run(post(webhook, payload("#help"))).status == 200
    assert len(client.sent) == 1
    assert "#nguoichoi" in client.sent[0][1]


def test_json_rac(hook):
    webhook, _ = hook
    assert asyncio.run(post(webhook, None)).status == 400


# --- 2. CHONG GHI TRUNG ---

def test_zalo_gui_lai_cung_update_khong_ghi_2_lan(hook):
    webhook, client = hook
    asyncio.run(post(webhook, payload("#nguoichoi Hương, Hằng, Toàn, Thu", "setup")))
    client.sent.clear()

    body = payload("-5, 5, , 6", message_id="lap-lai")
    asyncio.run(post(webhook, body))
    asyncio.run(post(webhook, body))
    asyncio.run(post(webhook, body))

    assert len(client.sent) == 1
    assert "Da ghi van 1" in client.sent[0][1]
    assert "van 2" not in client.sent[0][1]


def test_seen_messages_gioi_han_bo_nho():
    seen = SeenMessages(capacity=3)
    assert all(seen.add_if_new(f"m{i}") for i in range(3))
    assert not seen.add_if_new("m0")
    seen.add_if_new("m3")            # day m0 ra khoi bo dem
    assert seen.add_if_new("m0")     # coi nhu moi, chap nhan
    assert seen.add_if_new(None)     # thieu message_id thi khong chan


# --- 3. DOC PAYLOAD ---

def test_payload_phang_khong_boc_result(hook):
    """Webhook that gui event o goc; chi API response moi boc trong "result"."""
    webhook, client = hook
    assert asyncio.run(post(webhook, payload("#help")["result"])).status == 200
    assert len(client.sent) == 1


def test_bo_qua_event_khong_phai_tin_nhan_text(hook):
    webhook, client = hook
    body = payload("#help")
    body["result"]["event_name"] = "message.image.received"
    assert asyncio.run(post(webhook, body)).status == 200
    assert client.sent == []


def test_tin_nhan_thieu_text_hoac_chat_id(hook):
    webhook, client = hook
    body = payload("#help", "no-text")
    body["result"]["message"]["text"] = ""
    asyncio.run(post(webhook, body))

    body2 = payload("#help", "no-chat")
    body2["result"]["message"]["chat"] = {}
    asyncio.run(post(webhook, body2))
    assert client.sent == []


def test_tra_loi_dung_chat_id(hook):
    webhook, client = hook
    asyncio.run(post(webhook, payload("#help")))
    assert client.sent[0][0] == CHAT


def test_tin_dai_bi_cat_theo_gioi_han_zalo(hook):
    webhook, client = hook
    asyncio.run(post(webhook, payload("#nguoichoi " + ", ".join(f"Nguoi{i}" for i in range(40)))))
    assert all(len(text) <= 2000 for _, text in client.sent)
