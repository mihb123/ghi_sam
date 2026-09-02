# 🎴 Bot ghi điểm 3 cây — Telegram + Zalo + Web PWA

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind-v4-38bdf8.svg)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-134%20passed-brightgreen.svg)](tests/)

Sổ ghi điểm điện tử tự động cho bàn 3 cây ngoài đời. Gõ kết quả từng ván trực tiếp trong chat $\rightarrow$ lưu trữ SQLite $\rightarrow$ xem bảng tổng lũy kế ngay trong chat $\rightarrow$ xem realtime trên ứng dụng Web (PWA Mobile-First) $\rightarrow$ tự động export lên Google Sheets có format màu và freeze pane.

Chạy đồng thời **Telegram** (long polling) và **Zalo** (webhook + HMAC) trong cùng một tiến trình, dùng chung một cơ sở dữ liệu.

> 💡 **Tài liệu tra cứu chi tiết**: Xem [Cẩm nang Tra cứu Kỹ thuật & Danh mục Mã nguồn tại `docs/index.md`](docs/index.md) để tìm kiếm nhanh các file mã nguồn, tính năng, schema database, REST API và cấu trúc hệ thống.

---

## 📑 Mục lục

1. [Quy tắc tính điểm](#quy-tắc-tính-điểm)
2. [Cách nhập một ván](#cách-nhập-một-ván)
3. [Bảng lệnh Bot](#lệnh)
4. [Cài đặt & Khởi chạy nhanh](#setup)
5. [Cấu hình Telegram](#1-telegram)
6. [Cấu hình Zalo](#2-zalo)
7. [Expose webhook qua Cloudflare Tunnel](#3-expose-webhook-qua-cloudflare-tunnel)
8. [Cấp quyền Google Sheet](#4-cấp-quyền-google-sheet)
9. [Trang web xem trên điện thoại (PWA)](#trang-web-xem-trên-điện-thoại)
10. [CLI quản trị Zalo](#cli-quản-lý-zalo)
11. [Triển khai bằng Docker Compose](#triển-khai-bằng-docker)
12. [Bảng biến môi trường (.env)](#biến-trong-env)
13. [Kiến trúc Mã nguồn](#kiến-trúc)

---

## Quy tắc tính điểm

Người cầm chương **không điền điểm** — bot tự tính, vì chương ăn/trả trực tiếp với từng người nên tổng một ván luôn bằng 0:

```
Người chơi:  Hương, Hằng, Toàn, Thu     (thứ tự chỗ ngồi)
Bạn gõ:      -5, 5, , 6
                    └── ô trống = Toàn cầm chương

Bot tính:    Toàn = -(-5 + 5 + 6) = -6
Kết quả:     Hương -5 │ Hằng +5 │ Toàn -6 │ Thu +6      → tổng = 0 ✓
```

`0` là **điểm thật** (hòa), không phải dấu cầm chương. Chương có thể net = 0 và vẫn để ô trống.

---

## Cách nhập một ván

### 1. Theo vị trí (nhanh nhất — số ô phải đúng số chỗ ngồi)

| Gõ | Nghĩa |
|---|---|
| `-5, 5, , 6` | ô trống = Toàn cầm chương |
| `-5, 5, c, 6` | `c` cũng là cầm chương |
| `-5, 5, 6,` | ô trống ở cuối $\rightarrow$ Thu cầm chương |
| `, 5, -7, 6` | ô trống ở đầu $\rightarrow$ Hương cầm chương |
| `-5, 5, , x` | `x` = Thu bỏ ván này (ngồi ngoài) |
| `-5,5,,6` | khoảng trắng tùy ý |

### 2. Theo tên (khi muốn ghi rõ)

| Gõ | Nghĩa |
|---|---|
| `Hương -5, Hằng 5, Toàn, Thu 6` | tên trần không kèm số = cầm chương |
| `Toàn*, Hương -5, Hằng 5, Thu 6` | dấu `*` = cầm chương |
| `c:Toàn Hương -5 Hằng 5 Thu 6` | tiền tố `c:` = cầm chương |
| `Hương -5, Hằng 5, Thu 6` | thiếu Toàn $\rightarrow$ tự suy ra Toàn cầm chương |

- Tên không phân biệt hoa/thường và không cần gõ dấu (`hang` = `Hằng`).
- Bot chỉ tự bắt tin nhắn trần khi nó **chắc chắn** là kết quả ván, nên chat thường (*"tối nay đánh tiếp không"*) không bị ghi nhầm.

---

## Lệnh

**Telegram dùng `/`, Zalo dùng `#`** — Zalo không có menu lệnh dạng `/`. Cả hai prefix đều chạy được ở cả hai nền tảng; riêng phần hướng dẫn thì in đúng prefix của nền tảng đang dùng.

| Lệnh | Việc |
|---|---|
| `/help` · `#help` | Hướng dẫn sử dụng |
| `/nguoichoi Hương, Hằng, Toàn, Thu` | Khai báo người chơi — **thứ tự này chính là thứ tự nhập điểm** |
| `/dsnguoi` | Xem danh sách và thứ tự chỗ |
| `/themnguoi Nam` · `/xoanguoi Nam` | Thêm / bỏ một người |
| `/banmoi [ghi chú]` · `/ketthuc` | Mở bàn / chốt bàn |
| `/v -5, 5, , 6` | Ghi một ván |
| `/undo` | Huỷ ván vừa ghi |
| `/xoa 3` · `/xoa 3 5 7` | Xoá ván theo số thứ tự |
| `/khoiphuc 3` | Lấy lại ván đã xoá |
| `/sua 3 -5, 5, , 6` | Nhập lại ván số 3 (giữ nguyên số ván) |
| `/xoaban xacnhan` | Xoá sạch bàn đang chơi |
| `/bang` | Điểm luỹ kế bàn đang chơi |
| `/lichsu 10` | 10 ván gần nhất |
| `/xh` | Xếp hạng tích luỹ mọi bàn |
| `/web` | Link xem bàn đang chơi trên điện thoại |
| `/web doilink` | Đổi link nếu lỡ lọt ra ngoài nhóm |
| `/sheet <link>` | Lưu link Google Sheet cho nhóm này |
| `/export` | Ghi bàn đang chơi lên sheet |

> ℹ️ Xoá là **soft delete** — ván chỉ bị ẩn khỏi tổng, `/khoiphuc` lấy lại được.

---

## Setup

```bash
uv sync
cp .env.example .env        # rồi điền token
uv run ghibai
```

Không có `uv` thì `pip install -e .` rồi `python main.py`. File SQLite tự tạo và tự migrate theo `DB_PATH` khi chạy lần đầu. Chạy kiểm thử: `uv run pytest`.

Mỗi nền tảng là tuỳ chọn: có token nào thì bật nền tảng đó. Cần ít nhất một token.

---

### 1. Telegram

1. Chat với [@BotFather](https://t.me/BotFather) $\rightarrow$ `/newbot` $\rightarrow$ copy token vào `TELEGRAM_BOT_TOKEN`.
2. **Bắt buộc nếu dùng trong nhóm:** `/mybots` $\rightarrow$ chọn bot $\rightarrow$ *Bot Settings* $\rightarrow$ *Group Privacy* $\rightarrow$ **Turn off**. Không tắt thì bot chỉ nhận được lệnh có `/`, không đọc được tin nhắn trần như `-5, 5, , 6`. Bot cảnh báo việc này lúc khởi động.
3. **Phải tắt TRƯỚC khi thêm bot vào nhóm.** Telegram chốt quyền đọc cho từng nhóm ngay lúc bot vào, tắt sau không hồi tố — nhóm cũ vẫn lọc tin nhắn trần dù `getMe` đã báo `can_read_all_group_messages: true`. Với nhóm đã lỡ thêm, chọn 1 trong 2: kick bot ra rồi thêm lại, hoặc cấp quyền admin cho bot trong nhóm đó.

---

### 2. Zalo

1. Tạo bot tại [Zalo Bot Creator](https://zalo.me/s/botcreator/) $\rightarrow$ copy token vào `ZALO_BOT_TOKEN`.
2. Tạo secret cho webhook: `openssl rand -hex 24` $\rightarrow$ `ZALO_SECRET_TOKEN` (Zalo gửi khoá này trong header `X-Bot-Api-Secret-Token`; thiếu nó thì bất kỳ ai cũng gọi được webhook của bạn).
3. Đặt `ZALO_WEBHOOK_URL` = URL HTTPS công khai trỏ tới `/zalo/webhook`.
4. Chạy bot — bot **tự gọi `setWebhook`** lúc khởi động và log kết quả Zalo verify.

Zalo **chỉ** hỗ trợ webhook HTTPS, không nhận `http`, `localhost` hay IP nội bộ.

---

### 3. Expose webhook qua Cloudflare Tunnel

App chạy HTTP thuần (không TLS) trên `WEB_PORT`, tunnel lo HTTPS:

```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: sam.mihb.site
    service: http://localhost:10240      # phải khớp WEB_PORT trong .env
```

⚠️ **Minimum TLS Version của zone phải là 1.2, không được đặt 1.3.** Zalo dùng TLS 1.2 để gọi webhook; nếu zone chặn 1.2 thì `setWebhook` trả `webhook.err.tls` dù trình duyệt và `curl` vẫn vào được bình thường. Sửa tại **Cloudflare $\rightarrow$ SSL/TLS $\rightarrow$ Edge Certificates $\rightarrow$ Minimum TLS Version $\rightarrow$ TLS 1.2**. Kiểm tra:

```bash
curl --tlsv1.2 --tls-max 1.2 https://sam.mihb.site/healthz    # phải trả {"ok": true}
```

---

### 4. Cấp quyền Google Sheet

1. [Google Cloud Console](https://console.cloud.google.com/) $\rightarrow$ tạo project.
2. *APIs & Services* $\rightarrow$ bật **Google Sheets API** và **Google Drive API**.
3. *IAM & Admin* $\rightarrow$ *Service Accounts* $\rightarrow$ tạo mới $\rightarrow$ *Keys* $\rightarrow$ *Add key* $\rightarrow$ JSON.
4. Lưu file JSON vào **`secrets/service_account.json`**.
5. Mở Google Sheet của bạn $\rightarrow$ **Share** $\rightarrow$ dán email service account (dạng `ten-bot@project.iam.gserviceaccount.com`) $\rightarrow$ quyền **Editor**.

Chưa Share thì `/export` sẽ báo lỗi kèm đúng email cần thêm.

#### Sheet sau khi `/export`

Tab `Chi tiết ván` bị **ghi đè toàn bộ** mỗi lần export — SQLite là nguồn sự thật duy nhất, nên chạy bao nhiêu lần cũng ra kết quả giống nhau và không bao giờ trùng dòng.

```
Bàn ngày 2026-09-02 - 3 ván
Giờ   │ Hương │ Hằng │ Toàn │ Thu
20:14 │    -5 │    5 │   -6 │   6
20:19 │     3 │   -4 │    0 │   1
20:23 │    -2 │   -3 │    4 │   1
TỔNG  │    -4 │   -2 │   -2 │   8
```

Ô của người cầm chương được tô màu nền vàng. Mọi ô điểm là **số thật**, tính toán được trong Sheet.

---

## Trang web xem trên điện thoại

Bàn đang chơi có một trang web **chỉ đọc**: bảng xếp hạng và chi tiết từng ván, cài được lên màn hình chính như app thật (PWA). Không sửa được điểm ở đây — mọi thay đổi vẫn phải qua chat, nên không có đường nào để người ngoài nhóm ghi bậy vào sổ.

```bash
cd web && npm install && npm run build      # tạo web/dist
```

Rồi đặt trong `.env`:

```env
WEB_PUBLIC_URL=https://sam.mihb.site        # domain đã trỏ tới app
```

Khởi động lại bot, vào nhóm gõ `/web` — bot trả link riêng của **nhóm đó**:

```
https://sam.mihb.site/?k=DsVCaKSCVKK3u6KxRkEm4_ur
```

⚠️ **Token trong link chính là quyền xem.** Mỗi nhóm một token riêng, ai có link đều xem được bàn của nhóm đó (và chỉ nhóm đó — token của nhóm này không mở được bàn nhóm khác). Lỡ lọt ra ngoài thì `/web doilink` sinh token mới và vô hiệu link cũ ngay lập tức.

Trang dùng chung cổng `WEB_PORT` với webhook Zalo nên cấu hình Cloudflare Tunnel không phải đổi gì. `WEB_UI=0` tắt hẳn cả trang web lẫn API.

### Cài lên màn hình chính

Mở link $\rightarrow$ Safari: *Share* $\rightarrow$ *Add to Home Screen*; Chrome: *⋮* $\rightarrow$ *Add to Home screen*.

Mở từ icon thì URL không còn `?k=`, nên app lưu token vào `localStorage` ngay lần đầu — lần sau vẫn vào đúng nhóm cũ. Muốn xem nhóm khác thì mở link của nhóm đó, token mới ghi đè.

Điểm tự làm mới mỗi 15 giây khi màn hình đang bật; khoá máy thì dừng hẳn cho đỡ tốn pin và 4G. Mất sóng vẫn xem được số của lần tải gần nhất, kèm cảnh báo là số đã cũ.

### Sửa giao diện

```bash
cd web && npm run dev        # http://localhost:5173, tự proxy /api sang bot
```

Bot phải đang chạy ở `WEB_PORT` (mặc định 10240) thì dev server mới lấy được dữ liệu. Mở `http://localhost:5173/?k=<token>` với token lấy từ `/web`.

| Lệnh trong `web/` | Việc |
|---|---|
| `npm run dev` | Dev server, hot reload |
| `npm run build` | Build ra `web/dist` |
| `npm run typecheck` | Kiểm tra TypeScript |
| `npx shadcn@latest add <tên>` | Thêm component shadcn/ui |

---

## CLI quản lý Zalo

Debug webhook mà không phải chạy cả bot:

```bash
uv run ghibai-zalo getme                 # token còn đúng không
uv run ghibai-zalo setwebhook            # đăng ký (lấy ZALO_WEBHOOK_URL)
uv run ghibai-zalo info                  # webhook đang đăng ký + kết quả verify
uv run ghibai-zalo delete                # huỷ webhook
uv run ghibai-zalo send <chat_id> xin chào
```

---

## Triển khai bằng Docker

```bash
cp .env.example .env                            # rồi điền token
echo "DOCKER_UID=$(id -u)" >> .env              # để container ghi được vào ./data
echo "DOCKER_GID=$(id -g)" >> .env
docker compose up -d
docker compose logs -f bot
```

| Lệnh | Việc |
|---|---|
| `docker compose up -d` | Chạy nền, tự restart khi crash hoặc reboot |
| `docker compose logs -f bot` | Xem log trực tiếp |
| `docker compose down` | Dừng container |
| `docker compose up -d --build` | Deploy lại sau khi sửa code (build luôn cả trang web) |
| `uv run pytest` | Chạy test suite (image deploy không có pytest) |

⚠️ **Một token chỉ được một tiến trình poll.** Đừng chạy đồng thời `uv run ghibai` và container — Telegram sẽ đá một bên ra với lỗi `Conflict: terminated by other getUpdates`.

### Vài quyết định trong `docker-compose.yml`

- **`ports: 127.0.0.1:${WEB_PORT}:${WEB_PORT}`** — chỉ bind loopback. App không có TLS nên không được mở thẳng ra internet; cloudflared trên cùng host truy cập loopback bình thường.
- **`user: ${DOCKER_UID:-1000}:${DOCKER_GID:-1000}`** — container chạy bằng UID của host để ghi được vào bind mount `./data`. Nhờ vậy Docker và `uv run ghibai` **dùng chung một file SQLite**, đổi qua đổi lại không mất dữ liệu. UID sai thì bot báo lỗi kèm đúng lệnh cần chạy, chứ không chết bằng `unable to open database file`.
- **`TZ`** — bắt buộc. Container mặc định UTC sẽ làm cột `Giờ` trên sheet lệch 7 tiếng.
- **`./secrets:/app/secrets:ro`** — mount cả thư mục thay vì từng file, vì bind mount một file chưa tồn tại sẽ bị Docker biến thành thư mục rỗng.
- **`healthcheck`** — gọi `/healthz`, nhưng **tự bỏ qua khi không bật Zalo**, vì lúc đó không có HTTP server nào để kiểm tra.
- **`uv sync --frozen`** — build từ `uv.lock`, deploy đúng y bản đã test ở local.
- **Log rotate 10MB × 3** — bot chạy nhiều tháng không làm đầy đĩa.

---

## Biến trong `.env`

| Biến | Việc |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token từ @BotFather. Trống = tắt Telegram |
| `TELEGRAM_CHAT_ID` | Allowlist chat Telegram, cách nhau bằng phẩy. Trống = mọi chat |
| `ZALO_BOT_TOKEN` | Token từ botcreator. Trống = tắt Zalo |
| `ZALO_SECRET_TOKEN` | Khoá xác thực webhook, 8–256 ký tự. **Bắt buộc nếu bật Zalo** |
| `ZALO_WEBHOOK_URL` | URL HTTPS công khai trỏ tới `/zalo/webhook` |
| `ZALO_CHAT_ID` | Allowlist chat Zalo. Trống = mọi chat |
| `WEB_HOST` · `WEB_PORT` | HTTP server cho webhook Zalo và trang web (mặc định `0.0.0.0:10240`) |
| `WEB_UI` | `0` = tắt hẳn trang web và API. Mặc định bật |
| `WEB_PUBLIC_URL` | Gốc URL công khai, để `/web` dựng được link gửi vào nhóm |
| `WEB_DIST` | Thư mục build của React (mặc định `./web/dist`) |
| `GOOGLE_SA_JSON` | Đường dẫn file JSON key của Service Account |
| `DEFAULT_SHEET_URL` | Sheet dùng khi nhóm chưa tự set bằng `/sheet` |
| `SHEET_TAB_NAME` | Tên tab bị ghi đè mỗi lần `/export` |
| `DB_PATH` | File SQLite, tự tạo nếu chưa có |
| `TZ` | Múi giờ cho cột `Giờ` (mặc định `Asia/Ho_Chi_Minh`) |
| `DOCKER_UID` / `DOCKER_GID` | UID/GID host để container ghi được `./data` (`id -u` / `id -g`) |

Nếu allowlist chặn sai chat, bot trả lời kèm luôn `chat_id` thật của chat đó để bạn copy vào `.env` — không bao giờ im lặng khiến bạn tưởng bot chết.

---

## Kiến trúc

Logic lệnh nằm trong [`ghibai/core.py`](ghibai/core.py) và **không biết gì về Telegram hay Zalo**. Adapter chỉ làm việc vận chuyển, nên thêm nền tảng mới không phải nhân bản logic.

| File | Việc |
|---|---|
| [`ghibai/core.py`](ghibai/core.py) | Toàn bộ logic lệnh, trả về `list[str]` — dùng chung mọi nền tảng |
| [`ghibai/parser.py`](ghibai/parser.py) | Đọc tin nhắn thành kết quả ván (2 cú pháp, nhận diện chương) |
| [`ghibai/scoring.py`](ghibai/scoring.py) | Tính điểm cầm chương, đảm bảo tổng = 0 |
| [`ghibai/db.py`](ghibai/db.py) | SQLite + migration; `chat_key` = `<platform>:<id gốc>` |
| [`ghibai/render.py`](ghibai/render.py) | Dựng message; Telegram dùng `<pre>`, Zalo layout khác vì không có `<pre>` |
| [`ghibai/sheets.py`](ghibai/sheets.py) | Ghi Google Sheet + dịch lỗi quyền thành hướng dẫn |
| [`ghibai/adapters/telegram_adapter.py`](ghibai/adapters/telegram_adapter.py) | Long polling Telegram |
| [`ghibai/adapters/zalo_adapter.py`](ghibai/adapters/zalo_adapter.py) | Zalo API client + webhook (xác thực secret, chống ghi trùng) |
| [`ghibai/webserver.py`](ghibai/webserver.py) | aiohttp: `/zalo/webhook`, `/api/board`, `/healthz`, file build của web |
| [`ghibai/webapi.py`](ghibai/webapi.py) | Payload JSON cho trang web; xác thực bằng token trong link |
| [`web/`](web/) | Trang web React + Vite + shadcn/ui, PWA, ưu tiên mobile |
| [`ghibai/bot.py`](ghibai/bot.py) | Chạy song song cả hai nền tảng |
| [`ghibai/cli.py`](ghibai/cli.py) | `ghibai-zalo` — quản lý webhook |
| [`docs/index.md`](docs/index.md) | **Cẩm nang Tra cứu Kỹ thuật & Danh mục Mã nguồn Toàn diện** |

Mỗi phòng chat có danh sách người chơi và lịch sử **hoàn toàn riêng biệt**, kể cả khi Telegram và Zalo tình cờ trùng id gốc.

### Vài chỗ đáng lưu ý

- **Zalo gửi lại update khi endpoint trả lời chậm.** Webhook trả `200` ngay rồi xử lý nền (vì `/export` gọi Google Sheet mất vài giây), và chặn trùng theo `message_id` — ghi trùng một ván sẽ làm sai toàn bộ số điểm.
- **Zalo giới hạn 2000 ký tự/tin**, Telegram 4096 $\rightarrow$ message dài bị cắt theo dòng.
- **Zalo chỉ hỗ trợ `<b> <i> <u> <s>`**, không có `<pre>`/`<code>`, nên bảng căn cột bằng monospace sẽ vỡ font $\rightarrow$ bản Zalo trình bày mỗi ván một khối thay vì bảng.
