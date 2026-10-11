/** Shared Recharts styling so every chart in the product reads as one system. */
export const chartColors = {
  academic: 'var(--series-1)',
  placement: 'var(--series-2)',
  attendance: 'var(--series-3)',
  grid: '#ecebe6',
  axis: '#6b6b65',
  lowRisk: '#1c7a4f',
  attention: '#d99a2b',
}
export const axisTick = { fontSize: 12, fill: chartColors.axis }

type TooltipRow = { name?: string | number; value?: string | number; color?: string; payload?: { color?: string } }
export function ChartTooltip({ active, payload, label, unit = '/100' }: {
  active?: boolean; payload?: TooltipRow[]; label?: string | number; unit?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      {label !== undefined && <strong>{label}</strong>}
      {payload.map(row => (
        <div key={String(row.name)}>
          <span><i className="legend-dot" style={{ background: row.color ?? row.payload?.color }} />{row.name}</span>
          <b>{row.value}{unit}</b>
        </div>
      ))}
    </div>
  )
}
