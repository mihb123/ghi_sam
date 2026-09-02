export type ActiveTab = "bang" | "van"

const TAB_STORAGE_KEY = "ghibai:tab"
const REFRESH_STORAGE_KEY = "ghibai:refresh-interval"

export const DEFAULT_TAB: ActiveTab = "bang"
export const DEFAULT_REFRESH_INTERVAL = 15 // seconds

export type RefreshOption = {
  value: number
  label: string
  description?: string
  isDefault?: boolean
}

export const REFRESH_OPTIONS: readonly RefreshOption[] = [
  { value: 5, label: "5 giây", description: "Rất nhanh" },
  { value: 10, label: "10 giây", description: "Nhanh" },
  { value: 15, label: "15 giây", description: "Tiêu chuẩn", isDefault: true },
  { value: 30, label: "30 giây", description: "Tiết kiệm dữ liệu" },
  { value: 60, label: "1 phút", description: "Tiết kiệm pin" },
  { value: 0, label: "Tắt tự động", description: "Chỉ làm mới thủ công" },
]

const VALID_INTERVALS = new Set(REFRESH_OPTIONS.map((opt) => opt.value))

/**
 * Đọc tab hiện tại: ưu tiên URL hash/query -> localStorage -> mặc định "bang"
 */
export function readStoredTab(): ActiveTab {
  if (typeof window === "undefined") {
    return DEFAULT_TAB
  }

  // 1. Kiểm tra URL hash (#van / #bang)
  const hash = window.location.hash.replace(/^#/, "").trim()
  if (hash === "bang" || hash === "van") {
    return hash
  }

  // 2. Kiểm tra search params (?tab=van / ?tab=bang)
  try {
    const tabParam = new URLSearchParams(window.location.search).get("tab")?.trim()
    if (tabParam === "bang" || tabParam === "van") {
      return tabParam
    }
  } catch {
    // URL parsing fallback
  }

  // 3. Đọc từ localStorage
  try {
    const stored = window.localStorage.getItem(TAB_STORAGE_KEY)
    if (stored === "bang" || stored === "van") {
      return stored
    }
  } catch {
    // Safari chế độ riêng tư có thể chặn localStorage
  }

  return DEFAULT_TAB
}

/**
 * Lưu tab được chọn vào localStorage và cập nhật URL hash để giữ trạng thái khi reload
 */
export function writeStoredTab(tab: ActiveTab): void {
  if (typeof window === "undefined") {
    return
  }

  try {
    window.localStorage.setItem(TAB_STORAGE_KEY, tab)
  } catch {
    // Bỏ qua nếu không lưu được
  }

  // Cập nhật hash trên URL mà không gây nhảy trang/cuộn lại
  try {
    const newUrl = `${window.location.pathname}${window.location.search}#${tab}`
    window.history.replaceState(null, "", newUrl)
  } catch {
    // Bỏ qua nếu không hỗ trợ replaceState
  }
}

/**
 * Đọc cấu hình chu kỳ làm mới (tính bằng giây) từ localStorage
 */
export function readStoredRefreshInterval(): number {
  if (typeof window === "undefined") {
    return DEFAULT_REFRESH_INTERVAL
  }

  try {
    const raw = window.localStorage.getItem(REFRESH_STORAGE_KEY)
    if (raw !== null) {
      const parsed = parseInt(raw, 10)
      if (!isNaN(parsed) && VALID_INTERVALS.has(parsed)) {
        return parsed
      }
    }
  } catch {
    // Safari private mode fallback
  }

  return DEFAULT_REFRESH_INTERVAL
}

/**
 * Lưu cấu hình chu kỳ làm mới vào localStorage
 */
export function writeStoredRefreshInterval(intervalSec: number): void {
  if (typeof window === "undefined") {
    return
  }

  try {
    window.localStorage.setItem(REFRESH_STORAGE_KEY, String(intervalSec))
  } catch {
    // Bỏ qua nếu không lưu được
  }
}

/**
 * Format chu kỳ làm mới cho footer và nhãn UI
 */
export function formatRefreshInterval(seconds: number): string {
  if (seconds <= 0) {
    return "đã tắt tự làm mới"
  }
  if (seconds === 60) {
    return "mỗi 1 phút"
  }
  return `mỗi ${seconds} giây`
}
