/**
 * Token nam trong link bot gui (?k=...). Luu lai de ban PWA da cai — mo tu icon man
 * hinh chinh khong co query string — van vao dung nhom cu.
 */

const STORAGE_KEY = "ghibai:token"

export function readToken(): string | null {
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
