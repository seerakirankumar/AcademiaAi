import { useState } from 'react'
import { ArrowUpRight, Search } from 'lucide-react'
import { get } from '../lib/api'
import { useLoad, useMetadata } from '../lib/hooks'
import type { RiskItem } from '../lib/types'
import { Async, Avatar, EmptyState, PageHeading, RiskPill, ScoreCell } from '../components/Primitives'
import StudentDrawer from '../components/StudentDrawer'

const PAGE_SIZE = 15

export default function RiskPage({ kind }: { kind: 'academic' | 'placement' }) {
  const [level, setLevel] = useState('High')
  const [dept, setDept] = useState('')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const meta = useMetadata()
  const param = kind === 'academic' ? 'academic_level' : 'placement_level'
  const list = useLoad<RiskItem[]>(
    () => get<RiskItem[]>('/api/risks', { [param]: level, department: dept, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    JSON.stringify([kind, level, dept, page]))
  const total = list.meta.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const title = kind === 'academic' ? 'Academic risk' : 'Placement readiness'

  return (
    <>
      <PageHeading
        title={title}
        description={kind === 'academic'
          ? 'Identify students who may need academic support, with clear reasons behind each flag.'
          : 'Help students prepare for opportunities by identifying skill and assessment gaps early.'} />
      <div className="panel">
        <div className="directory-toolbar">
          <div className="directory-count"><strong>{total} students</strong><small>Sorted by combined risk points, highest first</small></div>
          <div className="filter-controls">
            <select className="select" aria-label="Risk level" value={level} onChange={e => { setLevel(e.target.value); setPage(0) }}>
              <option value="">Any level</option>{['High', 'Medium', 'Low', 'Not applicable', 'Insufficient data'].map(l => <option key={l}>{l}</option>)}</select>
            <select className="select" aria-label="Department" value={dept} onChange={e => { setDept(e.target.value); setPage(0) }}>
              <option value="">All departments</option>{meta.data?.departments.map(d => <option key={d}>{d}</option>)}</select>
          </div>
        </div>
        <Async loading={list.loading && !list.data} error={list.error} onRetry={list.reload}>
          <div className="table-wrap" style={{ opacity: list.loading ? 0.6 : 1 }}>
            <table className="data-table">
              <thead><tr><th>Student</th><th>Department</th><th>Success score</th><th>{title}</th><th>Why flagged</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {(list.data ?? []).map(r => {
                  const risk = kind === 'academic' ? r.academic_risk : r.placement_risk
                  return (
                    <tr key={r.student_id} className="clickable-row" onClick={() => setSelected(r.student_id)}>
                      <td><div className="student-cell"><Avatar name={r.student_name} id={r.student_id} />
                        <button className="cell-link" onClick={e => { e.stopPropagation(); setSelected(r.student_id) }}><strong>{r.student_name}</strong><small>{r.student_id}</small></button></div></td>
                      <td>{r.department}</td>
                      <td><ScoreCell score={r.success_score === null ? null : Math.round(r.success_score)} /></td>
                      <td><RiskPill risk={risk.level} /><br /><small style={{ color: 'var(--muted)' }}>{risk.points}/{risk.max_points} pts</small></td>
                      <td style={{ maxWidth: 360 }}>
                        {risk.reasons.length === 0 ? <small style={{ color: 'var(--muted)' }}>{risk.note ?? 'No flags'}</small>
                          : <ul className="risk-reasons">{risk.reasons.slice(0, 3).map(x => <li key={x}>{x}</li>)}{risk.reasons.length > 3 && <li>+{risk.reasons.length - 3} more</li>}</ul>}
                      </td>
                      <td><span className="row-arrow" aria-hidden="true"><ArrowUpRight size={16} /></span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {(list.data ?? []).length === 0 && <EmptyState icon={<Search size={22} />} title="No students at this level" body="Try a different risk level or department." />}
          </div>
          {total > 0 && (
            <div className="table-footer">
              <span>Showing {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total}</span>
              <div className="pager">
                <button className="button button-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                <span>Page {page + 1} of {pageCount}</span>
                <button className="button button-secondary" disabled={page >= pageCount - 1} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          )}
        </Async>
      </div>
      {selected && <StudentDrawer studentId={selected} onClose={() => setSelected(null)} onChanged={list.reload} />}
    </>
  )
}
