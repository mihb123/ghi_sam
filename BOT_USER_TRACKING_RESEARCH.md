# Hướng Dẫn Định Danh Người Dùng, Tracking Giới Thiệu & Thống Kê Lưu Lượng Cho Zalo Bot và Telegram Bot

> ## ✅ Trạng thái: đã triển khai (khác một số điểm so với bản nghiên cứu này)
>
> Tính năng đã được cài vào repo. **Đọc [`README.md` — Thống kê người dùng & nguồn giới thiệu](README.md#thống-kê-người-dùng--nguồn-giới-thiệu) và [`docs/index.md` §4.8](docs/index.md) để lấy thiết kế thực tế**; tài liệu này giữ lại làm bản nghiên cứu gốc.
>
> **Hai điểm đã kiểm chứng lại và khác với bản nghiên cứu:**
>
> 1. **Telegram `?startgroup=<payload>` CÓ trả payload về** — [tài liệu Telegram](https://core.telegram.org/bots/features#deep-linking) ghi rõ bot nhận được tin nhắn dạng `/start@your_bot <payload>` ngay trong nhóm. Bản nghiên cứu chỉ đề cập `?start=`. Payload tối đa 64 ký tự, chỉ `A-Z a-z 0-9 _ -`.
> 2. **Zalo Bot Platform không có deep link kèm tham số** — không tìm được tài liệu nào về start param, cũng không có event cho biết ai đã thêm bot vào nhóm. Nên **cơ chế "nhập mã `REF 8899`" ở mục 2.B đã bị bỏ**: yêu cầu chính là *không hỏi người dùng câu nào*. Thay vào đó link chia sẻ của người dùng Zalo trỏ về trang `/i/<mã>` trên server của mình, ghi log click rồi chuyển tiếp sang bot; việc ghép với người dùng mới là **suy đoán theo cửa sổ thời gian** và được đánh dấu `confidence = inferred`.
>
> **Những chỗ khác so với bản nghiên cứu:** stack thật là Python + SQLite (không phải Node + PostgreSQL); **không** làm `credits_balance` / `role` / `tier` / thưởng lượt ở mục 6 (schema chừa sẵn chỗ để thêm sau); có thêm luật thứ 3 không nằm trong bản nghiên cứu — người mới nhắn lần đầu trong nhóm đã có người dùng bot thì quy về người xuất hiện sớm nhất ở nhóm đó.

---

Tài liệu này tổng hợp toàn bộ giải pháp kỹ thuật và kiến trúc dữ liệu để:
1. **Định danh chính xác từng người dùng** đang tương tác với bot.
2. **Theo dõi nguồn gốc chia sẻ (Referral / Viral Tracking)**: Biết ai đã giới thiệu bot cho ai khi được share lan truyền.
3. **Thống kê lưu lượng sử dụng (Usage Analytics)**: Đo lường số request, DAU/MAU, chi phí token (nếu có dùng AI).
4. **Chuẩn bị nền tảng cho các tính năng nâng cao**: Phân quyền, giới hạn hạn mức (Quota/Rate limiting), nạp credit, CRM/Broadcasting.

---

## 1. Cơ Chế Định Danh Người Dùng (User Identity)

Cả Zalo Bot Platform (`bot.zapps.me`) và Telegram Bot Platform đều gửi thông tin định danh người dùng qua **Webhook Payload** mỗi khi có tương tác.

### Bảng so sánh dữ liệu nhận được qua Webhook

| Thuộc tính | Zalo Bot Platform (`bot.zapps.me`) | Telegram Bot Platform |
| :--- | :--- | :--- |
| **ID người dùng (Unique ID)** | `result.message.from.id`<br>*(Chuỗi hash duy nhất do Zalo cấp)* | `message.from.id`<br>*(Số nguyên định danh duy nhất vĩnh viễn)* |
| **Tên hiển thị** | `result.message.from.display_name`<br>*(Tên Zalo của user)* | `message.from.first_name`<br>`message.from.last_name` |
| **Username** | *(Chưa hỗ trợ trường username public)* | `message.from.username`<br>*(Ví dụ: `@johndoe`)* |
| **Loại hội thoại** | `result.message.chat.chat_type`<br>(`PRIVATE` hoặc `GROUP`) | `message.chat.type`<br>(`private`, `group`, `supergroup`) |
| **Chat ID phản hồi** | `result.message.chat.id` | `message.chat.id` |
| **Xác thực Webhook** | Header: `X-Bot-Api-Secret-Token` | Header: `X-Telegram-Bot-Api-Secret-Token` |

---

## 2. Giải Pháp Theo Dõi Nguồn Gốc Chia Sẻ (Referral / Viral Tracking)

Khi User A chia sẻ bot cho User B, User B lại chia sẻ cho User C:

```
[User A] --(Chia sẻ link/mã)--> [User B] --(Chia sẻ link/mã)--> [User C]
```

### A. Đối với Telegram: Tận dụng cơ chế Deep Linking (Tự động 100%)

> ✅ **Đã dùng cách này.** Bổ sung: `https://t.me/<bot>?startgroup=ref_<CODE>` cũng trả payload về (bot nhận `/start@<bot> ref_<CODE>` trong nhóm), nên link thêm bot vào nhóm cũng track được — cùng một đoạn code xử lý.

Telegram hỗ trợ truyền tham số trực tiếp qua lệnh `/start`:

1. **Cấu trúc link chia sẻ:**
   ```text
   https://t.me/<bot_username>?start=ref_<USER_ID_HOAC_REFERRAL_CODE>
   ```
2. **Luồng hoạt động:**
   - User A lấy link mời từ bot: `https://t.me/my_assistant_bot?start=ref_USERA123`.
   - User B bấm vào link và nhấn nút **Start**.
   - Telegram Webhook gửi tin nhắn đầu tiên về server của bạn với nội dung:
     ```json
     {
       "message": {
         "from": { "id": 99887766, "first_name": "Nguyen B" },
         "text": "/start ref_USERA123"
       }
     }
     ```
   - Server phân tích chuỗi `/start ref_USERA123` -> Tự động lưu `User B` và gán `referred_by_id = User A`.

---

### B. Đối với Zalo Bot Platform: Cơ chế Mã giới thiệu (Invite Code / Check-in)

> ❌ **Không dùng cách này.** Bắt người mới nhập `REF 8899` là hỏi trực tiếp — đúng thứ cần tránh. Cách đã cài: link `/i/<mã>` trên server của mình ghi log click rồi chuyển tiếp sang bot, sau đó ghép với người dùng Zalo mới xuất hiện trong 30 phút (chỉ ghép khi trong cửa sổ đó có **đúng một** mã được bấm), và luôn đánh dấu là suy đoán.
Zalo Bot Platform hiện tại nhận tin nhắn trực tiếp qua cửa sổ chat Zalo. Bạn có thể áp dụng các cách sau:

1. **Cơ chế Mã giới thiệu (Khuyên dùng):**
   - Mỗi người dùng có một mã giới thiệu ngắn (ví dụ: `REF-8899`).
   - Khi người mới nhắn tin lần đầu (bot kiểm tra trong Database chưa thấy `from.id`), bot gửi lời chào:
     > *"Chào mừng bạn đến với bot! Nếu bạn được bạn bè giới thiệu, hãy nhập mã mời (ví dụ: `REF 8899`) để cả 2 cùng nhận thêm 20 lượt dùng miễn phí!"*
   - Khi User B nhập mã, hệ thống liên kết B vào cây giới thiệu của A và kích hoạt phần thưởng.
2. **Lệnh tạo mã mời nhanh:**
   - User A chỉ cần gõ `/share` hoặc `/mycode` -> Bot tạo sẵn mẫu tin nhắn có mã để A chỉ việc chuyển tiếp (forward) cho bạn bè.
3. **Mở rộng với Zalo Mini App:**
   - Đính kèm URL Mini App dạng: `https://zalo.me/s/.../?referrer=USER_A_ID`. Khi mở Mini App, SDK tự động trích xuất query param để ghi nhận nguồn.

---

## 3. Thiết Kế Cơ Sở Dữ Liệu Chuẩn (Database Schema)

Dưới đây là thiết kế Schema SQL (PostgreSQL/MySQL) tối ưu cho việc tracking, đo lưu lượng và mở rộng tính năng:

```sql
-- 1. BẢNG NGƯỜI DÙNG (Quản lý User từ cả 2 nền tảng)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(20) NOT NULL,              -- 'telegram' | 'zalo'
    platform_user_id VARCHAR(100) NOT NULL,     -- ID từ Telegram/Zalo
    display_name VARCHAR(255),
    username VARCHAR(100),
    referral_code VARCHAR(50) UNIQUE NOT NULL,  -- Mã giới thiệu riêng của user
    referred_by_id UUID REFERENCES users(id),   -- ID người đã giới thiệu (nếu có)
    
    -- Phân quyền & Giới hạn
    role VARCHAR(20) DEFAULT 'user',            -- 'user' | 'vip' | 'admin' | 'banned'
    tier VARCHAR(20) DEFAULT 'free',            -- 'free' | 'pro' | 'enterprise'
    credits_balance INT DEFAULT 50,             -- Số lượt dùng / điểm khả dụng
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(platform, platform_user_id)
);

-- 2. BẢNG GHI LOG SỬ DỤNG (Thống kê lưu lượng, đo lường chi phí)
CREATE TABLE usage_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,
    action_type VARCHAR(50) NOT NULL,           -- 'text_message' | 'image_gen' | 'ai_chat' | 'command'
    input_content_length INT DEFAULT 0,
    tokens_used INT DEFAULT 0,                  -- Số token AI tiêu thụ (nếu có)
    cost_estimate NUMERIC(10, 6) DEFAULT 0,     -- Chi phí ước tính (USD/VND)
    response_time_ms INT,                       -- Thời gian xử lý của bot
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. BẢNG THEO DÕI LỊCH SỬ GIỚI THIỆU & THƯỞNG (Referral & Rewards)
CREATE TABLE referral_history (
    id BIGSERIAL PRIMARY KEY,
    inviter_id UUID NOT NULL REFERENCES users(id),
    invitee_id UUID NOT NULL REFERENCES users(id),
    reward_granted BOOLEAN DEFAULT FALSE,
    reward_credits INT DEFAULT 20,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tạo Index để tối ưu truy vấn thống kê
CREATE INDEX idx_users_platform_id ON users(platform, platform_user_id);
CREATE INDEX idx_usage_logs_user_id_date ON usage_logs(user_id, created_at);
CREATE INDEX idx_users_referred_by ON users(referred_by_id);
```

---

## 4. Code Mẫu Xử Lý Webhook (Node.js / Express / TypeScript)

```typescript
import express, { Request, Response } from "express";

const app = express();
app.use(express.json());

// Helper tạo mã giới thiệu ngẫu nhiên
function generateReferralCode(prefix: string): string {
  return `${prefix.toUpperCase()}-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;
}

// Logic kiểm tra / tạo mới User kèm Referral Tracking
async function getOrCreateUser(
  platform: "zalo" | "telegram",
  platformUserId: string,
  displayName: string,
  referralInput?: string
) {
  let user = await db.users.findOne({ platform, platform_user_id: platformUserId });

  if (!user) {
    let inviterUser = null;
    
    // Nếu có mã mời từ Deep Link hoặc người dùng gõ
    if (referralInput) {
      const cleanCode = referralInput.replace(/^ref_/i, "").trim().toUpperCase();
      inviterUser = await db.users.findOne({ referral_code: cleanCode });
    }

    const initialCredits = 50 + (inviterUser ? 20 : 0); // Thưởng thêm 20 lượt nếu có người mời

    user = await db.users.create({
      platform,
      platform_user_id: platformUserId,
      display_name: displayName,
      referral_code: generateReferralCode(platform === "zalo" ? "ZL" : "TG"),
      referred_by_id: inviterUser ? inviterUser.id : null,
      credits_balance: initialCredits,
      role: "user",
      tier: "free",
    });

    // Cộng thưởng cho người đã giới thiệu
    if (inviterUser) {
      await db.users.incrementCredits(inviterUser.id, 20);
      await db.referral_history.create({
        inviter_id: inviterUser.id,
        invitee_id: user.id,
        reward_credits: 20,
        reward_granted: true,
      });
    }
  } else {
    // Cập nhật last active
    await db.users.update(user.id, {
      last_active_at: new Date(),
      display_name: displayName,
    });
  }

  return user;
}

// ==========================================
// 1. WEBHOOK XỬ LÝ ZALO BOT (bot.zapps.me)
// ==========================================
app.post("/webhook/zalo", async (req: Request, res: Response) => {
  const secretToken = req.headers["x-bot-api-secret-token"];
  if (secretToken !== process.env.ZALO_WEBHOOK_SECRET) {
    return res.status(403).json({ message: "Unauthorized" });
  }

  const { event_name, message } = req.body.result || {};

  if (event_name === "message.text.received" && message) {
    const fromId = message.from.id;
    const displayName = message.from.display_name || "Zalo User";
    const text = (message.text || "").trim();

    // Kiểm tra xem tin nhắn có phải mã mời không (ví dụ: 'REF ZL-1234')
    let refCode: string | undefined;
    if (text.toUpperCase().startsWith("REF ")) {
      refCode = text.split(" ")[1];
    }

    const user = await getOrCreateUser("zalo", fromId, displayName, refCode);

    // Ghi log lưu lượng sử dụng
    await db.usage_logs.create({
      user_id: user.id,
      platform: "zalo",
      action_type: "text_message",
      input_content_length: text.length,
    });

    // TODO: Xử lý logic nghiệp vụ và gọi API sendMessage của Zalo Bot
  }

  return res.json({ ok: true });
});

// ==========================================
// 2. WEBHOOK XỬ LÝ TELEGRAM BOT
// ==========================================
app.post("/webhook/telegram", async (req: Request, res: Response) => {
  const secretToken = req.headers["x-telegram-bot-api-secret-token"];
  if (secretToken !== process.env.TELEGRAM_WEBHOOK_SECRET) {
    return res.status(403).json({ message: "Unauthorized" });
  }

  const message = req.body.message;
  if (message && message.text) {
    const fromId = message.from.id.toString();
    const displayName = [message.from.first_name, message.from.last_name].filter(Boolean).join(" ");
    const text = message.text.trim();

    // Bắt tham số deep link dạng: /start ref_TG-1234
    let startParam: string | undefined;
    if (text.startsWith("/start ")) {
      startParam = text.split(" ")[1];
    }

    const user = await getOrCreateUser("telegram", fromId, displayName, startParam);

    // Ghi log lưu lượng sử dụng
    await db.usage_logs.create({
      user_id: user.id,
      platform: "telegram",
      action_type: "text_message",
      input_content_length: text.length,
    });

    // TODO: Xử lý logic phản hồi tin nhắn Telegram
  }

  return res.json({ ok: true });
});
```

---

## 5. Các Chỉ Số Thống Kê Lưu Lượng Cần Theo Dõi (Analytics Metrics)

Dựa trên bảng `usage_logs` và `users`, bạn có thể xuất ra các Dashboard thống kê:

1. **Chỉ số Người Dùng & Tăng Trưởng:**
   - **DAU (Daily Active Users)**: Số user nhắn tin trong ngày.
   - **MAU (Monthly Active Users)**: Số user nhắn tin trong tháng.
   - **New Users**: Số lượng người dùng mới mỗi ngày theo từng platform.
2. **Chỉ số Lan Truyền (Viral Metrics):**
   - **Hệ số Lan truyền (K-factor / Viral Coefficient)**: Trung bình mỗi user mời được bao nhiêu user mới.
   - **Top Referrers (Bảng xếp hạng đại sứ)**: Top những người chia sẻ bot nhiều nhất.
3. **Chỉ số Lưu Lượng & Chi Phí (Usage & Cost):**
   - Tổng số request / tin nhắn bot xử lý mỗi ngày.
   - Lượng token AI tiêu thụ trung bình trên mỗi user.
   - Phân bố giờ cao điểm tương tác trong ngày.

---

## 6. Lộ Trình Phát Triển Các Tính Năng Nâng Cao Sau Này

| Nhóm tính năng | Chi tiết triển khai |
| :--- | :--- |
| **Phân tầng & Giới hạn (Rate Limiting / Quota)** | - Gói **Free**: 20 tin nhắn/ngày.<br>- Gói **Pro/VIP**: Không giới hạn tốc độ, ưu tiên thời gian phản hồi.<br>- Tự động chặn khi hết `credits_balance`. |
| **Cơ chế Gamification & Thưởng lượt** | - Mời 1 bạn mới: Tặng 20 credits.<br>- Điểm danh hàng ngày (`/daily`): Tặng 5 credits. |
| **Tích hợp Thanh toán (Monetization)** | - Tích hợp cổng thanh toán tự động (VietQR / SePay / Momo / Stripe).<br>- User quét mã QR chuyển khoản kèm cú pháp `NAP <USER_ID>` -> Webhook ngân hàng tự động nạp credits vào bot. |
| **Chăm sóc & Tiếp thị (CRM / Broadcasting)** | - Lọc danh sách user không hoạt động > 7 ngày để gửi tin nhắn chào mời quay lại.<br>- Gửi thông báo cập nhật tính năng mới tới toàn bộ người dùng hoặc chỉ nhóm VIP. |
| **Phân quyền Quản trị (Admin Panel)** | - Thêm lệnh `/admin_stats` trực tiếp trong bot cho người sở hữu.<br>- Khóa tài khoản (ban) các user có hành vi spam hoặc lạm dụng tài nguyên. |
