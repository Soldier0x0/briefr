import { prefersReducedMotion } from './motion.js'

export function chartAnimationOptions({ duration = 160 } = {}) {
  if (prefersReducedMotion()) return false
  return { duration, easing: 'easeOutQuad' }
}

export function baseChartOptions(theme, { animationDuration = 160, maxRotation = 45 } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartAnimationOptions({ duration: animationDuration }),
    layout: { padding: { left: 4, right: 8, top: 4, bottom: 4 } },
    plugins: {
      legend: {
        labels: {
          color: theme.textSecondary,
          font: { family: theme.mono, size: 12 },
          boxWidth: 10,
        },
      },
      tooltip: {
        backgroundColor: theme.panel,
        titleColor: theme.text,
        bodyColor: theme.textSecondary,
        borderColor: theme.grid,
        borderWidth: 1,
        titleFont: { family: theme.mono, size: 13 },
        bodyFont: { family: theme.mono, size: 13 },
      },
    },
    scales: {
      x: {
        ticks: {
          color: theme.textMuted,
          font: { family: theme.mono, size: 12 },
          maxRotation,
          minRotation: 0,
        },
        grid: { color: theme.grid },
        border: { color: theme.grid },
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: theme.textMuted,
          font: { family: theme.mono, size: 12 },
        },
        grid: { color: theme.grid },
        border: { color: theme.grid },
      },
    },
  }
}

export function axisTitle(theme, text) {
  return {
    display: Boolean(text),
    text: text || '',
    color: theme.textMuted,
    font: { family: theme.mono, size: 12 },
    padding: { top: 4, bottom: 0 },
  }
}
