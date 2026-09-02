import { CrownIcon } from "lucide-react"

import type { Standing } from "@/lib/api"
import { signed, tone } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Card } from "@/components/ui/card"

export function StandingsList({
  standings,
  gameType = "3cay",
}: {
  standings: Standing[]
  gameType?: string
}) {
  const bankLabel = gameType === "sam" ? "lần thắng" : "lần chương"

  return (
    <Card className="gap-0 py-0">
      <ul className="divide-y">
        {standings.map((player, index) => (
          <li
            key={player.id}
            className="flex min-h-14 items-center gap-3 px-4 py-2.5"
          >
            <span className="w-4 shrink-0 text-sm tabular-nums text-muted-foreground">
              {index + 1}
            </span>

            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{player.name}</p>
              <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                {player.played} ván
                {player.banked > 0 ? (
                  <>
                    <span aria-hidden>·</span>
                    <CrownIcon className="size-3 shrink-0" aria-hidden />
                    {player.banked} {bankLabel}
                  </>
                ) : null}
              </p>
            </div>

            <span
              className={cn(
                "shrink-0 text-xl font-semibold tabular-nums",
                tone(player.total)
              )}
            >
              {signed(player.total)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
