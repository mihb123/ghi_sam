import * as React from "react"
import { KeyRoundIcon, RefreshCwIcon, WifiOffIcon } from "lucide-react"

import { ApiError, type Stats } from "@/lib/api"
import { readAdminToken } from "@/lib/admin-token"
import { ddmm, hhmm } from "@/lib/format"
import { cn } from "@/lib/utils"
import { useStats } from "@/hooks/use-stats"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { BarChart } from "@/components/admin/bar-chart"
import { ReferralPanel } from "@/components/admin/referral-panel"
import { StatGrid, StatTile } from "@/components/admin/stat-tile"

type AdminTab = "tongquan" | "gioithieu" | "nhom"

export function AdminApp() {
  const [token] = React.useState(readAdminToken)
  const [tab, setTab] = React.useState<AdminTab>("tongquan")
  const { stats, error, loading, reload } = useStats(token)

  return (
    <div className="flex min-h-[100dvh] flex-col bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/95 pt-[env(safe-area-inset-top)] backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex max-w-2xl items-center gap-1.5 px-4 py-2">
          <div className="min-w-0 flex-1">
            <h1 className="truncate font-heading font-medium">Thống kê bot</h1>
            <p className="truncate text-xs text-muted-foreground">
              {stats
                ? `Số liệu lúc ${hhmm(stats.generatedAt)}`
                : "Đang tải số liệu…"}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon-lg"
            className="size-11"
            aria-label="Tải lại"
            onClick={reload}
          >
            <RefreshCwIcon className={cn(loading && "animate-spin")} />
          </Button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
        <Body
          token={token}
          stats={stats}
          error={error}
          loading={loading}
          tab={tab}
          onTabChange={setTab}
        />
      </main>
    </div>
  )
}

function Body({
  token,
  stats,
  error,
  loading,
  tab,
  onTabChange,
}: {
  token: string | null
  stats: Stats | null
  error: Error | null
  loading: boolean
  tab: AdminTab
  onTabChange: (tab: AdminTab) => void
}) {
  if (!token || (error instanceof ApiError && error.status === 404)) {
    return <NoAccessState />
  }
  if (!stats) {
    return loading ? <StatsSkeleton /> : <OfflineState error={error} />
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? <StaleAlert /> : null}

      <Tabs
        value={tab}
        onValueChange={(value) => onTabChange(value as AdminTab)}
      >
        <TabsList className="h-11 w-full">
          <TabsTrigger value="tongquan">Tổng quan</TabsTrigger>
          <TabsTrigger value="gioithieu">Giới thiệu</TabsTrigger>
          <TabsTrigger value="nhom">Nhóm</TabsTrigger>
        </TabsList>

        <TabsContent value="tongquan" className="pt-1">
          <Overview stats={stats} />
        </TabsContent>

        <TabsContent value="gioithieu" className="pt-1">
          <ReferralPanel
            refs={stats.referrals}
            totalUsers={stats.totals.users}
          />
        </TabsContent>

        <TabsContent value="nhom" className="pt-1">
          <ChatsPanel stats={stats} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function Overview({ stats }: { stats: Stats }) {
  const { users, totals, daily, hourly } = stats
  const axis: [string, string] = [
    ddmm(daily[0]?.day ?? ""),
    ddmm(daily[daily.length - 1]?.day ?? ""),
  ]
  const peakHour = hourly.reduce(
    (best, point) => (point.events > best.events ? point : best),
    hourly[0] ?? { hour: 0, events: 0 }
  )

  return (
    <div className="flex flex-col gap-4">
      <StatGrid>
        <StatTile
          label="Người dùng"
          value={totals.users}
          hint={`+${users.new7d} trong 7 ngày`}
        />
        <StatTile label="Mới hôm nay" value={users.newToday} tone="win" />
        <StatTile label="Dùng hôm nay" value={users.dau} hint="DAU" />
        <StatTile label="Dùng 30 ngày" value={users.mau} hint="MAU" />
      </StatGrid>

      <BarChart
        title="Lượt dùng mỗi ngày (30 ngày)"
        total={`${totals.events} lượt`}
        bars={daily.map((point) => ({
          key: point.day,
          value: point.events,
          caption: `${ddmm(point.day)}: ${point.events} lượt · ${point.activeUsers} người`,
        }))}
        axis={axis}
      />

      <BarChart
        title="Người dùng mới mỗi ngày"
        total={`${users.new30d} người / 30 ngày`}
        bars={daily.map((point) => ({
          key: point.day,
          value: point.newUsers,
          caption: `${ddmm(point.day)}: ${point.newUsers} người mới`,
        }))}
        axis={axis}
        tone="win"
      />

      <BarChart
        title="Giờ hay dùng nhất"
        total={`Cao điểm ${String(peakHour.hour).padStart(2, "0")}:00`}
        bars={hourly.map((point) => ({
          key: String(point.hour),
          value: point.events,
          caption: `${String(point.hour).padStart(2, "0")}:00 — ${point.events} lượt`,
        }))}
        axis={["00:00", "23:00"]}
      />

      <StatGrid>
        {stats.byPlatform.map((platform) => (
          <StatTile
            key={platform.platform}
            label={platform.platform}
            value={platform.users}
            hint={`${platform.chats} chat · ${platform.dau} đang dùng`}
          />
        ))}
      </StatGrid>

      {stats.topCommands.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h2 className="px-1 text-sm font-medium text-muted-foreground">
            Lệnh hay dùng
          </h2>
          <Card className="gap-0 py-0">
            <ul className="divide-y">
              {stats.topCommands.map((item) => (
                <li
                  key={item.command}
                  className="flex min-h-12 items-center justify-between gap-3 px-4 py-2"
                >
                  <code className="truncate font-mono text-sm">
                    /{item.command}
                  </code>
                  <span className="shrink-0 font-semibold tabular-nums">
                    {item.count}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      ) : null}
    </div>
  )
}

function ChatsPanel({ stats }: { stats: Stats }) {
  return (
    <div className="flex flex-col gap-4">
      <StatGrid>
        <StatTile label="Nhóm / chat" value={stats.totals.chats} />
        <StatTile label="Bàn đã mở" value={stats.totals.sessions} />
        <StatTile label="Ván đã ghi" value={stats.totals.rounds} />
        <StatTile label="Người dùng" value={stats.totals.users} />
      </StatGrid>

      {stats.topChats.length === 0 ? (
        <p className="px-1 py-4 text-sm text-muted-foreground">
          Chưa có nhóm nào ghi ván.
        </p>
      ) : (
        <Card className="gap-0 py-0">
          <ul className="divide-y">
            {stats.topChats.map((chat, index) => (
              <li
                key={`${chat.platform}-${chat.title}-${index}`}
                className="flex min-h-14 items-center gap-3 px-4 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    {chat.title ?? "(chat riêng)"}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {chat.platform} · {chat.members} người
                    {chat.lastActiveAt
                      ? ` · dùng lần cuối ${ddmm(chat.lastActiveAt)}`
                      : ""}
                  </p>
                </div>
                <span className="shrink-0 text-right text-sm tabular-nums">
                  <span className="text-xl font-semibold">{chat.rounds}</span>
                  <span className="block text-xs text-muted-foreground">ván</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

function NoAccessState() {
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <KeyRoundIcon />
        </EmptyMedia>
        <EmptyTitle>Cần link quản trị</EmptyTitle>
        <EmptyDescription>
          Trang này chỉ mở được bằng link có token:{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-foreground">
            /admin?k=…
          </code>{" "}
          — token là{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-foreground">
            ADMIN_STATS_TOKEN
          </code>{" "}
          trong .env.
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  )
}

function OfflineState({ error }: { error: Error | null }) {
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <WifiOffIcon />
        </EmptyMedia>
        <EmptyTitle>Chưa tải được số liệu</EmptyTitle>
        <EmptyDescription>
          {error?.message ?? "Không gọi được máy chủ."}
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  )
}

function StaleAlert() {
  return (
    <Alert variant="destructive">
      <WifiOffIcon />
      <AlertTitle>Chưa tải được số mới</AlertTitle>
      <AlertDescription>
        Số đang xem là lần tải gần nhất.
      </AlertDescription>
    </Alert>
  )
}

function StatsSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((tile) => (
          <Skeleton key={tile} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-11 rounded-lg" />
      <Skeleton className="h-44 rounded-xl" />
      <Skeleton className="h-44 rounded-xl" />
    </div>
  )
}
