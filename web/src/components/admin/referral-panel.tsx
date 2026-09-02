import { LinkIcon, UsersIcon } from "lucide-react"

import type { Referrals } from "@/lib/api"
import { ddmm, hhmm } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { StatGrid, StatTile } from "@/components/admin/stat-tile"

// Khop voi ref_source trong ghibai/tracking.py.
const SOURCE_LABEL: Record<string, string> = {
  link: "Link chia sẻ",
  group: "Cùng nhóm",
  landing: "Trang mời",
}

function sourceLabel(source: string): string {
  return SOURCE_LABEL[source] ?? source
}

export function ReferralPanel({
  refs,
  totalUsers,
}: {
  refs: Referrals
  totalUsers: number
}) {
  return (
    <div className="flex flex-col gap-4">
      <StatGrid>
        <StatTile
          label="Đã biết nguồn"
          value={refs.attributed}
          hint={`trên ${totalUsers} người dùng`}
        />
        <StatTile
          label="Chắc chắn"
          value={refs.exact}
          hint="bấm link chia sẻ"
          tone="win"
        />
        <StatTile label="Suy đoán" value={refs.inferred} hint="cùng nhóm / trang mời" />
        <StatTile
          label="K-factor"
          value={refs.kFactor}
          hint={`${refs.inviters} người từng mời được`}
        />
      </StatGrid>

      {refs.bySource.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {refs.bySource.map((item) => (
            <Badge key={item.source} variant="secondary">
              {sourceLabel(item.source)}: {item.count}
            </Badge>
          ))}
        </div>
      ) : null}

      <Section
        icon={<UsersIcon className="size-4" aria-hidden />}
        title="Mời được nhiều nhất"
        empty="Chưa có ai mời được người mới."
        rows={refs.topReferrers.map((person) => ({
          key: person.code,
          main: person.name ?? "(không tên)",
          sub: `${person.platform} · mã ${person.code}`,
          value: String(person.invited),
        }))}
      />

      <Section
        icon={<LinkIcon className="size-4" aria-hidden />}
        title="Gán nguồn gần đây"
        empty="Chưa ghi nhận lượt nào."
        rows={refs.recent.map((item, index) => ({
          key: `${item.invitee}-${index}`,
          main: `${item.invitee ?? "(không tên)"} ← ${item.inviter ?? "(không tên)"}`,
          sub: [
            sourceLabel(item.source),
            item.at ? `${ddmm(item.at)} ${hhmm(item.at)}` : null,
          ]
            .filter(Boolean)
            .join(" · "),
          badge: item.confidence === "exact" ? "chắc chắn" : "suy đoán",
          exact: item.confidence === "exact",
        }))}
      />
    </div>
  )
}

type Row = {
  key: string
  main: string
  sub: string
  value?: string
  badge?: string
  exact?: boolean
}

function Section({
  icon,
  title,
  rows,
  empty,
}: {
  icon: React.ReactNode
  title: string
  rows: Row[]
  empty: string
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="flex items-center gap-1.5 px-1 text-sm font-medium text-muted-foreground">
        {icon}
        {title}
      </h2>

      {rows.length === 0 ? (
        <p className="px-1 py-4 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <Card className="gap-0 py-0">
          <ul className="divide-y">
            {rows.map((row) => (
              <li
                key={row.key}
                className="flex min-h-14 items-center gap-3 px-4 py-2.5"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{row.main}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {row.sub}
                  </p>
                </div>
                {row.value ? (
                  <span className="shrink-0 text-xl font-semibold tabular-nums">
                    {row.value}
                  </span>
                ) : null}
                {row.badge ? (
                  <Badge
                    variant={row.exact ? "default" : "outline"}
                    className="shrink-0"
                  >
                    {row.badge}
                  </Badge>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  )
}
