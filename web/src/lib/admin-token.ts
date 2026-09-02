/**
 * Token quan tri nam trong link /admin?k=... (ADMIN_STATS_TOKEN trong .env). Luu rieng
 * key voi token xem ban (lib/token.ts) de mo trang /admin khong lam mat link nhom dang xem.
 */

const STORAGE_KEY = "ghibai:admin-token"

export function readAdminToken(): string | null {
  const fromUrl = new URLSearchParams(window.location.search).get("k")?.trim()
  if (fromUrl) {
    safeWrite(fromUrl)
    return fromUrl
  }
  return safeRead()
}

function safeRead(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Safari che do rieng tu chan localStorage; luc do chi song bang ?k= tren URL.
    return null
  }
}

function safeWrite(token: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, token)
  } catch {
    // Khong luu duoc thi thoi, khong anh huong lan xem hien tai.
  }
}
