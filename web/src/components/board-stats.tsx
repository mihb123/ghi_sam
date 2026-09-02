import { ScrollTextIcon, TrophyIcon } from "lucide-react"

import type { Board } from "@/lib/api"
import { hhmm, signed, tone } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function BoardStats({ board }: { board: Board }) {
  const leader = board.standings[0] ?? null
  const session = board.session

  return (
    <div className="grid grid-cols-2 gap-3">
      <StatTile
        label="Dẫn đầu"
        icon={<TrophyIcon className="size-3.5" aria-hidden />}
        value={leader ? leader.name : "—"}
        hint={leader ? signed(leader.total) : "chưa có ván nào"}
        hintClassName={leader ? tone(leader.total) : undefined}
      />
      <StatTile
        label="Đã chơi"
        icon={<ScrollTextIcon className="size-3.5" aria-hidden />}
        value={`${session?.played ?? 0} ván`}
        hint={session ? `từ ${hhmm(session.startedAt)}` : "—"}
      />
    </div>
  )
}

type StatTileProps = {
  label: string
  icon: React.ReactNode
  value: string
  hint: string
  hintClassName?: string
}

function StatTile({ label, icon, value, hint, hintClassName }: StatTileProps) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="flex items-center gap-1.5 text-xs">
          {icon}
          {label}
        </CardDescription>
        <CardTitle className="truncate text-lg">{value}</CardTitle>
      </CardHeader>
      <CardContent>
        <p
          className={cn(
            "truncate text-sm font-medium tabular-nums",
            hintClassName ?? "text-muted-foreground"
          )}
        >
          {hint}
        </p>
      </CardContent>
    </Card>
  )
}
