import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ChartShell } from './ui/index.js'
import {
  axisLabelStyle,
  axisTickStyle,
  barActiveProps,
  categoryAxisWidth,
  chartAnimationDuration,
  getRechartsTheme,
  rechartsMargin,
  tooltipContentStyle,
  tooltipCursorStyle,
  tooltipItemStyle,
  tooltipLabelStyle,
  verticalBarChartHeight,
} from '../utils/rechartsTheme.js'

export function VendorKevChart({ rows }) {
  const theme = getRechartsTheme()
  const anim = chartAnimationDuration()
  const vendors = rows.map((row) => row.vendor || 'Unknown')
  const yAxisWidth = categoryAxisWidth(vendors, { min: 100, max: 220 })
  const chartHeight = verticalBarChartHeight(rows.length, { min: 180 })
  const data = rows.map((row) => ({
    label: row.vendor || 'Unknown',
    vendor: row.vendor,
    kev_count: row.kev_count,
  }))

  return (
    <ChartShell
      height={chartHeight}
      ariaLabel="Top KEV vendors by entry count"
      className="brief-chart-canvas-wrap brief-chart-canvas-wrap--kev"
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={rechartsMargin({ left: 8, right: 12, top: 8, bottom: 8 })}
        >
          <CartesianGrid stroke={theme.grid} horizontal={false} />
          <XAxis
            type="number"
            tick={axisTickStyle(theme)}
            allowDecimals={false}
            label={{
              value: 'KEV count',
              position: 'insideBottom',
              offset: -2,
              style: axisLabelStyle(theme),
            }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={yAxisWidth}
            tick={{ ...axisTickStyle(theme), textAnchor: 'end' }}
            interval={0}
          />
          <Tooltip
            contentStyle={tooltipContentStyle(theme)}
            labelStyle={tooltipLabelStyle(theme)}
            itemStyle={tooltipItemStyle(theme)}
            cursor={tooltipCursorStyle(theme)}
            formatter={(value) => [
              `${value} KEV ${value === 1 ? 'entry' : 'entries'}`,
              'KEV entries',
            ]}
            labelFormatter={(_label, payload) => payload?.[0]?.payload?.vendor || _label}
          />
          <Bar
            dataKey="kev_count"
            radius={0}
            isAnimationActive={anim > 0}
            animationDuration={anim}
            activeBar={barActiveProps(theme)}
          >
            {data.map((entry) => (
              <Cell key={entry.vendor} fill={theme.accent} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}
