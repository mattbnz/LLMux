import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApi, type OverallDetailedUsage, type KeyUsageItem } from '@/hooks/use-api'
import { toast } from 'sonner'
import { SimpleBarChart } from '@/components/SimpleBarChart'
import { UsageDetailDialog } from '@/components/UsageDetailDialog'
import {
  RefreshCw, TrendingUp, DollarSign, Cpu, Clock,
  KeyRound, Archive, CheckCircle, ExternalLink
} from 'lucide-react'

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

export default function Usage() {
  const { get } = useApi()
  const [usage, setUsage] = useState<OverallDetailedUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedKey, setSelectedKey] = useState<KeyUsageItem | null>(null)

  const fetchUsage = async () => {
    setLoading(true)
    const { data, error } = await get<OverallDetailedUsage>('/usage')
    if (data) {
      setUsage(data)
    } else if (error) {
      toast.error('Failed to fetch usage data')
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchUsage()
  }, [])

  const totalTokens = usage
    ? usage.summary.total_input_tokens + usage.summary.total_output_tokens
    : 0

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Usage Analytics</h2>
          <p className="text-muted-foreground mt-1">Monitor API usage across all keys</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchUsage} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {loading && !usage ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : usage ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <Cpu className="w-4 h-4" />
                  Total Tokens
                </div>
                <div className="text-2xl font-bold">{formatTokens(totalTokens)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <DollarSign className="w-4 h-4" />
                  Estimated Cost
                </div>
                <div className="text-2xl font-bold">{formatCost(usage.summary.estimated_cost_usd)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <TrendingUp className="w-4 h-4" />
                  Total Requests
                </div>
                <div className="text-2xl font-bold">{usage.summary.total_requests.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <Clock className="w-4 h-4" />
                  Cache Savings
                </div>
                <div className="text-2xl font-bold">{formatTokens(usage.summary.total_cache_read_tokens)}</div>
              </CardContent>
            </Card>
          </div>

          {/* Usage by API Key */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="w-5 h-5" />
                Usage by API Key
              </CardTitle>
              <CardDescription>
                Breakdown of usage per API key including historical data
              </CardDescription>
            </CardHeader>
            <CardContent>
              {usage.by_key.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-3 font-medium">Key Name</th>
                        <th className="text-left p-3 font-medium">Status</th>
                        <th className="text-right p-3 font-medium">Requests</th>
                        <th className="text-right p-3 font-medium">Tokens</th>
                        <th className="text-right p-3 font-medium">Cost</th>
                        <th className="text-right p-3 font-medium"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {usage.by_key.map((key) => (
                        <tr key={key.key_id} className="border-t hover:bg-muted/30">
                          <td className="p-3">
                            <div className="font-medium">{key.key_name}</div>
                            <div className="text-xs text-muted-foreground font-mono">
                              {key.key_prefix}...
                            </div>
                          </td>
                          <td className="p-3">
                            <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${
                              key.is_deleted
                                ? 'bg-muted text-muted-foreground'
                                : 'bg-green-500/10 text-green-600'
                            }`}>
                              {key.is_deleted ? (
                                <>
                                  <Archive className="w-3 h-3" />
                                  Deleted
                                </>
                              ) : (
                                <>
                                  <CheckCircle className="w-3 h-3" />
                                  Active
                                </>
                              )}
                            </div>
                          </td>
                          <td className="p-3 text-right font-mono">
                            {key.request_count.toLocaleString()}
                          </td>
                          <td className="p-3 text-right font-mono">
                            {formatTokens(key.input_tokens + key.output_tokens)}
                          </td>
                          <td className="p-3 text-right font-mono">
                            {formatCost(key.estimated_cost_usd)}
                          </td>
                          <td className="p-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2"
                              onClick={() => setSelectedKey(key)}
                            >
                              <ExternalLink className="w-3.5 h-3.5 mr-1" />
                              Details
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No usage data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Usage by Model */}
          {usage.by_model.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Usage by Model</CardTitle>
                <CardDescription>Token usage breakdown by AI model</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-3 font-medium">Model</th>
                        <th className="text-right p-3 font-medium">Requests</th>
                        <th className="text-right p-3 font-medium">Input</th>
                        <th className="text-right p-3 font-medium">Output</th>
                        <th className="text-right p-3 font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usage.by_model.map((m) => (
                        <tr key={m.model} className="border-t hover:bg-muted/30">
                          <td className="p-3">
                            <div className="font-medium">{m.model_display_name}</div>
                            <div className="text-xs text-muted-foreground font-mono">{m.model}</div>
                          </td>
                          <td className="p-3 text-right font-mono">{m.request_count.toLocaleString()}</td>
                          <td className="p-3 text-right font-mono">{formatTokens(m.input_tokens)}</td>
                          <td className="p-3 text-right font-mono">{formatTokens(m.output_tokens)}</td>
                          <td className="p-3 text-right font-mono">{formatCost(m.estimated_cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Daily Usage Chart */}
          {usage.daily.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Daily Usage</CardTitle>
                <CardDescription>Token usage over the last 30 days</CardDescription>
              </CardHeader>
              <CardContent>
                <SimpleBarChart
                  data={usage.daily.slice(-14).map(d => ({
                    label: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    value: d.input_tokens + d.output_tokens
                  }))}
                  formatValue={formatTokens}
                />
              </CardContent>
            </Card>
          )}
        </>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          No usage data available
        </div>
      )}

      {/* Usage Detail Dialog */}
      <UsageDetailDialog
        keyId={selectedKey?.key_id ?? null}
        keyName={selectedKey?.key_name ?? null}
        open={!!selectedKey}
        onOpenChange={(open) => !open && setSelectedKey(null)}
      />
    </div>
  )
}
