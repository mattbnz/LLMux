import { type UsageWindow, type ExtraUsage } from '@/hooks/use-api'
import { Card } from '@/components/ui/card'
import { Clock, Calendar, Zap, DollarSign } from 'lucide-react'

type StatusLevel = 'green' | 'orange' | 'red' | 'gray'

interface UsageStatus {
  level: StatusLevel
  emoji: string
  color: string
  bgColor: string
}

// Calculate time remaining from reset timestamp
function getTimeRemaining(resetAt: string | null | undefined): { formatted: string; percentElapsed: number; totalMs: number; isActive: boolean } {
  // Check if resetAt is absent or empty
  if (!resetAt) {
    return { formatted: 'No session', percentElapsed: 100, totalMs: 0, isActive: false }
  }

  const now = new Date()
  const reset = new Date(resetAt)
  const msRemaining = reset.getTime() - now.getTime()

  // Check if resetAt is in the past
  if (msRemaining <= 0) {
    return { formatted: 'No session', percentElapsed: 100, totalMs: 0, isActive: false }
  }

  const days = Math.floor(msRemaining / (1000 * 60 * 60 * 24))
  const hours = Math.floor((msRemaining % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const minutes = Math.floor((msRemaining % (1000 * 60 * 60)) / (1000 * 60))

  let formatted = ''
  if (days > 0) {
    formatted = `${days}d ${hours}h ${minutes}m`
  } else if (hours > 0) {
    formatted = `${hours}h ${minutes}m`
  } else {
    formatted = `${minutes}m`
  }

  // For percent elapsed, we need to know the window duration
  // We'll estimate based on typical windows (5h, 7d)
  // This will be refined per-window type
  return { formatted, percentElapsed: 0, totalMs: msRemaining, isActive: true }
}

// Calculate status based on utilization vs time progression
function calculateStatus(
  utilization: number,
  resetAt: string | null | undefined,
  windowDurationMs: number
): UsageStatus {
  // Check if session is active
  if (!resetAt) {
    return {
      level: 'gray',
      emoji: '💤',
      color: 'text-muted-foreground',
      bgColor: 'bg-muted'
    }
  }

  const now = new Date()
  const reset = new Date(resetAt)
  const msRemaining = reset.getTime() - now.getTime()

  if (msRemaining <= 0) {
    return {
      level: 'gray',
      emoji: '💤',
      color: 'text-muted-foreground',
      bgColor: 'bg-muted'
    }
  }

  if (utilization >= 100) {
    return {
      level: 'red',
      emoji: '🔴',
      color: 'text-red-600',
      bgColor: 'bg-red-500/10'
    }
  }

  const percentElapsed = ((windowDurationMs - msRemaining) / windowDurationMs) * 100

  // Calculate burn rate: how fast we're using compared to time passing
  // If we're at 50% usage with 50% time elapsed, burn rate = 1.0 (on track)
  // If we're at 80% usage with 40% time elapsed, burn rate = 2.0 (burning too fast)
  const burnRate = percentElapsed > 0 ? utilization / percentElapsed : 0

  // Status thresholds
  if (burnRate <= 1.0) {
    // On track or better
    return {
      level: 'green',
      emoji: '✅',
      color: 'text-green-600',
      bgColor: 'bg-green-500/10'
    }
  } else if (burnRate <= 1.5) {
    // Slightly over pace
    return {
      level: 'orange',
      emoji: '⚠️',
      color: 'text-orange-600',
      bgColor: 'bg-orange-500/10'
    }
  } else {
    // Significantly over pace
    return {
      level: 'red',
      emoji: '❌',
      color: 'text-red-600',
      bgColor: 'bg-red-500/10'
    }
  }
}

// Calculate status for extra usage (budget-based)
function calculateExtraUsageStatus(extraUsage: ExtraUsage): UsageStatus {
  if (!extraUsage.is_enabled) {
    return {
      level: 'gray',
      emoji: '🚫',
      color: 'text-muted-foreground',
      bgColor: 'bg-muted'
    }
  }

  const percentUsed = (extraUsage.used_credits / extraUsage.monthly_limit) * 100

  if (percentUsed < 50) {
    return {
      level: 'green',
      emoji: '✅',
      color: 'text-green-600',
      bgColor: 'bg-green-500/10'
    }
  } else if (percentUsed < 80) {
    return {
      level: 'orange',
      emoji: '⚠️',
      color: 'text-orange-600',
      bgColor: 'bg-orange-500/10'
    }
  } else {
    return {
      level: 'red',
      emoji: '❌',
      color: 'text-red-600',
      bgColor: 'bg-red-500/10'
    }
  }
}

interface UsageBadgeProps {
  label: string
  window: UsageWindow | null
  windowDurationMs: number
  compact?: boolean
}

function UsageBadge({ label, window, windowDurationMs, compact = false }: UsageBadgeProps) {
  if (!window) {
    return null
  }

  const timeRemaining = getTimeRemaining(window.resets_at)
  const status = calculateStatus(window.utilization, window.resets_at, windowDurationMs)

  // Determine icon based on window type
  const getIcon = () => {
    if (label.includes('5h')) return Clock
    if (label.includes('Sonnet')) return Zap
    return Calendar
  }
  const Icon = getIcon()

  if (compact) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
          <Icon className="w-3 h-3" />
          {label}
        </div>
        <div className="flex items-center gap-2">
          {timeRemaining.isActive ? (
            <>
              <div className="text-xl font-bold">{window.utilization.toFixed(0)}%</div>
              <div className="text-xs text-muted-foreground">{timeRemaining.formatted}</div>
            </>
          ) : (
            <div className="text-sm text-muted-foreground">No session active</div>
          )}
          <span className="text-base ml-auto">{status.emoji}</span>
        </div>
      </Card>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="font-mono text-sm">
          {timeRemaining.isActive ? (
            <>
              {window.utilization.toFixed(0)}% · {timeRemaining.formatted} remaining{' '}
            </>
          ) : (
            <>No session active </>
          )}
          <span className="text-base">{status.emoji}</span>
        </p>
      </div>
    </div>
  )
}

interface ExtraUsageBadgeProps {
  extraUsage: ExtraUsage | null
  compact?: boolean
}

function ExtraUsageBadge({ extraUsage, compact = false }: ExtraUsageBadgeProps) {
  if (!extraUsage || !extraUsage.is_enabled) {
    return null
  }

  const status = calculateExtraUsageStatus(extraUsage)
  const percentUsed = (extraUsage.used_credits / extraUsage.monthly_limit) * 100
  const budgetDollars = extraUsage.monthly_limit / 100

  if (compact) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
          <DollarSign className="w-3 h-3" />
          Extra Usage
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xl font-bold">{percentUsed.toFixed(0)}%</div>
          <div className="text-xs text-muted-foreground">of ${budgetDollars}</div>
          <span className="text-base ml-auto">{status.emoji}</span>
        </div>
      </Card>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <div>
        <p className="text-xs text-muted-foreground">Extra Usage</p>
        <p className="font-mono text-sm">
          {percentUsed.toFixed(0)}% of ${budgetDollars}{' '}
          <span className="text-base">{status.emoji}</span>
        </p>
      </div>
    </div>
  )
}

interface OAuthUsageBadgesProps {
  fiveHour: UsageWindow | null
  sevenDay: UsageWindow | null
  sevenDaySonnet: UsageWindow | null
  extraUsage: ExtraUsage | null
  compact?: boolean
}

export function OAuthUsageBadges({
  fiveHour,
  sevenDay,
  sevenDaySonnet,
  extraUsage,
  compact = false
}: OAuthUsageBadgesProps) {
  // Window durations in milliseconds
  const FIVE_HOUR_MS = 5 * 60 * 60 * 1000
  const SEVEN_DAY_MS = 7 * 24 * 60 * 60 * 1000

  if (compact) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {fiveHour && (
          <UsageBadge
            label="5h Window"
            window={fiveHour}
            windowDurationMs={FIVE_HOUR_MS}
            compact
          />
        )}
        {sevenDay && (
          <UsageBadge
            label="7d Window"
            window={sevenDay}
            windowDurationMs={SEVEN_DAY_MS}
            compact
          />
        )}
        {sevenDaySonnet && (
          <UsageBadge
            label="7d Sonnet"
            window={sevenDaySonnet}
            windowDurationMs={SEVEN_DAY_MS}
            compact
          />
        )}
        {extraUsage && <ExtraUsageBadge extraUsage={extraUsage} compact />}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 gap-6">
      <UsageBadge
        label="5h Window"
        window={fiveHour}
        windowDurationMs={FIVE_HOUR_MS}
      />
      <UsageBadge
        label="7d Window"
        window={sevenDay}
        windowDurationMs={SEVEN_DAY_MS}
      />
      <UsageBadge
        label="7d Sonnet"
        window={sevenDaySonnet}
        windowDurationMs={SEVEN_DAY_MS}
      />
      <ExtraUsageBadge extraUsage={extraUsage} />
    </div>
  )
}
