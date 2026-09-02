import * as React from "react"

import { ApiError, type Board } from "@/lib/api"
import { hhmm } from "@/lib/format"
import {
  formatRefreshInterval,
  readStoredRefreshInterval,
  readStoredTab,
  writeStoredRefreshInterval,
  writeStoredTab,
  type ActiveTab,
} from "@/lib/settings"
import { readToken } from "@/lib/token"
import { useBoard } from "@/hooks/use-board"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { BoardHeader } from "@/components/board-header"
import {
  BadLinkState,
  BoardSkeleton,
  ChecksumAlert,
  NoSessionState,
  NoTokenState,
  StaleAlert,
} from "@/components/board-states"
import { BoardStats } from "@/components/board-stats"
import { RoundsView } from "@/components/rounds-view"
import { SettingsDialog } from "@/components/settings-dialog"
import { StandingsList } from "@/components/standings-list"

export function App() {
  // Token khong doi trong mot lan mo app nen chi doc URL/localStorage mot lan.
  const [token] = React.useState(readToken)

  // Tab active duoc luu lai trong localStorage / URL de reload van o tab cu.
  const [activeTab, setActiveTab] = React.useState<ActiveTab>(readStoredTab)

  // Thoi gian tu lam moi duoc luu lai trong localStorage.
  const [refreshInterval, setRefreshInterval] = React.useState<number>(
    readStoredRefreshInterval
  )
  const [settingsOpen, setSettingsOpen] = React.useState(false)

  const handleTabChange = React.useCallback((tab: ActiveTab) => {
    setActiveTab(tab)
    writeStoredTab(tab)
  }, [])

  const handleRefreshIntervalChange = React.useCallback((intervalSec: number) => {
    setRefreshInterval(intervalSec)
    writeStoredRefreshInterval(intervalSec)
  }, [])

  const { board, error, loading, reload } = useBoard(token, refreshInterval)

  return (
    // dvh chu khong phai vh: thanh dia chi cua trinh duyet mobile lam vh sai chieu cao.
    <div className="flex min-h-[100dvh] flex-col bg-background">
      <BoardHeader
        board={board}
        loading={loading}
        onReload={reload}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
        <Body
          token={token}
          board={board}
          error={error}
          loading={loading}
          activeTab={activeTab}
          onTabChange={handleTabChange}
        />
      </main>

      {board ? (
        <footer className="mx-auto w-full max-w-2xl px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-center text-xs text-muted-foreground">
          Cập nhật lúc {hhmm(board.fetchedAt)} ·{" "}
          {refreshInterval > 0
            ? `tự làm mới ${formatRefreshInterval(refreshInterval)}`
            : formatRefreshInterval(refreshInterval)}
        </footer>
      ) : null}

      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        refreshInterval={refreshInterval}
        onRefreshIntervalChange={handleRefreshIntervalChange}
      />
    </div>
  )
}

type BodyProps = {
  token: string | null
  board: Board | null
  error: Error | null
  loading: boolean
  activeTab: ActiveTab
  onTabChange: (tab: ActiveTab) => void
}

function Body({
  token,
  board,
  error,
  loading,
  activeTab,
  onTabChange,
}: BodyProps) {
  if (!token) {
    return <NoTokenState />
  }
  // Token sai thi khong co gi de xem, khac han loi mang (con so cu de hien).
  if (error instanceof ApiError && error.status === 404) {
    return <BadLinkState message={error.message} />
  }
  if (!board) {
    return loading ? <BoardSkeleton /> : <BadLinkState message={message(error)} />
  }
  if (!board.session) {
    return <NoSessionState />
  }

  return (
    <div className="flex flex-col gap-4">
      {error ? <StaleAlert message={message(error)} /> : null}
      {board.checksum !== 0 ? (
        <ChecksumAlert checksum={board.checksum} />
      ) : null}

      <BoardStats board={board} />

      <Tabs
        value={activeTab}
        onValueChange={(val) => {
          if (val === "bang" || val === "van") {
            onTabChange(val)
          }
        }}
      >
        <TabsList className="h-11 w-full">
          <TabsTrigger value="bang">Bảng xếp hạng</TabsTrigger>
          <TabsTrigger value="van">Chi tiết ván</TabsTrigger>
        </TabsList>

        <TabsContent value="bang" className="pt-1">
          {board.standings.length > 0 ? (
            <StandingsList standings={board.standings} />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Bàn đã mở nhưng chưa ghi ván nào.
            </p>
          )}
        </TabsContent>

        <TabsContent value="van" className="pt-1">
          {board.rounds.length > 0 ? (
            <RoundsView
              rounds={board.rounds}
              players={board.players}
              voidedSeqs={board.voidedSeqs}
            />
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Chưa có ván nào được ghi.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function message(error: Error | null): string {
  return error?.message ?? "Không gọi được máy chủ."
}

export default App

