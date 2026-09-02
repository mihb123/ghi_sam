import { cn } from "@/lib/utils"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export type StatTileProps = {
  label: string
  value: string | number
  hint?: string
  tone?: "default" | "win"
}

/** 2 cot tren dien thoai, 4 cot tu tablet: so lieu khong bao gio bi xo lech mot hang le. */
export function StatGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{children}</div>
  )
}

export function StatTile({ label, value, hint, tone = "default" }: StatTileProps) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="truncate text-xs">{label}</CardDescription>
        <CardTitle
          className={cn(
            "truncate text-2xl tabular-nums",
            tone === "win" && "text-win"
          )}
        >
          {value}
        </CardTitle>
      </CardHeader>
      {hint ? (
        <CardContent>
          <p className="truncate text-xs text-muted-foreground">{hint}</p>
        </CardContent>
      ) : null}
    </Card>
  )
}
