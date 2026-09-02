import { CrownIcon } from "lucide-react"

import type { Player, RoundEntry } from "@/lib/api"
import { hhmm, signed, tone } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

type RoundsViewProps = {
  rounds: RoundEntry[]
  players: Player[]
  voidedSeqs: number[]
  gameType?: string
}

export function RoundsView({
  rounds,
  players,
  voidedSeqs,
  gameType = "3cay",
}: RoundsViewProps) {
  // Van moi nhat len dau: mo dien thoai giua ban la de xem van vua ghi.
  const newestFirst = [...rounds].reverse()

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 md:hidden">
        {newestFirst.map((round) => (
          <RoundCard
            key={round.seq}
            round={round}
            players={players}
            gameType={gameType}
          />
        ))}
      </div>

      <Card className="hidden py-0 md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-14">Ván</TableHead>
              <TableHead className="w-16">Giờ</TableHead>
              {players.map((player) => (
                <TableHead key={player.id} className="text-right">
                  {player.name}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {newestFirst.map((round) => (
              <TableRow key={round.seq}>
                <TableCell className="tabular-nums">{round.seq}</TableCell>
                <TableCell className="tabular-nums text-muted-foreground">
                  {hhmm(round.at)}
                </TableCell>
                {players.map((player) => (
                  <TableCell key={player.id} className="text-right">
                    <ScoreCell round={round} player={player} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {voidedSeqs.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          Đã xoá: ván {voidedSeqs.join(", ")} — khôi phục bằng lệnh{" "}
          <code className="rounded bg-muted px-1 py-0.5">/khoiphuc</code> trong
          nhóm chat.
        </p>
      ) : null}
    </div>
  )
}

function RoundCard({
  round,
  players,
  gameType,
}: {
  round: RoundEntry
  players: Player[]
  gameType?: string
}) {
  const banker = players.find((player) => player.id === round.bankerId)
  const roleLabel = gameType === "sam" ? "thắng" : "chương"

  return (
    <div className="rounded-xl bg-card p-3 ring-1 ring-foreground/10">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">Ván {round.seq}</span>
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <CrownIcon className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate">{roleLabel}: {banker?.name ?? "?"}</span>
          <span aria-hidden>·</span>
          <span className="tabular-nums">{hhmm(round.at)}</span>
        </span>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
        {players.map((player) => (
          <div
            key={player.id}
            className="flex items-baseline justify-between gap-2 text-sm"
          >
            <span className="truncate text-muted-foreground">
              {player.name}
            </span>
            <ScoreCell round={round} player={player} />
          </div>
        ))}
      </div>
    </div>
  )
}

// Khong co diem = bo van, khac han diem 0 (0 la diem that).
function ScoreCell({ round, player }: { round: RoundEntry; player: Player }) {
  const score = round.scores[String(player.id)]

  if (score === undefined) {
    return (
      <span className="shrink-0 text-muted-foreground" title="bỏ ván">
        —
      </span>
    )
  }
  return (
    <span
      className={cn("shrink-0 font-medium tabular-nums", tone(score))}
    >
      {signed(score)}
    </span>
  )
}
