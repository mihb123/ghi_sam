import * as React from "react"
import { createPortal } from "react-dom"
import {
  CheckIcon,
  LaptopIcon,
  MoonIcon,
  SettingsIcon,
  SunIcon,
  TimerIcon,
  XIcon,
} from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import {
  REFRESH_OPTIONS,
  type RefreshOption,
} from "@/lib/settings"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

type SettingsDialogProps = {
  open: boolean
  onClose: () => void
  refreshInterval: number
  onRefreshIntervalChange: (intervalSec: number) => void
}

export function SettingsDialog({
  open,
  onClose,
  refreshInterval,
  onRefreshIntervalChange,
}: SettingsDialogProps) {
  const { theme, setTheme } = useTheme()

  // Khóa cuộn màn hình khi mở dialog/sheet
  React.useEffect(() => {
    if (!open) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose()
      }
    }
    window.addEventListener("keydown", handleKeyDown)

    return () => {
      document.body.style.overflow = originalOverflow
      window.removeEventListener("keydown", handleKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-dialog-title"
      className="fixed inset-0 z-50 flex flex-col justify-end sm:items-center sm:justify-center"
    >
      {/* Nền mờ scrim */}
      <div
        onClick={onClose}
        aria-hidden="true"
        className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity animate-in fade-in"
      />

      {/* Container Dialog / Bottom Sheet */}
      <div className="relative z-10 flex max-h-[85dvh] w-full flex-col rounded-t-2xl border-t bg-background shadow-2xl transition-all animate-in fade-in sm:max-h-[90dvh] sm:max-w-md sm:rounded-2xl sm:border">
        {/* Thanh kéo handle bar trên mobile */}
        <div className="flex w-full justify-center pt-3 pb-1 sm:hidden">
          <div className="h-1 w-10 rounded-full bg-muted-foreground/30" />
        </div>

        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b px-5 py-3.5">
          <div className="flex items-center gap-2">
            <SettingsIcon className="size-5 text-muted-foreground" />
            <h2 id="settings-dialog-title" className="font-heading font-medium text-base">
              Cài đặt
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            className="size-8 rounded-full"
            aria-label="Đóng cài đặt"
            onClick={onClose}
          >
            <XIcon className="size-4" />
          </Button>
        </div>

        {/* Content cuộn bên trong */}
        <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-4 space-y-6">
          {/* Section: Thời gian làm mới */}
          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <TimerIcon className="size-4 text-muted-foreground" />
              <h3 className="text-sm font-medium text-foreground">
                Thời gian tự làm mới
              </h3>
            </div>
            <p className="text-xs text-muted-foreground">
              Chu kỳ tự động tải dữ liệu mới từ máy chủ.
            </p>

            <div className="grid grid-cols-2 gap-2">
              {REFRESH_OPTIONS.map((opt: RefreshOption) => {
                const isSelected = refreshInterval === opt.value
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => onRefreshIntervalChange(opt.value)}
                    className={cn(
                      "flex min-h-[52px] flex-col justify-center rounded-xl border p-2.5 text-left transition-all touch-manipulation active:scale-[0.98]",
                      isSelected
                        ? "border-primary bg-primary/5 text-foreground ring-1 ring-primary"
                        : "border-border bg-card text-foreground hover:bg-muted/50"
                    )}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-sm font-medium leading-tight">
                        {opt.label}
                      </span>
                      {isSelected ? (
                        <CheckIcon className="size-4 shrink-0 text-primary" />
                      ) : null}
                    </div>
                    {opt.description ? (
                      <span className="mt-0.5 text-[11px] text-muted-foreground">
                        {opt.description}
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          </section>

          {/* Section: Giao diện */}
          <section className="space-y-3 border-t pt-4">
            <div className="flex items-center gap-2">
              <SunIcon className="size-4 text-muted-foreground" />
              <h3 className="text-sm font-medium text-foreground">Giao diện</h3>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <ThemeButton
                active={theme === "light"}
                icon={<SunIcon className="size-4" />}
                label="Sáng"
                onClick={() => setTheme("light")}
              />
              <ThemeButton
                active={theme === "dark"}
                icon={<MoonIcon className="size-4" />}
                label="Tối"
                onClick={() => setTheme("dark")}
              />
              <ThemeButton
                active={theme === "system"}
                icon={<LaptopIcon className="size-4" />}
                label="Hệ thống"
                onClick={() => setTheme("system")}
              />
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t p-4 pb-[calc(1rem+env(safe-area-inset-bottom))]">
          <Button
            type="button"
            className="w-full min-h-[44px] touch-manipulation font-medium"
            onClick={onClose}
          >
            Xong
          </Button>
        </div>
      </div>
    </div>,
    document.body
  )
}

type ThemeButtonProps = {
  active: boolean
  icon: React.ReactNode
  label: string
  onClick: () => void
}

function ThemeButton({ active, icon, label, onClick }: ThemeButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex min-h-[48px] flex-col items-center justify-center gap-1.5 rounded-xl border p-2 text-xs font-medium transition-all touch-manipulation active:scale-[0.98]",
        active
          ? "border-primary bg-primary/5 text-foreground ring-1 ring-primary"
          : "border-border bg-card text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
