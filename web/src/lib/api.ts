// Kieu du lieu khop 1-1 voi payload cua ghibai/webapi.py.

export type Chat = {
  title: string | null
  platform: string
}

export type SessionInfo = {
  id: number
  gameType?: "3cay" | "sam" | string
  note: string | null
  startedAt: string
  endedAt: string | null
  live: boolean
  played: number
}

export type Player = {
  id: number
  name: string
  seat: number
}

export type Standing = {
  id: number
  name: string
  total: number
  played: number
  banked: number
}

export type RoundEntry = {
  seq: number
  at: string
  /** Nguoi cam chuong khong tu dien diem, bot tinh ho de tong van = 0. */
  bankerId: number
  /** Khoa la player id dang chuoi. Thieu khoa = nguoi do bo van, khac han diem 0. */
  scores: Record<string, number>
}

export type Board = {
  chat: Chat
  session: SessionInfo | null
  players: Player[]
  standings: Standing[]
  rounds: RoundEntry[]
  voidedSeqs: number[]
  /** Tong diem ca ban; khac 0 nghia la co van bi loi. */
  checksum: number
  fetchedAt: string
}

// --- THONG KE (/api/stats, khop voi ghibai/stats.py) ---

export type StatsTotals = {
  users: number
  chats: number
  sessions: number
  rounds: number
  events: number
}

export type StatsUsers = {
  newToday: number
  new7d: number
  new30d: number
  /** Active = co it nhat 1 lenh / 1 van trong ky, khong tinh tin nhan tan gau. */
  dau: number
  wau: number
  mau: number
}

export type PlatformStat = {
  platform: string
  users: number
  new7d: number
  chats: number
  dau: number
}

export type DailyPoint = {
  day: string
  events: number
  activeUsers: number
  newUsers: number
}

export type Referrals = {
  attributed: number
  /** Bam link that (deep link Telegram) - chac chan. */
  exact: number
  /** Suy ra tu cung nhom hoac tu click trang moi - khong chac chan. */
  inferred: number
  inviters: number
  kFactor: number
  bySource: { source: string; count: number }[]
  topReferrers: {
    name: string | null
    platform: string
    code: string
    invited: number
  }[]
  recent: {
    invitee: string | null
    inviter: string | null
    platform: string
    source: string
    confidence: string
    at: string | null
  }[]
}

export type ChatStat = {
  title: string | null
  platform: string
  members: number
  rounds: number
  lastActiveAt: string | null
}

export type Stats = {
  generatedAt: string
  totals: StatsTotals
  users: StatsUsers
  byPlatform: PlatformStat[]
  daily: DailyPoint[]
  hourly: { hour: number; events: number }[]
  referrals: Referrals
  topCommands: { command: string; count: number }[]
  topChats: ChatStat[]
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

export async function fetchBoard(
  token: string,
  signal?: AbortSignal
): Promise<Board> {
  const response = await fetch(`/api/board?k=${encodeURIComponent(token)}`, {
    signal,
    headers: { Accept: "application/json" },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as Board
}

export async function fetchStats(
  token: string,
  signal?: AbortSignal
): Promise<Stats> {
  const response = await fetch(`/api/stats?k=${encodeURIComponent(token)}`, {
    signal,
    headers: { Accept: "application/json" },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as Stats
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string }
    if (body.error) {
      return body.error
    }
  } catch {
    // Body khong phai JSON (vi du loi tu reverse proxy) thi dung message mac dinh.
  }
  return `Máy chủ trả lỗi ${response.status}.`
}
