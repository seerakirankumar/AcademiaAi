import { BookOpen, CalendarDays, GraduationCap, Users } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { get } from '../lib/api'
import { num, pct, shortDept } from '../lib/format'
import { useLoad } from '../lib/hooks'
import type { DashboardSummary, DepartmentMetric } from '../lib/types'
import { Async, MetricCard, PageHeading, Panel } from '../components/Primitives'
import { axisTick, chartColors, ChartTooltip } from '../components/chartTheme'

export default function Academics() {
  const summary = useLoad<DashboardSummary>(() => get<DashboardSummary>('/api/dashboard/summary'), 'summary')
  const depts = useLoad<DepartmentMetric[]>(() => get<DepartmentMetric[]>('/api/analytics/departments'), 'depts')
  const s = summary.data
  const rows = depts.data ?? []
  return (
    <>
      <PageHeading title="Academic analytics" description="Understand academic outcomes, attendance and learning engagement across departments." />
      <Async loading={summary.loading || depts.loading} error={summary.error ?? depts.error} onRetry={() => { summary.reload(); depts.reload() }}>
        {s && (
          <div className="metric-grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
            <MetricCard label="Students monitored" value={num(s.total_students)} sub="Current records" icon={<Users size={18} />} />
            <MetricCard label="Average attendance" value={pct(s.average_attendance_pct)} sub="Across recorded classes" icon={<CalendarDays size={18} />} />
            <MetricCard label="Needing academic support" value={num(s.students_flagged_academic_support)} sub="Medium or high academic risk" icon={<BookOpen size={18} />} />
            <MetricCard label="Strong placement readiness" value={num(s.students_strong_placement_readiness)} sub="Readiness score of 70+" icon={<GraduationCap size={18} />} />
          </div>
        )}
        <Panel title="Attendance and learning activity by department" subtitle="Average values, out of 100">
          <div className="chart-box" role="img" aria-label="Bar chart of attendance and LMS score by department">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows.map(d => ({ department: shortDept(d.department), attendance: d.average_attendance_pct, lms: d.average_lms_score, score: d.average_success_score }))} margin={{ top: 10, right: 12, left: -8, bottom: 0 }}>
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis dataKey="department" tickLine={false} axisLine={false} tick={axisTick} dy={8} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={axisTick} width={40} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: '#f3f2ee' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="score" name="Success score" fill={chartColors.academic} radius={[4, 4, 0, 0]} maxBarSize={22} />
                <Bar dataKey="attendance" name="Attendance" fill={chartColors.attendance} radius={[4, 4, 0, 0]} maxBarSize={22} />
                <Bar dataKey="lms" name="Learning activity" fill={chartColors.placement} radius={[4, 4, 0, 0]} maxBarSize={22} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <div style={{ marginTop: 16 }}>
          <Panel flush title="Department comparison" subtitle="Flagged counts use rule-based Medium/High risk levels">
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>Department</th><th>Students</th><th>Avg score</th><th>Avg CGPA</th><th>Attendance</th><th>Academic flags</th><th>Placement flags</th><th>Priority support</th></tr></thead>
                <tbody>
                  {rows.map(d => (
                    <tr key={d.department}>
                      <td><strong>{d.department}</strong></td><td className="num">{d.students}</td><td className="num">{num(d.average_success_score, 1)}</td>
                      <td className="num">{num(d.average_cgpa, 2)}</td><td className="num">{pct(d.average_attendance_pct)}</td>
                      <td className="num">{d.flagged_academic_support}</td><td className="num">{d.flagged_placement_support}</td><td className="num">{d.priority_support}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </Async>
    </>
  )
}
