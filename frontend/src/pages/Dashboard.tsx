import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ArrowRight, ArrowUpRight, BookOpen, CalendarDays, Download, GraduationCap, Info, Users } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { get, getAll } from '../lib/api'
import { STAFF, useAuth } from '../lib/auth'
import { downloadCsv, num, pct, shortDept } from '../lib/format'
import { useLoad } from '../lib/hooks'
import type { DashboardSummary, DepartmentMetric, RiskItem, StudentListItem } from '../lib/types'
import { Async, Avatar, EmptyState, MetricCard, Notice, PageHeading, Panel, RiskPill, ScoreCell } from '../components/Primitives'
import StudentDrawer from '../components/StudentDrawer'
import { axisTick, chartColors, ChartTooltip } from '../components/chartTheme'

const SEGMENT_COLORS: Record<string, string> = {
  'High readiness': '#1c7a4f', Developing: '#2a52d9', 'Needs support': '#d99a2b', 'Priority support': '#b42f2a',
}

export default function Dashboard() {
  const { can } = useAuth()
  const staff = can(...STAFF)
  const [selected, setSelected] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [hoveredSegmentName, setHoveredSegmentName] = useState<string | null>(null)
  const summary = useLoad<DashboardSummary>(() => get<DashboardSummary>('/api/dashboard/summary'), 'summary')
  const depts = useLoad<DepartmentMetric[]>(() => get<DepartmentMetric[]>('/api/analytics/departments'), 'depts')
  const attention = useLoad<RiskItem[]>(() => (staff ? get<RiskItem[]>('/api/risks', { limit: 6 }) : Promise.resolve({ data: [] as RiskItem[] })), `attention-${staff}`)

  const s = summary.data
  const segmentData = s ? Object.entries(s.segments).map(([name, value]) => ({ name, value, color: SEGMENT_COLORS[name] ?? '#8e8e87' })) : []
  const hoveredSegment = segmentData.find(segment => segment.name === hoveredSegmentName)
  const hoveredSegmentPct = hoveredSegment && s?.total_students
    ? Math.round(hoveredSegment.value / s.total_students * 100)
    : 0
  const deptData = (depts.data ?? []).map(d => ({
    department: shortDept(d.department), score: d.average_success_score, attendance: d.average_attendance_pct,
    placement: d.average_placement_readiness, students: d.students,
  }))

  const exportOverview = async () => {
    try {
      const rows = await getAll<StudentListItem>('/api/students')
      downloadCsv('academia-student-overview.csv', [
        ['Student ID', 'Name', 'Department', 'Year', 'Success score', 'Academic risk', 'Placement risk', 'Segment'],
        ...rows.map(r => [r.student_id, r.student_name, r.department, r.year_of_study, r.success_score ?? 'Incomplete', r.academic_risk_level, r.placement_risk_level, r.segment]),
      ])
      setNotice(`Exported ${rows.length} students as CSV.`)
    } catch (e) { setNotice(e instanceof Error ? e.message : 'Export failed.') }
  }

  return (
    <>
      <PageHeading
        title="Student success, at a glance"
        description="A clear view of how students are doing — and where your team can make a difference."
        actions={<>
          <span className="chip"><CalendarDays size={16} />{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
          {staff && <button className="button button-primary" onClick={exportOverview}><Download size={16} />Export overview</button>}
        </>}
      />
      {notice && <Notice tone="success" onDismiss={() => setNotice(null)}>{notice}</Notice>}
      <Async loading={summary.loading} error={summary.error} onRetry={summary.reload}>
        {s && (<>
          <div className="metric-grid">
            <MetricCard label="Students monitored" value={num(s.total_students)} sub={`${depts.data?.length ?? '—'} departments`} icon={<Users size={18} />} />
            <MetricCard label="Average success score" value={num(s.average_success_score, 1)} sub="Out of 100 points" icon={<Activity size={18} />} />
            <MetricCard label="Needing academic support" value={num(s.students_flagged_academic_support)} sub={`${num(s.high_risk_academic)} at high risk`} icon={<BookOpen size={18} />} />
            <MetricCard label="Needing placement preparation" value={num(s.students_flagged_placement_support)} sub={`${num(s.high_risk_placement)} at high risk`} icon={<GraduationCap size={18} />} />
            <MetricCard label="Average attendance" value={pct(s.average_attendance_pct)} sub="Across recorded classes" icon={<CalendarDays size={18} />} />
          </div>

          <div className="dashboard-grid">
            <Panel flush title="Department performance" subtitle="Average score, attendance and placement readiness (out of 100)">
              <div className="panel-body">
                <Async loading={depts.loading} error={depts.error} onRetry={depts.reload}>
                  <div className="chart-box" role="img" aria-label="Grouped bar chart of success score, attendance and placement readiness by department">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={deptData} margin={{ top: 10, right: 12, left: -8, bottom: 0 }}>
                        <CartesianGrid stroke={chartColors.grid} vertical={false} />
                        <XAxis dataKey="department" tickLine={false} axisLine={false} tick={axisTick} dy={8} />
                        <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={axisTick} width={40} />
                        <Tooltip content={<ChartTooltip />} cursor={{ fill: '#f3f2ee' }} />
                        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                        <Bar dataKey="score" name="Success score" fill={chartColors.academic} radius={[4, 4, 0, 0]} maxBarSize={22} />
                        <Bar dataKey="attendance" name="Attendance" fill={chartColors.attendance} radius={[4, 4, 0, 0]} maxBarSize={22} />
                        <Bar dataKey="placement" name="Placement readiness" fill={chartColors.placement} radius={[4, 4, 0, 0]} maxBarSize={22} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Async>
              </div>
            </Panel>

            <Panel flush title="Where support is needed" subtitle="Students by support segment">
              <div className="risk-summary">
                <div className="risk-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={segmentData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={72} paddingAngle={3} stroke="none" startAngle={90} endAngle={-270}>
                        {segmentData.map(e => (
                          <Cell
                            key={e.name}
                            fill={e.color}
                            onMouseEnter={() => setHoveredSegmentName(e.name)}
                            onMouseLeave={() => setHoveredSegmentName(null)}
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="donut-center" aria-live="polite">
                    {hoveredSegment ? <>
                      <strong>{num(hoveredSegment.value)}</strong>
                      <span className="donut-segment-name">{hoveredSegment.name}</span>
                      <span className="donut-segment-share">{hoveredSegmentPct}% of students</span>
                    </> : <>
                      <strong>{num(s.total_students)}</strong>
                      <span>students</span>
                    </>}
                  </div>
                </div>
                <div className="risk-legend">
                  {segmentData.map(r => (
                    <div key={r.name}>
                      <span><i style={{ background: r.color }} />{r.name}</span>
                      <strong>{r.value} <small>({s.total_students ? Math.round(r.value / s.total_students * 100) : 0}%)</small></strong>
                    </div>
                  ))}
                </div>
              </div>
              {staff && (
                <div className="risk-breakdown">
                  <Link to="/academic-risk" style={{ display: 'contents' }}><button>
                    <span className="risk-symbol"><BookOpen size={17} /></span>
                    <span className="copy"><strong>Academic risk</strong><small>{num(s.high_risk_academic)} high · {num(s.students_flagged_academic_support)} flagged</small></span>
                    <ArrowUpRight size={16} /></button></Link>
                  <Link to="/placement-risk" style={{ display: 'contents' }}><button>
                    <span className="risk-symbol"><GraduationCap size={17} /></span>
                    <span className="copy"><strong>Placement risk</strong><small>{num(s.high_risk_placement)} high · {num(s.students_flagged_placement_support)} flagged</small></span>
                    <ArrowUpRight size={16} /></button></Link>
                </div>
              )}
            </Panel>
          </div>

          {staff && (
            <Panel flush title="Students to check in with" subtitle="Students with the highest combined academic and placement risk points"
              action={<Link className="text-button" to="/students">View all students <ArrowRight size={15} /></Link>}>
              <Async loading={attention.loading} error={attention.error} onRetry={attention.reload}>
                <div className="table-wrap" style={{ marginTop: 16 }}>
                  <table className="data-table">
                    <thead><tr><th>Student</th><th>Department</th><th>Success score</th><th>Academic risk</th><th>Placement risk</th><th><span className="sr-only">Actions</span></th></tr></thead>
                    <tbody>
                      {(attention.data ?? []).map(r => (
                        <tr key={r.student_id} className="clickable-row" onClick={() => setSelected(r.student_id)}>
                          <td><div className="student-cell"><Avatar name={r.student_name} id={r.student_id} />
                            <button className="cell-link" onClick={e => { e.stopPropagation(); setSelected(r.student_id) }}><strong>{r.student_name}</strong><small>{r.student_id}</small></button></div></td>
                          <td>{r.department}</td>
                          <td><ScoreCell score={r.success_score === null ? null : Math.round(r.success_score)} /></td>
                          <td><RiskPill risk={r.academic_risk.level} /></td>
                          <td><RiskPill risk={r.placement_risk.level} /></td>
                          <td><span className="row-arrow" aria-hidden="true"><ArrowUpRight size={16} /></span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(attention.data ?? []).length === 0 && <EmptyState title="No students flagged" body="No students currently have risk points." />}
                </div>
              </Async>
            </Panel>
          )}

          <Panel title="Segment size by department" subtitle="Share of each department's students that are in a Needs support or Priority support segment">
            <div className="chart-box short" role="img" aria-label="Bar chart of students needing support by department">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={(depts.data ?? []).map(d => ({
                  department: shortDept(d.department),
                  share: d.students ? Math.round(((d.segments['Needs support'] ?? 0) + (d.segments['Priority support'] ?? 0)) / d.students * 100) : 0,
                }))} layout="vertical" margin={{ top: 4, right: 36, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tickLine={false} axisLine={false} tick={axisTick} unit="%" />
                  <YAxis type="category" dataKey="department" width={90} tickLine={false} axisLine={false} tick={{ ...axisTick, fill: '#44443f' }} />
                  <Tooltip content={<ChartTooltip unit="%" />} cursor={{ fill: '#f3f2ee' }} />
                  <Bar dataKey="share" name="Needing support" fill={chartColors.attention} radius={[0, 6, 6, 0]} barSize={22}>
                    <LabelList dataKey="share" position="right" formatter={(v: number) => `${v}%`} style={{ fontSize: 12, fontWeight: 600, fill: '#161616' }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <p className="method-note"><Info size={15} /><span>{s.disclaimer ?? 'Scores and risk levels are rule-based indicators, not probabilities.'} {s.students_with_incomplete_data > 0 && `${s.students_with_incomplete_data} students have incomplete records; missing values are never treated as zero.`}</span></p>
        </>)}
      </Async>
      {selected && <StudentDrawer studentId={selected} onClose={() => setSelected(null)} onChanged={() => { summary.reload(); attention.reload() }} />}
    </>
  )
}
