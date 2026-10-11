import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowUpRight, Download, Plus, Search, X } from 'lucide-react'
import { get, getAll } from '../lib/api'
import { useAuth } from '../lib/auth'
import { downloadCsv } from '../lib/format'
import { useDebounced, useLoad, useMetadata } from '../lib/hooks'
import type { StudentListItem } from '../lib/types'
import { Async, Avatar, EmptyState, Notice, PageHeading, RiskPill, ScoreCell } from '../components/Primitives'
import StudentDrawer from '../components/StudentDrawer'
import StudentForm from '../components/StudentForm'

const PAGE_SIZE = 15
const RISKS = ['Low', 'Medium', 'High']

export default function Students() {
  const [params] = useSearchParams()
  const { can } = useAuth()
  const meta = useMetadata()
  const [q, setQ] = useState(params.get('q') ?? '')
  const [dept, setDept] = useState('')
  const [year, setYear] = useState('')
  const [academic, setAcademic] = useState(params.get('academic') ?? '')
  const [placement, setPlacement] = useState(params.get('placement') ?? '')
  const [segment, setSegment] = useState('')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  // Follow top-bar searches that arrive while this page is already open.
  const urlQ = params.get('q')
  useEffect(() => { setQ(urlQ ?? ''); setPage(0) }, [urlQ])

  const dq = useDebounced(q)
  const query = { search: dq.trim(), department: dept, year_of_study: year, academic_risk: academic, placement_risk: placement, segment }
  const list = useLoad<StudentListItem[]>(
    () => get<StudentListItem[]>('/api/students', { search: query.search, department: dept, year, academic_risk: academic, placement_risk: placement, segment, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    JSON.stringify([query, page]))

  const total = list.meta.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const filtersActive = !!(q || dept || year || academic || placement || segment)
  const reset = () => { setQ(''); setDept(''); setYear(''); setAcademic(''); setPlacement(''); setSegment(''); setPage(0) }
  const upd = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLSelectElement>) => { fn(e.target.value); setPage(0) }

  const exportCsv = async () => {
    try {
      const rows = await getAll<StudentListItem>('/api/students', { search: query.search, department: dept, year, academic_risk: academic, placement_risk: placement, segment })
      downloadCsv('academia-students.csv', [
        ['ID', 'Name', 'Department', 'Year', 'Section', 'CGPA', 'Attendance %', 'Success score', 'Academic risk', 'Placement risk', 'Segment', 'Placement status'],
        ...rows.map(s => [s.student_id, s.student_name, s.department, s.year_of_study, s.section, s.cgpa, s.overall_attendance_pct, s.success_score, s.academic_risk_level, s.placement_risk_level, s.segment, s.placement_status]),
      ])
    } catch (e) { setNotice(e instanceof Error ? e.message : 'Export failed.') }
  }

  return (
    <>
      <PageHeading
        title="Students"
        description="Find a student, understand their current indicators, and see where support may help."
        actions={<>
          <button className="button button-secondary" onClick={exportCsv}><Download size={16} />Export list</button>
          {can('admin') && <button className="button button-primary" onClick={() => setAdding(true)} disabled={!meta.data}><Plus size={16} />Add student</button>}
        </>}
      />
      {notice && <Notice tone="success" onDismiss={() => setNotice(null)}>{notice}</Notice>}

      <div className="panel">
        <div className="directory-toolbar">
          <div className="directory-count"><strong>{total} students</strong><small>{filtersActive ? 'Matching your filters' : 'In this directory'}</small></div>
          <div className="filter-controls">
            <label className="field"><Search size={16} /><span className="sr-only">Search students</span>
              <input placeholder="Search by name or ID" value={q} onChange={e => { setQ(e.target.value); setPage(0) }} /></label>
            <select className="select" aria-label="Department" value={dept} onChange={upd(setDept)}>
              <option value="">All departments</option>{meta.data?.departments.map(d => <option key={d}>{d}</option>)}</select>
            <select className="select" aria-label="Year" value={year} onChange={upd(setYear)}>
              <option value="">All years</option>{meta.data?.years_of_study.map(y => <option key={y} value={y}>Year {y}</option>)}</select>
            <select className="select" aria-label="Academic risk" value={academic} onChange={upd(setAcademic)}>
              <option value="">Any academic risk</option>{RISKS.map(r => <option key={r} value={r}>Academic: {r}</option>)}</select>
            <select className="select" aria-label="Placement risk" value={placement} onChange={upd(setPlacement)}>
              <option value="">Any placement risk</option>{RISKS.map(r => <option key={r} value={r}>Placement: {r}</option>)}</select>
            <select className="select" aria-label="Segment" value={segment} onChange={upd(setSegment)}>
              <option value="">All segments</option>{meta.data?.segments.map(r => <option key={r}>{r}</option>)}</select>
            {filtersActive && <button className="text-button" onClick={reset}><X size={15} />Clear filters</button>}
          </div>
        </div>

        <Async loading={list.loading && !list.data} error={list.error} onRetry={list.reload}>
          <div className="table-wrap" style={{ opacity: list.loading ? 0.6 : 1 }}>
            <table className="data-table">
              <thead><tr><th>Student</th><th>Department</th><th>Year</th><th>Success score</th><th>Academic risk</th><th>Placement risk</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {(list.data ?? []).map(s => (
                  <tr key={s.student_id} className="clickable-row" onClick={() => setSelected(s.student_id)}>
                    <td><div className="student-cell"><Avatar name={s.student_name} id={s.student_id} />
                      <button className="cell-link" onClick={e => { e.stopPropagation(); setSelected(s.student_id) }}><strong>{s.student_name}</strong><small>{s.student_id}</small></button></div></td>
                    <td>{s.department}</td>
                    <td>{s.year_of_study ?? '—'}</td>
                    <td><ScoreCell score={s.success_score === null ? null : Math.round(s.success_score)} /></td>
                    <td><RiskPill risk={s.academic_risk_level} /></td>
                    <td><RiskPill risk={s.placement_risk_level} /></td>
                    <td><span className="row-arrow" aria-hidden="true"><ArrowUpRight size={16} /></span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(list.data ?? []).length === 0 && <EmptyState icon={<Search size={22} />} title="No matching students" body="Try a different name, ID or filter." />}
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
      {adding && meta.data && (
        <StudentForm metadata={meta.data} onClose={() => setAdding(false)}
          onSaved={p => { setAdding(false); setNotice(`Added ${String(p.personal.student_name)} (${p.student_id}).`); list.reload(); setSelected(p.student_id) }} />
      )}
    </>
  )
}
