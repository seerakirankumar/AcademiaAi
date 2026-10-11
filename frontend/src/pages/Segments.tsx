import { get } from '../lib/api'
import { num, pct, shortDept } from '../lib/format'
import { useLoad } from '../lib/hooks'
import type { SegmentSummary } from '../lib/types'
import { Async, PageHeading, Panel } from '../components/Primitives'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { axisTick, chartColors, ChartTooltip } from '../components/chartTheme'

const COLORS: Record<string, string> = { 'High readiness': '#1c7a4f', Developing: '#2a52d9', 'Needs support': '#d99a2b', 'Priority support': '#b42f2a' }

export default function Segments() {
  const seg = useLoad<SegmentSummary[]>(() => get<SegmentSummary[]>('/api/segments'), 'segments')
  const rows = seg.data ?? []
  const depts = Array.from(new Set(rows.flatMap(r => Object.keys(r.by_department)))).sort()
  const chart = depts.map(d => ({ department: shortDept(d), ...Object.fromEntries(rows.map(r => [r.segment, r.by_department[d] ?? 0])) }))
  return (
    <>
      <PageHeading title="Student segments" description="Group students by shared patterns so support can be more targeted and timely." />
      <Async loading={seg.loading} error={seg.error} onRetry={seg.reload}>
        <div className="module-grid">
          {rows.map(r => (
            <article className="module-card" key={r.segment}>
              <div><h2>{r.segment}</h2><p>{r.description}</p></div>
              <div className="module-card-foot">
                <strong>{num(r.students)} <small>students · {num(r.percentage, 1)}%</small></strong>
                <small style={{ color: 'var(--muted)' }}>Avg score {num(r.average_success_score, 1)} · attendance {pct(r.average_attendance_pct)} · placement readiness {num(r.average_placement_readiness, 1)}</small>
              </div>
            </article>
          ))}
        </div>
        <Panel title="Segments by department" subtitle="Number of students in each segment">
          <div className="chart-box" role="img" aria-label="Stacked bar chart of segments by department">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ top: 10, right: 12, left: -8, bottom: 0 }}>
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis dataKey="department" tickLine={false} axisLine={false} tick={axisTick} dy={8} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={axisTick} width={40} />
                <Tooltip content={<ChartTooltip unit=" students" />} cursor={{ fill: '#f3f2ee' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                {rows.map(r => <Bar key={r.segment} dataKey={r.segment} stackId="a" fill={COLORS[r.segment] ?? '#8e8e87'} maxBarSize={44} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </Async>
    </>
  )
}
