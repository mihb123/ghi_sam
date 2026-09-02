import { LinkIcon, SpadeIcon, TriangleAlertIcon, WifiOffIcon } from "lucide-react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function NoTokenState() {
  return (
    <StateBlock icon={<LinkIcon />} title="Chưa có link bàn chơi">
      Trang này mở bằng link riêng của từng nhóm. Vào nhóm chat và gõ{" "}
      <Cmd>/web</Cmd> (Telegram) hoặc <Cmd>#web</Cmd> (Zalo), bot sẽ gửi link.
    </StateBlock>
  )
}

export function BadLinkState({ message }: { message: string }) {
  return (
    <StateBlock icon={<LinkIcon />} title="Link không dùng được">
      {message}
    </StateBlock>
  )
}

export function NoSessionState() {
  return (
    <StateBlock icon={<SpadeIcon />} title="Nhóm này chưa chơi ván nào">
      Ghi ván đầu tiên trong nhóm chat rồi quay lại đây — bàn mới sẽ tự hiện.
    </StateBlock>
  )
}

export function StaleAlert({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <WifiOffIcon />
      <AlertTitle>Chưa tải được số mới</AlertTitle>
      <AlertDescription>
        {message} Số đang xem là lần tải gần nhất.
      </AlertDescription>
    </Alert>
  )
}

export function ChecksumAlert({ checksum }: { checksum: number }) {
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon />
      <AlertTitle>Tổng điểm không bằng 0 ({checksum})</AlertTitle>
      <AlertDescription>
        Mỗi ván phải cộng lại bằng 0, nên có ván nhập sai. Sửa trong nhóm chat
        bằng <Cmd>/sua</Cmd>.
      </AlertDescription>
    </Alert>
  )
}

export function BoardSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-hidden>
      <div className="grid grid-cols-2 gap-3">
        <Skeleton className="h-24 rounded-xl" />
        <Skeleton className="h-24 rounded-xl" />
      </div>
      <Skeleton className="h-11 rounded-lg" />
      <Card className="gap-0 py-0">
        <ul className="divide-y">
          {[0, 1, 2, 3].map((row) => (
            <li key={row} className="flex min-h-14 items-center gap-3 px-4">
              <Skeleton className="size-8 rounded-full" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-6 w-12" />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

function StateBlock({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <Empty className="border">
      <EmptyHeader>
        <EmptyMedia variant="icon">{icon}</EmptyMedia>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{children}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  )
}

function Cmd({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded bg-muted px-1 py-0.5 font-mono text-foreground">
      {children}
    </code>
  )
}
