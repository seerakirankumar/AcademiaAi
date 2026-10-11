import { useState } from 'react'
import { Plus, Search } from 'lucide-react'
import { get, write } from '../lib/api'
import { errorMessage, useLoad, useMetadata } from '../lib/hooks'
import type { Intervention } from '../lib/types'
import { Async, EmptyState, Notice, PageHeading } from '../components/Primitives'
import InterventionForm from '../components/InterventionForm'
import StudentDrawer from '../components/StudentDrawer'

const PAGE_SIZE = 15

export default function Interventions() {
  const meta = useMetadata()
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [page, setPage] = useState(0)
  const [adding, setAdding] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const list = useLoad<Intervention[]>(
    () => get<Intervention[]>('/api/interventions', { status, intervention_type: type, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    JSON.stringify([status, type, page]))
  const total = list.meta.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const changeStatus = async (i: Intervention, next: string) => {
    try {
      await write('PATCH', `/api/interventions/${encodeURIComponent(i.intervention_id)}`, { status: next })
      setNotice({ tone: 'success', text: `${i.intervention_id} marked ${next}.` }); list.reload()
    } catch (e) { setNotice({ tone: 'error', text: errorMessage(e) }) }
  }

  return (
    <>
      <PageHeading title="Interventions" description="Track the support offered to students. Changes are saved to the interventions file."
        actions={<button className="button button-primary" onClick={() => setAdding(true)} disabled={!meta.data}><Plus size={16} />Record intervention</button>} />
      {notice && <Notice tone={notice.tone} onDismiss={() => setNotice(null)}>{notice.text}</Notice>}
      <div className="panel">
        <div className="directory-toolbar">
          <div className="directory-count"><strong>{total} interventions</strong>
            <small>{Object.entries(list.meta.status_counts ?? {}).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(' · ') || 'None recorded yet'}</small></div>
          <div className="filter-controls">
            <select className="select" aria-label="Status" value={status} onChange={e => { setStatus(e.target.value); setPage(0) }}>
              <option value="">Any status</option>{meta.data?.intervention_statuses.map(s => <option key={s}>{s}</option>)}</select>
            <select className="select" aria-label="Type" value={type} onChange={e => { setType(e.target.value); setPage(0) }}>
              <option value="">Any type</option>{meta.data?.intervention_types.map(s => <option key={s}>{s}</option>)}</select>
          </div>
        </div>
        <Async loading={list.loading && !list.data} error={list.error} onRetry={list.reload}>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>ID</th><th>Student</th><th>Type</th><th>Assigned</th><th>Status</th><th>Notes</th></tr></thead>
              <tbody>
                {(list.data ?? []).map(i => (
                  <tr key={i.intervention_id}>
                    <td>{i.intervention_id}</td>
                    <td><button className="cell-link" onClick={() => setSelected(i.student_id)}><strong>{i.student_name ?? i.student_id}</strong>{i.student_name && <small>{i.student_id}</small>}</button></td>
                    <td>{i.intervention_type}</td><td>{i.assigned_date}</td>
                    <td><select className="select" aria-label={`Status of ${i.intervention_id}`} value={i.status} onChange={e => changeStatus(i, e.target.value)}>
                      {meta.data?.intervention_statuses.map(s => <option key={s}>{s}</option>) ?? <option>{i.status}</option>}</select></td>
                    <td style={{ maxWidth: 320 }}>{i.follow_up_notes || <span style={{ color: 'var(--muted)' }}>—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(list.data ?? []).length === 0 && <EmptyState icon={<Search size={22} />} title="No interventions yet" body="Record one here, or from a student's profile." />}
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
      {adding && meta.data && <InterventionForm metadata={meta.data} onClose={() => setAdding(false)}
        onSaved={i => { setAdding(false); setNotice({ tone: 'success', text: `Recorded ${i.intervention_id}.` }); list.reload() }} />}
      {selected && <StudentDrawer studentId={selected} onClose={() => setSelected(null)} onChanged={list.reload} />}
    </>
  )
}
