import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useApi, type DetailedUsage } from '@/hooks/use-api'
import { SimpleBarChart } from './SimpleBarChart'
import { RefreshCw, TrendingUp, Clock, Cpu, DollarSign } from 'lucide-react'

interface UsageDetailDialogProps {
  keyId: string | null
  keyName: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function formatTokens(tokens: number): string {
  if (tokens < 1000) return tokens.toString()
  if (tokens < 1_000_000) return `${(tokens / 1000).toFixed(1)}K`
  return `${(tokens / 1_000_000).toFixed(2)}M`
}

function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  if (cost < 1) return `$${cost.toFixed(2)}`
  return `$${cost.toFixed(2)}`
}

export function UsageDetailDialog({
  keyId,
  keyName,
  open,
  onOpenChange
}: UsageDetailDialogProps) {
  const { get } = useApi()
  const [usage, setUsage] = useState<DetailedUsage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!keyId || !open) {
      return
    }

    async function fetchUsage() {
      setLoading(true)
      setError(null)
      const { data, error: fetchError } = await get<DetailedUsage>(`/keys/${keyId}/usage`)
      if (data) {
        setUsage(data)
      } else {
        setError(fetchError || 'Failed to load usage data')
      }
      setLoading(false)
    }
    fetchUsage()
  }, [keyId, open, get])

  const totalTokens = usage
    ? usage.summary.total_input_tokens + usage.summary.total_output_tokens
    : 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Usage Details: {keyName}
          </DialogTitle>
          <DialogDescription>
            Token usage and cost breakdown for this API key
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-destructive">
            {error}
          </div>
        ) : usage ? (
          <div className="space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg border bg-card">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                  <Cpu className="w-3.5 h-3.5" />
                  Total Tokens
                </div>
                <div className="text-lg font-semibold">{formatTokens(totalTokens)}</div>
              </div>
              <div className="p-3 rounded-lg border bg-card">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                  <DollarSign className="w-3.5 h-3.5" />
                  Estimated Cost
                </div>
                <div className="text-lg font-semibold">{formatCost(usage.summary.estimated_cost_usd)}</div>
              </div>
              <div className="p-3 rounded-lg border bg-card">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                  <TrendingUp className="w-3.5 h-3.5" />
                  Requests
                </div>
                <div className="text-lg font-semibold">{usage.summary.total_requests.toLocaleString()}</div>
              </div>
              <div className="p-3 rounded-lg border bg-card">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                  <Clock className="w-3.5 h-3.5" />
                  Cache Savings
                </div>
                <div className="text-lg font-semibold">
                  {formatTokens(usage.summary.total_cache_read_tokens)}
                </div>
              </div>
            </div>

            {/* Token Breakdown */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Token Breakdown</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="flex justify-between p-2 rounded bg-muted/50">
                  <span className="text-muted-foreground">Input Tokens</span>
                  <span className="font-medium">{formatTokens(usage.summary.total_input_tokens)}</span>
                </div>
                <div className="flex justify-between p-2 rounded bg-muted/50">
                  <span className="text-muted-foreground">Output Tokens</span>
                  <span className="font-medium">{formatTokens(usage.summary.total_output_tokens)}</span>
                </div>
                <div className="flex justify-between p-2 rounded bg-muted/50">
                  <span className="text-muted-foreground">Cache Read</span>
                  <span className="font-medium">{formatTokens(usage.summary.total_cache_read_tokens)}</span>
                </div>
                <div className="flex justify-between p-2 rounded bg-muted/50">
                  <span className="text-muted-foreground">Cache Write</span>
                  <span className="font-medium">{formatTokens(usage.summary.total_cache_creation_tokens)}</span>
                </div>
              </div>
            </div>

            {/* By Model */}
            {usage.by_model.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Usage by Model</h4>
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-2 font-medium">Model</th>
                        <th className="text-right p-2 font-medium">Requests</th>
                        <th className="text-right p-2 font-medium">Tokens</th>
                        <th className="text-right p-2 font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usage.by_model.map((m) => (
                        <tr key={m.model} className="border-t">
                          <td className="p-2">
                            <div>{m.model_display_name}</div>
                            <div className="text-xs text-muted-foreground font-mono">{m.model}</div>
                          </td>
                          <td className="p-2 text-right">{m.request_count.toLocaleString()}</td>
                          <td className="p-2 text-right">{formatTokens(m.input_tokens + m.output_tokens)}</td>
                          <td className="p-2 text-right">{formatCost(m.estimated_cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Daily Usage Chart */}
            {usage.daily.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Daily Usage (Last 30 Days)</h4>
                <SimpleBarChart
                  data={usage.daily.slice(-14).map(d => ({
                    label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    value: d.input_tokens + d.output_tokens
                  }))}
                  formatValue={formatTokens}
                />
              </div>
            )}

            {/* Hourly Usage */}
            {usage.hourly.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Hourly Usage (Last 24 Hours)</h4>
                <SimpleBarChart
                  data={usage.hourly.map(h => ({
                    label: `${h.hour.toString().padStart(2, '0')}:00`,
                    value: h.input_tokens + h.output_tokens
                  }))}
                  formatValue={formatTokens}
                />
              </div>
            )}

            {/* First/Last Usage */}
            {(usage.summary.first_usage || usage.summary.last_usage) && (
              <div className="text-xs text-muted-foreground pt-2 border-t">
                {usage.summary.first_usage && (
                  <div>First usage: {new Date(usage.summary.first_usage).toLocaleString()}</div>
                )}
                {usage.summary.last_usage && (
                  <div>Last usage: {new Date(usage.summary.last_usage).toLocaleString()}</div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No usage data available
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
