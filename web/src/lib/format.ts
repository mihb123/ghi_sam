const TIME = new Intl.DateTimeFormat("vi-VN", {
  hour: "2-digit",
  minute: "2-digit",
})
const DATE = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
})

/** Luon hien dau: mau sac mot minh khong du de phan biet thang/thua (WCAG). */
export function signed(value: number): string {
  return value > 0 ? `+${value}` : String(value)
}

export function tone(value: number): string {
  if (value > 0) return "text-win"
  if (value < 0) return "text-lose"
  return "text-muted-foreground"
}

export function hhmm(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? "" : TIME.format(date)
}

export function ddmm(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? "" : DATE.format(date)
}
