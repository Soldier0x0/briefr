import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartShell } from '../../../components/ui/index.js'
import { fmtBytes, fmtDur } from '../formatters.js'
import {
  axisLabelStyle,
  axisTickStyle,
  barActiveProps,
  chartAnimationDuration,
  getRechartsTheme,
  legendStyle,
  rechartsMargin,
  tooltipContentStyle,
  tooltipCursorStyle,
  tooltipItemStyle,
  tooltipLabelStyle,
} from '../../../utils/rechartsTheme.js'

function ingestScaleMax(secondsList) {
  if (!secondsList.length) return undefined
  const sorted = [...secondsList].sort((a, b) => a - b)
  const p75 = sorted[Math.floor(sorted.length * 0.75)] || sorted[sorted.length - 1]
  const cap = Math.max(p75 * 1.25, sorted[0])
  return cap > 0 ? cap : undefined
}

function backupSparklineLabel(row) {
  const name = (row?.filename || '').replace(/^briefr-backup-/, '').replace(/\.tar\.gz$/, '')
  if (!name) return 'backup'
  return name.length > 12 ? `${name.slice(0, 12)}…` : name
}

export function IngestDurationChart({ rows }) {
  const theme = getRechartsTheme()
  const durations = rows.map((r) => r.seconds)
  const scaleMax = ingestScaleMax(durations)
  const data = rows.map((row) => ({
    label: row.label,
    seconds: row.seconds,
    hadError: row.hadError,
  }))
  const anim = chartAnimationDuration()

  return (
    <ChartShell height={200} ariaLabel="Ingest job duration chart" className="admin-ops-chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={rechartsMargin({ left: 8, right: 12 })}
        >
          <CartesianGrid stroke={theme.grid} horizontal={false} />
          <XAxis
            type="number"
            domain={[0, scaleMax || 'auto']}
            tick={axisTickStyle(theme)}
            tickFormatter={(v) => fmtDur(Number(v))}
            label={{
              value: 'Duration',
              position: 'insideBottom',
              offset: -2,
              style: axisLabelStyle(theme),
            }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={110}
            tick={axisTickStyle(theme)}
            interval={0}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(theme)}
            labelStyle={tooltipLabelStyle(theme)}
            itemStyle={tooltipItemStyle(theme)}
            cursor={tooltipCursorStyle(theme)}
            formatter={(value, _name, item) => {
              const err = item?.payload?.hadError ? ' (last run errored)' : ''
              return [`${fmtDur(Number(value))}${err}`, 'Last run duration']
            }}
          />
          <Bar
            dataKey="seconds"
            radius={0}
            isAnimationActive={anim > 0}
            animationDuration={anim}
            activeBar={barActiveProps(theme)}
          >
            {data.map((entry, index) => (
              <Cell
                key={entry.label || index}
                fill={entry.hadError ? theme.redDim : theme.accent}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function BackupSizesChart({ rows }) {
  const theme = getRechartsTheme()
  const data = rows.map((row) => ({
    label: backupSparklineLabel(row),
    size: row.size_bytes || 0,
    filename: row.filename,
    created_at: row.created_at,
  }))
  const anim = chartAnimationDuration()

  return (
    <ChartShell height={200} ariaLabel="Backup archive sizes chart" className="admin-ops-chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={rechartsMargin({ left: 8, right: 12, bottom: 16 })}>
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            dataKey="label"
            tick={axisTickStyle(theme)}
            interval={0}
            label={{
              value: 'Newest →',
              position: 'insideBottom',
              offset: -2,
              style: axisLabelStyle(theme),
            }}
          />
          <YAxis
            tick={axisTickStyle(theme)}
            tickFormatter={(v) => fmtBytes(Number(v))}
            label={{
              value: 'Size',
              angle: -90,
              position: 'insideLeft',
              style: axisLabelStyle(theme),
            }}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(theme)}
            labelStyle={tooltipLabelStyle(theme)}
            itemStyle={tooltipItemStyle(theme)}
            cursor={tooltipCursorStyle(theme)}
            formatter={(value) => [fmtBytes(Number(value)), 'Archive size']}
            labelFormatter={(_label, payload) => payload?.[0]?.payload?.filename || _label}
          />
          <Line
            type="monotone"
            dataKey="size"
            stroke={theme.green}
            fill={theme.greenDim}
            strokeWidth={2}
            dot={{ r: 3, fill: theme.green }}
            activeDot={{ r: 4, fill: theme.green, stroke: theme.text, strokeWidth: 1 }}
            isAnimationActive={anim > 0}
            animationDuration={anim}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function WebhookDeliveriesChart({ buckets }) {
  const theme = getRechartsTheme()
  const data = buckets.map((b) => ({
    day: b.day.slice(5),
    ok: b.ok,
    failed: b.failed,
    fullDay: b.day,
  }))
  const anim = chartAnimationDuration()

  return (
    <ChartShell height={200} ariaLabel="Webhook deliveries chart" className="admin-ops-chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={rechartsMargin({ left: 8, right: 12, bottom: 24 })}>
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            dataKey="day"
            tick={axisTickStyle(theme)}
            label={{
              value: 'Day (UTC)',
              position: 'insideBottom',
              offset: -2,
              style: axisLabelStyle(theme),
            }}
          />
          <YAxis
            tick={axisTickStyle(theme)}
            allowDecimals={false}
            label={{
              value: 'Deliveries',
              angle: -90,
              position: 'insideLeft',
              style: axisLabelStyle(theme),
            }}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(theme)}
            labelStyle={tooltipLabelStyle(theme)}
            itemStyle={tooltipItemStyle(theme)}
            cursor={tooltipCursorStyle(theme)}
            labelFormatter={(_label, payload) => payload?.[0]?.payload?.fullDay || _label}
          />
          <Legend
            verticalAlign="bottom"
            wrapperStyle={legendStyle(theme)}
            iconType="square"
            iconSize={10}
          />
          <Bar
            dataKey="ok"
            name="Delivered"
            stackId="wh"
            fill={theme.greenDim}
            radius={0}
            isAnimationActive={anim > 0}
            animationDuration={anim}
            activeBar={barActiveProps(theme)}
          />
          <Bar
            dataKey="failed"
            name="Failed"
            stackId="wh"
            fill={theme.redDim}
            radius={0}
            isAnimationActive={anim > 0}
            animationDuration={anim}
            activeBar={barActiveProps(theme)}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}
