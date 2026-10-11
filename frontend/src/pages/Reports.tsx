import { useState } from 'react'
import { Download } from 'lucide-react'
import { getAll } from '../lib/api'
import { downloadCsv } from '../lib/format'
import type { RiskItem, StudentListItem } from '../lib/types'
import { Notice, PageHeading } from '../components/Primitives'

type Job = 'overview' | 'academic' | 'placement'

export default function Reports() {
  const [busy, setBusy] = useState<Job | null>(null)
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)

  const run = async (job: Job) => {
    setBusy(job); setNotice(null)
    try {
      if (job === 'overview') {
        const rows = await getAll<StudentListItem>('/api/students')
        downloadCsv('student-success-overview.csv', [
          ['Student ID', 'Name', 'Department', 'Year', 'Section', 'CGPA', 'Attendance %', 'Success score', 'Academic risk', 'Placement risk', 'Segment', 'Placement status'],
          ...rows.map(s => [s.student_id, s.student_name, s.department, s.year_of_study, s.section, s.cgpa, s.overall_attendance_pct, s.success_score, s.academic_risk_level, s.placement_risk_level, s.segment, s.placement_status]),
        ])
        setNotice({ tone: 'success', text: `Exported ${rows.length} students.` })
      } else {
        const key = job === 'academic' ? 'academic_level' : 'placement_level'
        const rows = [...await getAll<RiskItem>('/api/risks', { [key]: 'High' }), ...await getAll<RiskItem>('/api/risks', { [key]: 'Medium' })]
        downloadCsv(`${job}-support-list.csv`, [
          ['Student ID', 'Name', 'Department', 'Year', 'Level', 'Risk points', 'Reasons', 'Suggested actions'],
          ...rows.map(r => { const k = job === 'academic' ? r.academic_risk : r.placement_risk
            return [r.student_id, r.student_name, r.department, r.year_of_study, k.level, `${k.points}/${k.max_points}`, k.reasons.join('; '), k.suggested_actions.join('; ')] }),
        ])
        setNotice({ tone: 'success', text: `Exported ${rows.length} students with medium or high ${job} risk.` })
      }
    } catch (e) { setNotice({ tone: 'error', text: e instanceof Error ? e.message : 'Export failed.' }) }
    finally { setBusy(null) }
  }

  const cards: { job: Job; title: string; body: string }[] = [
    { job: 'overview', title: 'Student success overview', body: 'Every student with success score, both risk levels and segment.' },
    { job: 'academic', title: 'Academic support list', body: 'Students with medium or high academic risk, with reasons and suggested actions.' },
    { job: 'placement', title: 'Placement preparation list', body: 'Students with medium or high placement risk, with reasons and suggested actions.' },
  ]
  return (
    <>
      <PageHeading title="Reports" description="Download focused snapshots of student success, risk and readiness for your team." />
      {notice && <Notice tone={notice.tone} onDismiss={() => setNotice(null)}>{notice.text}</Notice>}
      <Notice>Reports contain student names and IDs. Share them only with staff who support students.</Notice>
      <div className="module-grid">
        {cards.map(c => (
          <article className="module-card" key={c.job}>
            <div><h2>{c.title}</h2><p>{c.body}</p></div>
            <div className="module-card-foot">
              <button className="button button-secondary" disabled={busy !== null} onClick={() => run(c.job)}><Download size={16} />{busy === c.job ? 'Preparing…' : 'Download CSV'}</button>
            </div>
          </article>
        ))}
      </div>
    </>
  )
}
