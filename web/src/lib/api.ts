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
