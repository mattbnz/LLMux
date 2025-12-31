interface BarChartData {
  label: string
  value: number
}

interface SimpleBarChartProps {
  data: BarChartData[]
  maxValue?: number
  formatValue?: (value: number) => string
  className?: string
}

export function SimpleBarChart({
  data,
  maxValue,
  formatValue = (v) => v.toString(),
  className = ''
}: SimpleBarChartProps) {
  if (data.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-4">
        No data available
      </div>
    )
  }

  const max = maxValue || Math.max(...data.map(d => d.value), 1)

  return (
    <div className={`space-y-1.5 ${className}`}>
      {data.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs w-12 text-muted-foreground truncate" title={item.label}>
            {item.label}
          </span>
          <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
            <div
              className="h-full bg-primary/80 transition-all duration-300"
              style={{ width: `${Math.min((item.value / max) * 100, 100)}%` }}
            />
          </div>
          <span className="text-xs w-16 text-right text-muted-foreground">
            {formatValue(item.value)}
          </span>
        </div>
      ))}
    </div>
  )
}
