# Trang web của bot ghi bài

Trang chỉ đọc để xem bàn 3 cây đang chơi: bảng xếp hạng và chi tiết từng ván.
Ưu tiên màn hình điện thoại, cài được lên màn hình chính (PWA).

React + Vite + TypeScript + [shadcn/ui](https://ui.shadcn.com) (style `base-nova`),
Tailwind v4. Xem hướng dẫn đầy đủ ở [README gốc](../README.md#trang-web-xem-trên-điện-thoại).

```bash
npm install
npm run dev          # http://localhost:5173, proxy /api sang bot đang chạy
npm run build        # ra dist/, bot phục vụ thư mục này
npm run typecheck
```

Dev server cần bot chạy sẵn ở `WEB_PORT` (mặc định 10240). Mở
`http://localhost:5173/?k=<token>` với token lấy từ lệnh `/web` trong nhóm chat.
Đổi cổng bot: `VITE_API_TARGET=http://127.0.0.1:8080 npm run dev`.

## Cấu trúc

| Đường dẫn | Việc |
|---|---|
| `src/App.tsx` | Bố cục màn hình + chọn trạng thái hiển thị |
| `src/hooks/use-board.ts` | Gọi API, tự làm mới 15 giây khi tab đang mở |
| `src/lib/api.ts` | Kiểu dữ liệu khớp `ghibai/webapi.py` |
| `src/lib/token.ts` | Token trong link `?k=`, lưu lại cho bản PWA đã cài |
| `src/components/` | Header, thẻ số liệu, bảng xếp hạng, chi tiết ván, trạng thái rỗng |
| `src/components/ui/` | Component shadcn/ui — thêm bằng `npx shadcn@latest add <tên>` |

## Vài quyết định

- **Một endpoint duy nhất** `/api/board`: cả màn hình chỉ cần một request mỗi lần làm mới.
- **Chi tiết ván: thẻ trên mobile, bảng từ `md:`** — bảng 6 cột trên điện thoại phải cuộn
  ngang mới đọc được.
- **Ván mới nhất nằm trên cùng**: mở điện thoại giữa bàn là để xem ván vừa ghi.
- **Không có màu nào đứng một mình**: điểm luôn kèm dấu `+`/`-` để không phụ thuộc màu.
- **Ô trống khác điểm 0**: người bỏ ván hiện `—`, còn `0` là điểm thật.
