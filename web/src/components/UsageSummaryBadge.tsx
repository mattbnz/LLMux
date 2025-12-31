import { useEffect, useState } from 'react'
import { useApi, type UsageSummary } from '@/hooks/use-api'
import { RefreshCw } from 'lucide-react'

interface UsageSummaryBadgeProps {
  keyId: string
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return tokens.toString()
  if (tokens < 1_000_000) return `${(tokens / 1000).toFixed(1)}K`
  return `${(tokens / 1_000_000).toFixed(1)}M`
}

function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  if (cost < 1) return `$${cost.toFixed(2)}`
  return `$${cost.toFixed(2)}`
}

export function UsageSummaryBadge({ keyId }: UsageSummaryBadgeProps) {
  const { get } = useApi()
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    async function fetchUsage() {
      setLoading(true)
      setError(false)
      const { data, error: fetchError } = await get<UsageSummary>(`/keys/${keyId}/usage/summary`)
      if (data) {
        setUsage(data)
      } else if (fetchError) {
        setError(true)
      }
      setLoading(false)
    }
    fetchUsage()
  }, [keyId, get])

  if (loading) {
    return (
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <RefreshCw className="w-3 h-3 animate-spin" />
      </div>
    )
  }

  if (error || !usage) {
    return null
  }

  const totalTokens = usage.total_input_tokens + usage.total_output_tokens

  if (totalTokens === 0) {
    return (
      <span className="text-xs text-muted-foreground">
        No usage yet
      </span>
    )
  }

  return (
    <span className="text-xs text-muted-foreground">
      {formatTokens(totalTokens)} tokens | {formatCost(usage.estimated_cost_usd)}
    </span>
  )
}
