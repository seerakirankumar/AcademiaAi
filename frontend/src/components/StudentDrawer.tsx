import { useEffect, useRef, useState } from 'react'
import { Check, CircleAlert, Pencil, Plus, X } from 'lucide-react'
import { get } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useLoad, useMetadata } from '../lib/hooks'
import { num, pct } from '../lib/format'
import type { Profile, RiskView } from '../lib/types'
import { Async, Avatar, Meter, RiskPill, scoreTone, useEscape } from './Primitives'
import StudentForm from './StudentForm'
import InterventionForm from './InterventionForm'

const COMPONENT_LABELS: Record<string, string> = {
  academic: 'Academic performance', attendance: 'Attendance', lms: 'Learning activity', placement_readiness: 'Placement readiness',
}

function Indicator({ label, value }: { label: string; value: number | string | null | undefined }) {
  const n = typeof value === 'number' ? value : null
  return (
    <div className="indicator">
      <div className="indicator-head">
        <span>{label}</span>
        {n === null ? <span className="not-measured">Not measured</span> : <strong>{num(n, 1)}%</strong>}
      </div>
      {n !== null && <Meter wide value={n} color={scoreTone(n).color} label={label} />}
    </div>
  )
}

function RiskBlock({ title, risk }: { title: string; risk: RiskView }) {
  return (
    <div className="kv-row" style={{ alignItems: 'flex-start' }}>
      <span>{title}
        <small>{risk.points}/{risk.max_points} rule points · not a probability</small>
        {risk.reasons.length > 0 && <ul className="risk-reasons">{risk.reasons.map(r => <li key={r}>{r}</li>)}</ul>}
        {risk.note && <small>{risk.note}</small>}
      </span>
      <RiskPill risk={risk.level} />
    </div>
  )
}

export default function StudentDrawer({ studentId, onClose, onChanged }: { studentId: string; onClose: () => void; onChanged?: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const { can } = useAuth()
  const [editing, setEditing] = useState(false)
  const [recording, setRecording] = useState<{ type: string | null } | null>(null)
  const [override, setOverride] = useState<Profile | null>(null)
  const meta = useMetadata()
  const load = useLoad<Profile>(() => get<Profile>(`/api/students/${encodeURIComponent(studentId)}`), studentId)
  const profile = override ?? load.data

  useEscape(onClose, !editing && !recording)
  useEffect(() => {
    closeRef.current?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previous }
  }, [])

  const score = profile?.success_score.score ?? null
  const tone = scoreTone(score)
  const p = profile
  const name = String(p?.personal.student_name ?? studentId)

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="student-drawer" role="dialog" aria-modal="true" aria-label={`${name} — student overview`} onClick={e => e.stopPropagation()}>
        <div className="drawer-top">
          <span>Student overview</span>
          <button ref={closeRef} className="icon-button" onClick={onClose} aria-label="Close student overview"><X size={18} /></button>
        </div>
        <div className="drawer-body">
          <Async loading={load.loading && !override} error={load.error} onRetry={load.reload}>
            {p && (<>
              <div className="drawer-person">
                <Avatar name={name} id={p.student_id} large />
                <div>
                  <h2>{name}</h2>
                  <p>{p.student_id} · {String(p.personal.department)} · Year {String(p.personal.year_of_study)}, Section {String(p.personal.section)}</p>
                </div>
              </div>
              <div className="drawer-actions">
                {can('admin') && <button className="button button-secondary" onClick={() => setEditing(true)} disabled={!meta.data}><Pencil size={15} />Edit student</button>}
                <button className="button button-secondary" onClick={() => setRecording({ type: null })} disabled={!meta.data}><Plus size={15} />Record intervention</button>
              </div>

              <div className="drawer-score">
                <div>
                  <span className="label">Student Success Score</span>
                  <small>{tone.label} · {p.success_score.coverage >= 1 ? 'All indicators measured' : `${Math.round(p.success_score.coverage * 100)}% of the score is based on measured data`}</small>
                </div>
                <strong style={{ color: tone.color }}>{score === null ? '—' : num(score, 1)}<small>/100</small></strong>
              </div>

              <section className="drawer-section">
                <h3>Support needed</h3>
                <p className="help">Segment: <strong>{p.segment.name}</strong>{p.segment.description ? ` — ${p.segment.description}` : ''}</p>
                <RiskBlock title="Academic risk" risk={p.risk.academic} />
                <RiskBlock title="Placement risk" risk={p.risk.placement} />
                <p className="disclaimer">{p.risk.disclaimer}</p>
              </section>

              <section className="drawer-section">
                <h3>Academic indicators</h3>
                <div className="kv-row"><span>CGPA</span><strong>{p.academics.cgpa === null ? '—' : `${num(Number(p.academics.cgpa), 2)} / ${String(p.academics.cgpa_scale_max)}`}</strong></div>
                <Indicator label="Semester score" value={p.academics.semester_score_pct} />
                <Indicator label="Internal assessment" value={p.academics.internal_score_pct} />
                <Indicator label="Attendance" value={p.attendance.overall_attendance_pct} />
                <Indicator label="Assignment completion" value={p.lms.assignment_completion_pct} />
                <div className="kv-row"><span>Active backlogs</span><strong>{p.academics.backlogs ?? '—'}</strong></div>
                <div className="kv-row"><span>Subjects below attendance threshold</span><strong>{p.attendance.subjects_below_attendance_threshold ?? '—'}</strong></div>
                <div className="kv-row"><span>LMS logins (30 days)</span><strong>{p.lms.logins_last_30_days ?? '—'}</strong></div>
              </section>

              <section className="drawer-section">
                <h3>Skills & placement readiness</h3>
                <Indicator label="Aptitude" value={p.placement.aptitude_score} />
                <Indicator label="Coding assessment" value={p.placement.coding_score} />
                <Indicator label="Mock interview" value={p.placement.mock_interview_score} />
                <Indicator label="Resume readiness" value={p.placement.resume_readiness_pct} />
                <Indicator label="Technical skills" value={p.skills.technical_skill_score} />
                <Indicator label="Soft skills" value={p.skills.soft_skill_score} />
                <div className="kv-row"><span>Placement status</span><strong>{String(p.placement.placement_status ?? '—')}</strong></div>
              </section>

              <section className="drawer-section">
                <h3>How the score is calculated</h3>
                <p className="help">Each component contributes according to its weight; missing data is reweighted, never counted as zero.</p>
                {Object.entries(p.success_score.components).map(([key, c]) => (
                  <div className="kv-row" key={key}>
                    <span>{COMPONENT_LABELS[key] ?? key}<small>{Math.round(c.weight * 100)}% weight</small></span>
                    {c.score === null ? <span className="not-measured">Not measured</span> : <strong>{num(c.score, 1)}/100</strong>}
                  </div>
                ))}
                <p className="disclaimer">{p.success_score.note}</p>
              </section>

              <section className="drawer-section">
                <h3>Suggested support</h3>
                {p.recommendations.length === 0
                  ? <div className="reason-row positive"><Check size={16} /><span>No recommendations from the current rules.</span></div>
                  : p.recommendations.map(r => (
                    <div className="rec-card" key={r.id}>
                      <strong>{r.title}</strong> <span className="tag">{r.priority}</span>
                      <p>{r.description}</p>
                      {r.suggested_steps.length > 0 && <ul className="risk-reasons">{r.suggested_steps.map(s => <li key={s}>{s}</li>)}</ul>}
                      {r.related_intervention_type && !r.existing_open_intervention && (
                        <button className="text-button" onClick={() => setRecording({ type: r.related_intervention_type })}>Record “{r.related_intervention_type}”</button>
                      )}
                    </div>
                  ))}
              </section>

              <section className="drawer-section">
                <h3>Interventions</h3>
                {p.interventions.length === 0
                  ? <p className="help">No interventions recorded yet.</p>
                  : p.interventions.map(i => (
                    <div className="kv-row" key={i.intervention_id}>
                      <span>{i.intervention_type}<small>{i.assigned_date} · {i.intervention_id}{i.follow_up_notes ? ` · ${i.follow_up_notes}` : ''}</small></span>
                      <span className="tag">{i.status}</span>
                    </div>
                  ))}
              </section>

              <section className="drawer-section">
                <h3>Data quality</h3>
                <div className="kv-row"><span>Record completeness</span><strong>{pct(p.data_quality.completeness_pct)}</strong></div>
                {p.data_quality.missing_fields.length > 0 && (
                  <div className="reason-row"><CircleAlert size={16} /><span>Not recorded: {p.data_quality.missing_fields.join(', ')}</span></div>
                )}
              </section>
            </>)}
          </Async>
        </div>
      </aside>
      {editing && p && meta.data && (
        <div onClick={e => e.stopPropagation()}>
          <StudentForm profile={p} metadata={meta.data} onClose={() => setEditing(false)}
            onSaved={saved => { setOverride(saved); setEditing(false); onChanged?.() }} />
        </div>
      )}
      {recording && p && meta.data && (
        <div onClick={e => e.stopPropagation()}>
          <InterventionForm metadata={meta.data} studentId={p.student_id} defaultType={recording.type} onClose={() => setRecording(null)}
            onSaved={() => { setRecording(null); setOverride(null); load.reload(); onChanged?.() }} />
        </div>
      )}
    </div>
  )
}
