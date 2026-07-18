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
import { bytesChartScale, durationChartScale } from '../formatters.js'
import {
  axisLabelStyle,
  axisTickStyle,
  barActiveProps,
  chartAnimationDuration,
  getRechartsTheme,
  categoryAxisWidth,
  legendStyle,
  rechartsMargin,
  tooltipContentStyle,
  tooltipCursorStyle,
  tooltipItemStyle,
  tooltipLabelStyle,
  verticalBarChartHeight,
} from '../../../utils/rechartsTheme.js'
import { backupChartPoints, backupTooltipModel } from './backupChartUtils.js'

function ingestScaleMax(displayValues) {
  if (!displayValues.length) return undefined
  const sorted = [...displayValues].sort((a, b) => a - b)
  const p75 = sorted[Math.floor(sorted.length * 0.75)] || sorted[sorted.length - 1]
  const cap = Math.max(p75 * 1.25, sorted[0])
  return cap > 0 ? cap : undefined
}

export function IngestDurationChart({ rows }) {
  const theme = getRechartsTheme()
  const scale = durationChartScale(rows.map((r) => r.seconds))
  const data = rows.map((row, index) => ({
    pointKey: index,
    label: row.label,
    duration: scale.toDisplay(row.seconds),
    hadError: row.hadError,
  }))
  const labels = data.map((r) => r.label)
  const scaleMax = ingestScaleMax(data.map((r) => r.duration)) || scale.domainMax
  const yAxisWidth = categoryAxisWidth(labels)
  const chartHeight = verticalBarChartHeight(rows.length)
  const anim = chartAnimationDuration()

  return (
    <ChartShell height={chartHeight} ariaLabel="Ingest job duration chart" className="admin-ops-chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={rechartsMargin({ left: 8, right: 12, top: 8, bottom: 8 })}
        >
          <CartesianGrid stroke={theme.grid} horizontal={false} />
          <XAxis
            type="number"
            domain={[0, scaleMax || 'auto']}
            tick={axisTickStyle(theme)}
            tickFormatter={(v) => scale.format(Number(v))}
            label={{
              value: `Duration (${scale.unit})`,
              position: 'insideBottom',
              offset: -2,
              style: axisLabelStyle(theme),
            }}
          />
          <YAxis
            type="category"
            dataKey="pointKey"
            allowDuplicatedCategory={false}
            width={yAxisWidth}
            tick={{ ...axisTickStyle(theme), textAnchor: 'end' }}
            tickFormatter={(value) => data[Number(value)]?.label || String(value)}
            interval={0}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(theme)}
            labelStyle={tooltipLabelStyle(theme)}
            itemStyle={tooltipItemStyle(theme)}
            cursor={tooltipCursorStyle(theme)}
            labelFormatter={(_label, payload) => payload?.[0]?.payload?.label || _label}
            formatter={(value, _name, item) => {
              const err = item?.payload?.hadError ? ' (last run errored)' : ''
              return [`${scale.format(Number(value))}${err}`, 'Last run duration']
            }}
          />
          <Bar
            dataKey="duration"
            radius={0}
            isAnimationActive={anim > 0}
            animationDuration={anim}
            activeBar={barActiveProps(theme)}
          >
            {data.map((entry) => (
              <Cell
                key={entry.pointKey}
                fill={entry.hadError ? theme.redDim : theme.accent}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

function BackupSizeTooltip({ active, payload, scale, theme }) {
  if (!active) return null
  const model = backupTooltipModel(payload)
  if (!model) return null
  return (
    <div style={tooltipContentStyle(theme)}>
      <div style={tooltipLabelStyle(theme)}>{model.filename}</div>
      <div style={tooltipItemStyle(theme)}>
        {`Archive size : ${scale.format(model.size)}`}
      </div>
    </div>
  )
}

export function BackupSizesChart({ rows }) {
  const theme = getRechartsTheme()
  const safeRows = Array.isArray(rows) ? rows : []
  const scale = bytesChartScale(safeRows.map((row) => row?.size_bytes || 0))
  const data = backupChartPoints(safeRows, scale)
  const anim = chartAnimationDuration()

  return (
    <ChartShell height={200} ariaLabel="Backup archive sizes chart" className="admin-ops-chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={rechartsMargin({ left: 16, right: 12, top: 8, bottom: 28 })}>
          <CartesianGrid stroke={theme.grid} vertical={false} />
          <XAxis
            type="category"
            dataKey="pointKey"
            allowDuplicatedCategory={false}
            tick={axisTickStyle(theme)}
            interval="preserveStartEnd"
            minTickGap={20}
            angle={-35}
            textAnchor="end"
            height={48}
            tickFormatter={(value) => data[Number(value)]?.tickLabel || String(value)}
            label={{
              value: 'Newest →',
              position: 'insideBottom',
              offset: -4,
              style: axisLabelStyle(theme),
            }}
          />
          <YAxis
            width={72}
            domain={[0, scale.domainMax]}
            tick={axisTickStyle(theme)}
            tickFormatter={(v) => scale.format(Number(v))}
            label={{
              value: `Size (${scale.unit})`,
              angle: -90,
              position: 'insideLeft',
              offset: 8,
              style: axisLabelStyle(theme),
            }}
          />
          <Tooltip
            cursor={tooltipCursorStyle(theme)}
            content={({ active, payload }) => (
              <BackupSizeTooltip active={active} payload={payload} scale={scale} theme={theme} />
            )}
          />
          <Line
            type="monotone"
            dataKey="size"
            name="Archive size"
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
  const data = buckets.map((b, index) => ({
    pointKey: index,
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
            type="category"
            dataKey="pointKey"
            allowDuplicatedCategory={false}
            tick={axisTickStyle(theme)}
            tickFormatter={(value) => data[Number(value)]?.day || String(value)}
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
