import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartShell } from '../../components/ui/index.js'
import {
  axisTickStyle,
  chartAnimationDuration,
  getRechartsTheme,
  rechartsMargin,
  tooltipContentStyle,
  tooltipCursorStyle,
  tooltipItemStyle,
  tooltipLabelStyle,
} from '../../utils/rechartsTheme.js'
import { fmtBytes } from './formatters.js'

function fmtMetric(field, value) {
  if (value == null || Number.isNaN(value)) return '—'
  if (field.endsWith('_bytes')) return fmtBytes(value)
  if (field.endsWith('_pct')) return `${Number(value).toFixed(1)}%`
  if (field === 'req_count') return String(Math.round(value))
  if (field.includes('iops') || field.includes('_per_min') || field.includes('_bps')) {
    return Number(value).toFixed(1)
  }
  return Number(value).toFixed(2)
}

export function ResourceLineChart({ series, fields, labels, tableTitle }) {
  const theme = getRechartsTheme()
  const anim = chartAnimationDuration()

  const plottable = (series || []).filter((row) =>
    fields.some((field) => {
      const v = row[field]
      return v != null && !Number.isNaN(Number(v))
    }),
  )

  if (!plottable.length) {
    return (
      <div className="admin-empty admin-ops-chart-empty" role="status">
        No samples in this window yet
      </div>
    )
  }

  const data = plottable.map((row) => {
    const entry = {
      tsLabel: row.ts?.slice(11, 16) || '',
      tsFull: row.ts ? String(row.ts).slice(0, 19) : '—',
    }
    fields.forEach((field) => {
      entry[field] = row[field] != null ? Number(row[field]) : null
    })
    return entry
  })

  const lineColors = [theme.accent, theme.chart2, theme.textSecondary]

  return (
    <ChartShell
      height={200}
      ariaLabel={tableTitle || 'Resource utilization chart'}
      className="admin-resources-chart-wrap"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={rechartsMargin({ left: 8, right: 12 })}>
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            dataKey="tsLabel"
            tick={axisTickStyle(theme)}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis tick={axisTickStyle(theme)} domain={['auto', 'auto']} />
          <Tooltip
            contentStyle={tooltipContentStyle(theme)}
            labelStyle={tooltipLabelStyle(theme)}
            itemStyle={tooltipItemStyle(theme)}
            cursor={tooltipCursorStyle(theme)}
            labelFormatter={(_label, payload) => payload?.[0]?.payload?.tsFull || _label}
            formatter={(value, name) => {
              const idx = labels.indexOf(name)
              const field = fields[idx >= 0 ? idx : 0]
              return [fmtMetric(field, value), name]
            }}
          />
          {fields.map((field, idx) => (
            <Line
              key={field}
              type="monotone"
              dataKey={field}
              name={labels[idx] || field}
              stroke={lineColors[idx] || theme.textSecondary}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 4, fill: lineColors[idx] || theme.textSecondary, stroke: theme.text, strokeWidth: 1 }}
              connectNulls
              isAnimationActive={anim > 0}
              animationDuration={anim}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}
