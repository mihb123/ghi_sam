import { cn } from "@/lib/utils"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export type Bar = {
  /** Khoa React va nhan khi hover tren may tinh. */
  key: string
  caption: string
  value: number
}

type BarChartProps = {
  title: string
  total: string
  bars: Bar[]
  /** Nhan hai dau truc ngang; giua truc de trong vi 30 nhan khong vua man hinh. */
  axis?: [string, string]
  tone?: "primary" | "win"
}

/**
 * Bieu do cot bang div thuan - khong keo thu vien chart nao vao ban build PWA cho 3 hang
 * cot. Cao co dinh h-24, moi cot flex-1 nen 24 hay 30 cot deu vua ngang man hinh 360px.
 */
export function BarChart({
  title,
  total,
  bars,
  axis,
  tone = "primary",
}: BarChartProps) {
  const peak = Math.max(...bars.map((b) => b.value), 0)

  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="text-xs">{title}</CardDescription>
        <CardTitle className="text-xl tabular-nums">{total}</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className="flex h-24 items-end gap-px"
          role="img"
          aria-label={`${title}. Cao nhất ${peak}.`}
        >
          {bars.map((bar) => (
            <div
              key={bar.key}
              title={bar.caption}
              style={{ height: peak > 0 ? `${(bar.value / peak) * 100}%` : "2px" }}
              className={cn(
                "min-h-[2px] flex-1 rounded-t-sm",
                bar.value === 0
                  ? "bg-border"
                  : tone === "win"
                    ? "bg-win"
                    : "bg-primary/75"
              )}
            />
          ))}
        </div>

        {axis ? (
          <div className="mt-1.5 flex justify-between text-[11px] tabular-nums text-muted-foreground">
            <span>{axis[0]}</span>
            <span>{axis[1]}</span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
