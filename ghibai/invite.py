"""Trang mo dau cho link chia se: /i/<ma>.

Telegram khong can trang nay (deep link ?start= da mang ma di theo), nhung Zalo Bot
Platform khong ho tro tham so trong link nen phai di qua mot trang cua minh de ghi log
click, roi moi chuyen tiep sang bot. Bat duoc nguon hay khong sau do la viec cua
Tracker (luat 'landing').

Trang duoc dung bang HTML thuan, CSS inline, khong dung ban build React: nguoi moi chi
nhin trang nay dung mot lan, khong dang de tai ca mot SPA.
"""

import logging
from html import escape

from aiohttp import web

from .tracking import Tracker, fingerprint

logger = logging.getLogger(__name__)

NOT_FOUND = "Link mời này không còn dùng được. Hãy xin người gửi một link mới."


class InvitePages:
    def __init__(
        self,
        tracker: Tracker,
        telegram_username: str | None = None,
        zalo_bot_link: str | None = None,
    ):
        self.tracker = tracker
        self.telegram_username = telegram_username
        self.zalo_bot_link = zalo_bot_link

    async def page(self, request: web.Request) -> web.StreamResponse:
        # --- 1. TRA MA & GHI LOG CLICK ---
        code = (request.match_info.get("code") or "").strip().upper()
        owner = self.tracker.note_click(code, fingerprint(*_client(request))) if code else None
        if owner is None:
            raise web.HTTPNotFound(text=_shell(NOT_FOUND, []), content_type="text/html")

        # --- 2. CHUYEN TIEP HOAC CHO CHON NEN TANG ---
        links = self._links(code)
        if not links:
            logger.warning(
                "Co nguoi bam link moi %s nhung chua cau hinh TELEGRAM_BOT_USERNAME "
                "hay ZALO_BOT_LINK nen khong biet chuyen di dau.",
                code,
            )
            raise web.HTTPNotFound(text=_shell(NOT_FOUND, []), content_type="text/html")
        if len(links) == 1:
            raise web.HTTPFound(links[0][1])

        return web.Response(
            text=_shell("Bấm vào nền tảng bạn đang dùng để mở bot:", links),
            content_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    # Ma di kem link Telegram nen Telegram luon gan nguon chinh xac; Zalo khong nhan
    # duoc tham so nao, chi con dua vao log click.
    def _links(self, code: str) -> list[tuple[str, str]]:
        links = []
        if self.telegram_username:
            links.append(
                ("Mở bằng Telegram", f"https://t.me/{self.telegram_username}?start=r_{code}")
            )
        if self.zalo_bot_link:
            links.append(("Mở bằng Zalo", self.zalo_bot_link))
        return links


def _client(request: web.Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() or request.remote
    return request.headers.get("User-Agent"), ip


def _shell(message: str, links: list[tuple[str, str]]) -> str:
    buttons = "\n".join(
        f'<a class="btn" href="{escape(url)}">{escape(label)}</a>' for label, url in links
    )
    return f"""<!doctype html>
<html lang="vi"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot ghi điểm 3 cây &amp; Sâm</title>
<style>
  :root {{ color-scheme: light dark; --bg: #f6f7f5; --fg: #16181a; --muted: #5f6570;
           --card: #fff; --line: #e3e5e1; --accent: #0e3b2d; --accent-fg: #fff; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #0f1211; --fg: #eef1ee; --muted: #9aa3a0; --card: #181c1a;
             --line: #2a2f2c; --accent: #1f7d5f; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100dvh; display: grid; place-items: center;
          padding-block: 24px calc(24px + env(safe-area-inset-bottom));
          padding-inline: calc(20px + env(safe-area-inset-left))
                          calc(20px + env(safe-area-inset-right));
          background: var(--bg); color: var(--fg);
          font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ width: 100%; max-width: 27rem; background: var(--card); border: 1px solid var(--line);
          border-radius: 18px; padding: 28px 22px; text-align: center; }}
  h1 {{ margin: 0 0 6px; font-size: 1.3rem; }}
  p {{ margin: 0 0 22px; color: var(--muted); }}
  .btn {{ display: block; margin-top: 12px; padding: 15px 18px; border-radius: 12px;
          background: var(--accent); color: var(--accent-fg); font-weight: 600;
          text-decoration: none; }}
  .btn:active {{ opacity: .85; }}
</style>
</head><body><main>
<div style="font-size:2.6rem;line-height:1">🎴</div>
<h1>Bot ghi điểm 3 cây &amp; Sâm</h1>
<p>{escape(message)}</p>
{buttons}
</main></body></html>
"""
