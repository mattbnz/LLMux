import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApi, type OverallDetailedUsage, type KeyUsageItem, type OAuthUsageResponse } from '@/hooks/use-api'
import { toast } from 'sonner'
import { SimpleBarChart } from '@/components/SimpleBarChart'
import { UsageDetailDialog } from '@/components/UsageDetailDialog'
import { OAuthUsageBadges } from '@/components/OAuthUsageBadges'
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
  const [oauthUsage, setOAuthUsage] = useState<OAuthUsageResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedKey, setSelectedKey] = useState<KeyUsageItem | null>(null)

  const fetchUsage = async () => {
    setLoading(true)

    // Fetch OAuth usage separately as it's not under /api/management
    const fetchOAuthUsage = async () => {
      try {
        const response = await fetch('/api/oauth/usage')
        if (response.ok) {
          return await response.json()
        }
      } catch (err) {
        console.error('Failed to fetch OAuth usage:', err)
      }
      return null
    }

    const [usageResp, oauthUsageData] = await Promise.all([
      get<OverallDetailedUsage>('/usage'),
      fetchOAuthUsage()
    ])
    if (usageResp.data) {
      setUsage(usageResp.data)
    } else if (usageResp.error) {
      toast.error('Failed to fetch usage data')
    }
    if (oauthUsageData) {
      setOAuthUsage(oauthUsageData)
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
          {/* Usage Summary Card */}
          <Card className="border-primary/20">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10">
                  <DollarSign className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <CardTitle>Usage Summary</CardTitle>
                  <CardDescription>Overall API usage and costs</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* OAuth Usage Windows */}
              {oauthUsage && (
                <OAuthUsageBadges
                  fiveHour={oauthUsage.five_hour}
                  sevenDay={oauthUsage.seven_day}
                  sevenDaySonnet={oauthUsage.seven_day_sonnet}
                  extraUsage={oauthUsage.extra_usage}
                />
              )}

              {/* Summary Stats */}
              <div className="grid grid-cols-4 gap-6">
                <div className="flex items-center gap-3">
                  <Cpu className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Total Tokens</p>
                    <p className="font-mono text-sm">{formatTokens(totalTokens)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <DollarSign className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Est. Cost</p>
                    <p className="font-mono text-sm">${usage.summary.estimated_cost_usd.toFixed(2)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <TrendingUp className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Requests</p>
                    <p className="font-mono text-sm">{usage.summary.total_requests.toLocaleString()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-xs text-muted-foreground">Cache Savings</p>
                    <p className="font-mono text-sm">{formatTokens(usage.summary.total_cache_read_tokens)}</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Usage by API Key */}
          <Card className="border-primary/20">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-primary/10">
                  <KeyRound className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <CardTitle>Usage by API Key</CardTitle>
                  <CardDescription>
                    Breakdown of usage per API key including historical data
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {usage.by_key.length > 0 ? (
                <div className="overflow-hidden">
                  <table className="w-full text-xs">
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
                        <tr key={key.key_id} className="hover:bg-muted/30">
                          <td className="p-3">
                            <div className="font-medium text-xs">{key.key_name}</div>
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
                              className="h-7 px-2 text-xs"
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
                <div className="text-center py-8 text-xs text-muted-foreground">
                  No usage data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Usage by Model */}
          {usage.by_model.length > 0 && (
            <Card className="border-primary/20">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Cpu className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle>Usage by Model</CardTitle>
                    <CardDescription>Token usage breakdown by AI model</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-hidden">
                  <table className="w-full text-xs">
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
                        <tr key={m.model} className="hover:bg-muted/30">
                          <td className="p-3">
                            <div className="font-medium text-xs">{m.model_display_name}</div>
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
            <Card className="border-primary/20">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <TrendingUp className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle>Daily Usage</CardTitle>
                    <CardDescription>Token usage over the last 30 days</CardDescription>
                  </div>
                </div>
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
