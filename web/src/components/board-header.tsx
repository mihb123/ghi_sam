import { RefreshCwIcon, SettingsIcon } from "lucide-react"

import type { Board } from "@/lib/api"
import { ddmm, hhmm } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

type BoardHeaderProps = {
  board: Board | null
  loading: boolean
  onReload: () => void
  onOpenSettings?: () => void
}

export function BoardHeader({
  board,
  loading,
  onReload,
  onOpenSettings,
}: BoardHeaderProps) {
  const session = board?.session ?? null

  return (
    <header className="sticky top-0 z-30 border-b bg-background/95 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex max-w-2xl items-center gap-1.5 px-4 py-2">
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-heading font-medium">
            {board?.chat.title ?? "Bàn 3 cây"}
          </h1>
          <p className="truncate text-xs text-muted-foreground">
            {subtitle(board)}
          </p>
        </div>

        {session ? (
          <Badge variant={session.live ? "default" : "secondary"}>
            {session.live ? "Đang chơi" : "Đã chốt"}
          </Badge>
        ) : null}

        <Button
          variant="ghost"
          size="icon-lg"
          className="size-11"
          aria-label="Tải lại"
          onClick={onReload}
        >
          <RefreshCwIcon className={cn(loading && "animate-spin")} />
        </Button>

        {onOpenSettings ? (
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11"
            aria-label="Cài đặt"
            onClick={onOpenSettings}
          >
            <SettingsIcon />
          </Button>
        ) : null}
      </div>
    </header>
  )
}

function subtitle(board: Board | null): string {
  if (!board?.session) {
    return "Chưa có bàn nào"
  }
  const { session } = board
  const started = `${ddmm(session.startedAt)} · ${hhmm(session.startedAt)}`
  return session.note ? `${started} · ${session.note}` : started
}

