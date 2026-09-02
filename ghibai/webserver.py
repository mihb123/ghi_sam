"""HTTP server: webhook Zalo + API JSON + trang web xem ban dang choi (React build).

Truoc day server chi mo khi bat Zalo. Gio trang web cung can no, nen dieu kien mo nam
o Config.needs_webserver chu khong con gan lien voi Zalo.
"""

import logging
from pathlib import Path

from aiohttp import web

logger = logging.getLogger(__name__)

ZALO_WEBHOOK_PATH = "/zalo/webhook"
BOARD_API_PATH = "/api/board"

# Vite bam hash vao ten file trong assets/ nen cache vinh vien duoc. index.html va service
# worker thi khong: cache chung se lam user ket o ban cu sau moi lan deploy.
IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"


def build_app(zalo_webhook=None, api=None, dist: Path | None = None) -> web.Application:
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    if zalo_webhook is not None:
        app.router.add_post(ZALO_WEBHOOK_PATH, zalo_webhook.handle)
    if api is not None:
        app.router.add_get(BOARD_API_PATH, api.board)
    # Phai dang ky cuoi cung: route bat-tat-ca nay nuot moi duong dan chua khop o tren.
    if dist is not None:
        app.router.add_get("/{tail:.*}", _spa(dist))
    return app


async def _healthz(_: web.Request) -> web.Response:
    return web.json_response({"ok": True})


# SPA: duong dan khong tro toi file that deu tra index.html de React tu dinh tuyen.
def _spa(dist: Path):
    root = dist.resolve()
    index = root / "index.html"
    assets = root / "assets"

    async def handler(request: web.Request) -> web.StreamResponse:
        target = _resolve_file(root, request.match_info.get("tail", ""))
        if target is None:
            if not index.is_file():
                raise web.HTTPNotFound(
                    text="Chưa build trang web. Chạy: cd web && npm install && npm run build"
                )
            target = index
        response = web.FileResponse(target)
        response.headers["Cache-Control"] = IMMUTABLE if target.parent == assets else NO_CACHE
        return response

    return handler


# Chan ../ thoat ra ngoai thu muc build.
def _resolve_file(root: Path, tail: str) -> Path | None:
    if not tail:
        return None
    candidate = (root / tail).resolve()
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate


async def start(app: web.Application, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    logger.info("HTTP server: http://%s:%s", host, port)
    return runner
