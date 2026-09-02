# 🎴 Bot ghi điểm 3 cây & Sâm — Telegram + Zalo + Web PWA

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind-v4-38bdf8.svg)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)](https://sqlite.org/)
[![Tests](https://img.shields.io/badge/Tests-188%20passed-brightgreen.svg)](tests/)

Sổ ghi điểm điện tử tự động cho bàn **3 cây** và **Sâm (Sâm lốc)** ngoài đời. Gõ kết quả từng ván trực tiếp trong chat $\rightarrow$ lưu trữ SQLite $\rightarrow$ xem bảng tổng lũy kế ngay trong chat $\rightarrow$ xem realtime trên ứng dụng Web (PWA Mobile-First) $\rightarrow$ tự động export lên Google Sheets có format màu và freeze pane.

Chạy đồng thời **Telegram** (long polling) và **Zalo** (webhook + HMAC) trong cùng một tiến trình, dùng chung một cơ sở dữ liệu.

> 💡 **Tài liệu tra cứu chi tiết**: Xem [Cẩm nang Tra cứu Kỹ thuật & Danh mục Mã nguồn tại `docs/index.md`](docs/index.md) để tìm kiếm nhanh các file mã nguồn, tính năng, schema database, REST API và cấu trúc hệ thống.

---

## 📑 Mục lục

1. [Chế độ chơi (3 cây & Sâm)](#chế-độ-chơi-3-cây--sâm)
2. [Quy tắc tính điểm](#quy-tắc-tính-điểm)
3. [Cách nhập một ván](#cách-nhập-một-ván)
4. [Bảng lệnh Bot](#lệnh)
5. [Cài đặt & Khởi chạy nhanh](#setup)
6. [Cấu hình Telegram](#1-telegram)
7. [Cấu hình Zalo](#2-zalo)
8. [Expose webhook qua Cloudflare Tunnel](#3-expose-webhook-qua-cloudflare-tunnel)
9. [Cấp quyền Google Sheet](#4-cấp-quyền-google-sheet)
10. [Trang web xem trên điện thoại (PWA)](#trang-web-xem-trên-điện-thoại)
11. [CLI quản trị Zalo](#cli-quản-lý-zalo)
12. [Triển khai bằng Docker Compose](#triển-khai-bằng-docker)
13. [Thống kê người dùng & nguồn giới thiệu](#thống-kê-người-dùng--nguồn-giới-thiệu)
14. [Bảng biến môi trường (.env)](#biến-trong-env)
15. [Kiến trúc Mã nguồn](#kiến-trúc)

---

## Chế độ chơi (3 cây & Sâm)

Bot hỗ trợ 2 chế độ chơi và lưu thông tin `game_type` vào database:
- **3 cây (`3cay`)**: Người cầm chương là vai trò trung tâm. Trong bảng lịch sử / xếp hạng hiển thị cột **Chương** / **lần chương**.
- **Sâm (`sam`)**: Người thắng ván ăn điểm của tất cả người thua. Trong bảng lịch sử / xếp hạng hiển thị cột **Thắng** / **lần thắng**.

Khi mở bàn mới bằng lệnh `/banmoi`, bot sẽ hỏi bạn muốn chơi 3 cây hay Sâm:
- `/banmoi 3cay [ghi chú]` (hoặc lệnh tắt `/3cay [ghi chú]`): Mở bàn chơi 3 cây.
- `/banmoi sam [ghi chú]` (hoặc lệnh tắt `/sam [ghi chú]`): Mở bàn chơi Sâm.
- `/help 3cay` / `/help sam`: Xem hướng dẫn chi tiết riêng cho từng trò chơi.

---

## Quy tắc tính điểm

Người cầm chương (ở 3 cây) hoặc Người thắng (ở Sâm) **không điền điểm** — bot tự tính, vì người thắng/chương ăn/trả trực tiếp với từng người nên tổng một ván luôn bằng 0:

```
Người chơi:  Hương, Hằng, Toàn, Thu     (thứ tự chỗ ngồi)
Bạn gõ:      -5, -10, , -20
                    └── ô trống = Toàn (thắng/chương)

Bot tính:    Toàn = -(-5 + -10 + -20) = +35
Kết quả:     Hương -5 │ Hằng -10 │ Toàn +35 │ Thu -20      → tổng = 0 ✓
```

`0` là **điểm thật** (hòa), không phải dấu người thắng/chương. Người thắng/chương vẫn để ô trống.

---

## Cách nhập một ván

### 1. Theo vị trí (nhanh nhất — số ô phải đúng số chỗ ngồi)

| Gõ | Nghĩa |
|---|---|
| `-5, 5, , 6` | ô trống = Toàn thắng / cầm chương |
| `-5, 5, c, 6` / `-5, 5, t, 6` | `c` / `t` cũng là cầm chương / thắng |
| `-5, 5, 6,` | ô trống ở cuối $\rightarrow$ Thu thắng / cầm chương |
| `, 5, -7, 6` | ô trống ở đầu $\rightarrow$ Hương thắng / cầm chương |
| `-5, 5, , x` | `x` = Thu bỏ ván này (ngồi ngoài) |
| `-5,5,,6` | khoảng trắng tùy ý |

### 2. Theo tên (khi muốn ghi rõ)

| Gõ | Nghĩa |
|---|---|
| `Hương -5, Hằng 5, Toàn, Thu 6` | tên trần không kèm số = người thắng / cầm chương |
| `Toàn*, Hương -5, Hằng 5, Thu 6` | dấu `*` = người thắng / cầm chương |
| `c:Toàn Hương -5 Hằng 5 Thu 6` | tiền tố `c:` = cầm chương (3 cây) |
| `thang:Toàn Hương -5 Hằng -10 Thu -20` | tiền tố `thang:` (hoặc `t:`, `win:`) = người thắng (Sâm) |
| `Hương -5, Hằng 5, Thu 6` | thiếu Toàn $\rightarrow$ tự suy ra Toàn thắng / cầm chương |

- Tên không phân biệt hoa/thường và không cần gõ dấu (`hang` = `Hằng`).
- Bot chỉ tự bắt tin nhắn trần khi nó **chắc chắn** là kết quả ván, nên chat thường (*"tối nay đánh tiếp không"*) không bị ghi nhầm.

---

## Lệnh

**Telegram dùng `/`, Zalo dùng `#`** — Zalo không có menu lệnh dạng `/`. Cả hai prefix đều chạy được ở cả hai nền tảng; riêng phần hướng dẫn thì in đúng prefix của nền tảng đang dùng.

| Lệnh | Việc |
|---|---|
| `/help` · `#help` | Hướng dẫn sử dụng (tự theo trò chơi hiện tại, hoặc `/help sam`, `/help 3cay`) |
| `/nguoichoi Hương, Hằng, Toàn, Thu` | Khai báo người chơi — **thứ tự này chính là thứ tự nhập điểm** |
| `/dsnguoi` | Xem danh sách và thứ tự chỗ |
| `/themnguoi Nam` · `/xoanguoi Nam` | Thêm / bỏ một người |
| `/banmoi` | Mở bàn mới (hỏi chọn 3 cây hay Sâm) |
| `/banmoi 3cay [ghi chú]` · `/3cay [ghi chú]` | Mở bàn 3 cây |
| `/banmoi sam [ghi chú]` · `/sam [ghi chú]` | Mở bàn Sâm |
| `/ketthuc` | Chốt bàn đang chơi |
| `/v -5, 5, , 6` | Ghi một ván |
| `/undo` | Huỷ ván vừa ghi |
| `/xoa 3` · `/xoa 3 5 7` | Xoá ván theo số thứ tự |
| `/khoiphuc 3` | Lấy lại ván đã xoá |
| `/sua 3 -5, 5, , 6` | Nhập lại ván số 3 (giữ nguyên số ván) |
| `/tong` | Điểm luỹ kế bàn đang chơi |
| `/lichsu 10` | 10 ván gần nhất |
| `/web` | Link xem bàn đang chơi trên điện thoại |
| `/web doilink` | Đổi link nếu lỡ lọt ra ngoài nhóm |
| `/chiase` · `/moi` | Lấy link mời bạn bè dùng bot (mỗi người một link riêng) |
| `/thongke` | Thống kê người dùng & nguồn giới thiệu — **chỉ admin** |
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

## Thống kê người dùng & nguồn giới thiệu

Bot đếm được có bao nhiêu người đang dùng, hôm nay ai còn dùng, và **người mới đến từ ai** — người mới không phải nhập mã hay trả lời câu hỏi nào.

### Người share: một lệnh, một link

```
/chiase
→ 🔗 Link mời bạn bè dùng bot
  https://t.me/<bot>?start=r_AB12CD
  Gửi link này cho bạn bè, họ bấm vào là dùng được ngay.
  🌱 Đã có 3 người vào bot từ link của bạn.
```

Mỗi người có một mã riêng nằm trong link. Bạn bè bấm link $\rightarrow$ nhấn **Start** $\rightarrow$ dùng bot bình thường; bot ghi nhận nguồn im lặng, không hiện gì trong chat.

Người dùng Zalo nhận link dạng `https://<WEB_PUBLIC_URL>/i/AB12CD` — một trang nhỏ trên server của bạn, vì Zalo Bot Platform **không hỗ trợ tham số trong link**.

### Ba luật gán nguồn

| Điều kiện | Nguồn | Độ tin cậy |
|---|---|---|
| Người mới bấm link `?start=r_MÃ` (kể cả `?startgroup=`, Telegram gửi `/start@bot r_MÃ` vào nhóm) | `link` | **chắc chắn** |
| Người mới nhắn lần đầu trong chat đã có người dùng bot trước → quy về người xuất hiện sớm nhất ở chat đó | `group` | suy đoán |
| Có **đúng một** mã được bấm ở `/i/<mã>` trong 30 phút gần nhất mà chưa ai nhận | `landing` | suy đoán |

Luật 2 và 3 chỉ chạy với người hoàn toàn mới. Luật 1 chạy cả với người cũ, để nâng một bản ghi từ *suy đoán* lên *chắc chắn* khi họ bấm link thật. Bot không tự giới thiệu chính mình, không tạo vòng trong cây, và không ghi đè nguồn đã chắc chắn.

> ⚠️ Số `suy đoán` là **phỏng đoán, không phải sự thật** — nhất là trên Zalo, nơi chỉ có mốc thời gian để ghép. Đọc thống kê thì tách riêng hai cột `chắc chắn` / `suy đoán`.

### Xem số liệu

- **`/thongke` trong chat** (chỉ `ADMIN_USER_IDS`): người dùng, DAU/MAU, nguồn giới thiệu, K-factor, top người mời. Ai chưa phải admin gõ vào sẽ được bot in ra `user_id` của họ để bạn dán vào `.env`.
- **Trang `/admin?k=<ADMIN_STATS_TOKEN>`**: 3 tab (Tổng quan / Giới thiệu / Nhóm), biểu đồ 30 ngày và giờ cao điểm, bảng top người mời — cùng một PWA với trang xem bàn.
- **`GET /api/stats?k=<ADMIN_STATS_TOKEN>`**: JSON thô, dùng chung nguồn số với `/thongke` nên hai chỗ không bao giờ lệch nhau.

Thiếu `ADMIN_STATS_TOKEN` thì cả trang `/admin` và API đều trả 404.

### Bot lưu những gì

`bot_users`: id người dùng do nền tảng cấp, tên hiển thị, username (chỉ Telegram), mã giới thiệu, người giới thiệu, lần đầu/lần cuối thấy, số tin nhắn. `chat_members`: ai xuất hiện ở chat nào. `usage_events`: mỗi lệnh hoặc ván được ghi (không ghi tin nhắn tán gẫu, không lưu nội dung tin nhắn), tự xoá sau `USAGE_RETENTION_DAYS`. `ref_clicks`: mã + thời điểm + **hash** của User-Agent và IP, không lưu bản gốc.

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
| `ADMIN_USER_IDS` | Ai được gõ `/thongke`, dạng `telegram:123,zalo:abc`. Trống = không ai |
| `ADMIN_STATS_TOKEN` | Token mở `/admin?k=…` và `/api/stats?k=…`. Trống = tắt hẳn cả hai |
| `TELEGRAM_BOT_USERNAME` | Ghi đè username bot; thường không cần vì bot tự lấy bằng `getMe` |
| `ZALO_BOT_LINK` | Link mở bot Zalo, để trang `/i/<mã>` biết chuyển tiếp đi đâu |
| `REF_CLICK_WINDOW_MIN` | Cửa sổ ghép click trang mời với người dùng Zalo mới (mặc định 30 phút) |
| `USAGE_RETENTION_DAYS` | Giữ log lưu lượng bao nhiêu ngày (mặc định 180) |
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
| [`ghibai/webserver.py`](ghibai/webserver.py) | aiohttp: `/zalo/webhook`, `/api/board`, `/api/stats`, `/i/<mã>`, `/healthz`, file build của web |
| [`ghibai/webapi.py`](ghibai/webapi.py) | Payload JSON cho trang web và trang thống kê; xác thực bằng token trong link |
| [`ghibai/tracking.py`](ghibai/tracking.py) | Định danh người dùng + 3 luật gán nguồn giới thiệu |
| [`ghibai/stats.py`](ghibai/stats.py) | Tổng hợp số liệu dùng chung cho `/thongke` và `/api/stats` |
| [`ghibai/invite.py`](ghibai/invite.py) | Trang `/i/<mã>`: ghi log click rồi chuyển tiếp sang bot |
| [`web/`](web/) | Trang web React + Vite + shadcn/ui, PWA, ưu tiên mobile |
| [`ghibai/bot.py`](ghibai/bot.py) | Chạy song song cả hai nền tảng |
| [`ghibai/cli.py`](ghibai/cli.py) | `ghibai-zalo` — quản lý webhook |
| [`docs/index.md`](docs/index.md) | **Cẩm nang Tra cứu Kỹ thuật & Danh mục Mã nguồn Toàn diện** |

Mỗi phòng chat có danh sách người chơi và lịch sử **hoàn toàn riêng biệt**, kể cả khi Telegram và Zalo tình cờ trùng id gốc.

### Vài chỗ đáng lưu ý

- **Zalo gửi lại update khi endpoint trả lời chậm.** Webhook trả `200` ngay rồi xử lý nền (vì `/export` gọi Google Sheet mất vài giây), và chặn trùng theo `message_id` — ghi trùng một ván sẽ làm sai toàn bộ số điểm.
- **Zalo giới hạn 2000 ký tự/tin**, Telegram 4096 $\rightarrow$ message dài bị cắt theo dòng.
- **Zalo chỉ hỗ trợ `<b> <i> <u> <s>`**, không có `<pre>`/`<code>`, nên bảng căn cột bằng monospace sẽ vỡ font $\rightarrow$ bản Zalo trình bày mỗi ván một khối thay vì bảng.
