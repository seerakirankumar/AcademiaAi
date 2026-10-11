import { useState, type FormEvent } from 'react'
import { write } from '../lib/api'
import { errorMessage } from '../lib/hooks'
import type { Metadata, Profile } from '../lib/types'
import Modal from './Modal'
import { Notice } from './Primitives'

type Kind = 'text' | 'int' | 'float' | 'select'
interface Field { key: string; label: string; kind: Kind; group: keyof Profile | 'personal'; options?: string[]; step?: string; min?: number; max?: number; required?: boolean }

const F = (group: Field['group'], key: string, label: string, kind: Kind = 'float', extra: Partial<Field> = {}): Field => ({ group, key, label, kind, ...extra })
const pct = { min: 0, max: 100, step: '0.1' }

const SECTIONS: { title: string; fields: (m: Metadata) => Field[] }[] = [
  { title: 'Student', fields: m => [
    F('personal', 'student_name', 'Full name', 'text', { required: true }),
    F('personal', 'department', 'Department', 'select', { required: true, options: m.departments }),
    F('personal', 'year_of_study', 'Year of study', 'int', { required: true, min: 1, max: 8 }),
    F('personal', 'section', 'Section', 'text', { required: true }),
    F('personal', 'admission_year', 'Admission year', 'int', { required: true, min: 1990, max: 2100 }),
    F('personal', 'student_email', 'Email', 'text'),
  ] },
  { title: 'Academics & attendance', fields: () => [
    F('academics', 'cgpa', 'CGPA (0–10)', 'float', { min: 0, max: 10, step: '0.01' }),
    F('academics', 'backlogs', 'Backlogs', 'int', { min: 0 }),
    F('academics', 'internal_score_pct', 'Internal score %', 'float', pct),
    F('academics', 'semester_score_pct', 'Semester score %', 'float', pct),
    F('attendance', 'overall_attendance_pct', 'Overall attendance %', 'float', pct),
    F('attendance', 'subjects_below_attendance_threshold', 'Subjects below attendance threshold', 'int', { min: 0 }),
  ] },
  { title: 'Learning platform & engagement', fields: () => [
    F('lms', 'logins_last_30_days', 'LMS logins (30 days)', 'int', { min: 0 }),
    F('lms', 'assignment_completion_pct', 'Assignment completion %', 'float', pct),
    F('lms', 'avg_weekly_learning_hours', 'Weekly learning hours', 'float', { min: 0, max: 168, step: '0.1' }),
    F('engagement', 'events_attended', 'Events attended', 'int', { min: 0 }),
    F('engagement', 'hackathons_participated', 'Hackathons', 'int', { min: 0 }),
    F('engagement', 'club_participation', 'Club participation', 'select', { options: ['None', 'Occasional', 'Active'] }),
    F('engagement', 'volunteer_hours', 'Volunteer hours', 'float', { min: 0, step: '0.1' }),
  ] },
  { title: 'Skills & placement', fields: m => [
    F('skills', 'technical_skill_score', 'Technical skill score', 'float', pct),
    F('skills', 'soft_skill_score', 'Soft skill score', 'float', pct),
    F('skills', 'certifications_count', 'Certifications', 'int', { min: 0 }),
    F('skills', 'projects_count', 'Projects', 'int', { min: 0 }),
    F('placement', 'aptitude_score', 'Aptitude score', 'float', pct),
    F('placement', 'coding_score', 'Coding score', 'float', pct),
    F('placement', 'mock_interview_score', 'Mock interview score', 'float', pct),
    F('placement', 'resume_readiness_pct', 'Resume readiness %', 'float', pct),
    F('placement', 'placement_status', 'Placement status', 'select', { options: Array.from(new Set(['Not started', 'Eligible', 'Training', 'Placed', ...m.placement_statuses])) }),
  ] },
  { title: 'Feedback', fields: () => [
    F('feedback', 'student_satisfaction_1_to_5', 'Student satisfaction (1–5)', 'float', { min: 1, max: 5, step: '0.1' }),
    F('feedback', 'faculty_feedback_1_to_5', 'Faculty feedback (1–5)', 'float', { min: 1, max: 5, step: '0.1' }),
    F('feedback', 'support_requested', 'Support requested', 'select', { options: ['No', 'Yes'] }),
    F('feedback', 'feedback_topic', 'Feedback topic', 'text'),
  ] },
]

const initial = (profile: Profile | undefined, f: Field) => {
  const v = profile ? (profile[f.group as keyof Profile] as Record<string, unknown> | undefined)?.[f.key] : undefined
  return v === null || v === undefined ? '' : String(v)
}

export default function StudentForm({ profile, metadata, onClose, onSaved }: {
  profile?: Profile; metadata: Metadata; onClose: () => void; onSaved: (p: Profile) => void
}) {
  const editing = !!profile
  const sections = SECTIONS.map(s => ({ ...s, list: s.fields(metadata) }))
  const all = sections.flatMap(s => s.list)
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(all.map(f => [f.key, initial(profile, f)])))
  const [studentId, setStudentId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = (k: string, v: string) => setValues(s => ({ ...s, [k]: v }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const payload: Record<string, string | number> = {}
    for (const f of all) {
      const raw = values[f.key].trim()
      if (raw === '' || (editing && raw === initial(profile, f))) continue
      payload[f.key] = f.kind === 'int' || f.kind === 'float' ? Number(raw) : raw
    }
    if (editing && Object.keys(payload).length === 0) { setError('No changes to save.'); return }
    if (!editing && studentId.trim()) payload.student_id = studentId.trim().toUpperCase()
    setBusy(true); setError(null)
    try {
      const saved = editing
        ? await write<Profile>('PATCH', `/api/students/${encodeURIComponent(profile.student_id)}`, payload)
        : await write<Profile>('POST', '/api/students', payload)
      onSaved(saved)
    } catch (err) { setError(errorMessage(err)); setBusy(false) }
  }

  return (
    <Modal title={editing ? `Edit ${profile.personal.student_name}` : 'Add student'} onClose={onClose}
      footer={<>
        <button type="button" className="button button-secondary" onClick={onClose}>Cancel</button>
        <button type="submit" form="student-form" className="button button-primary" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Add student'}</button>
      </>}>
      <form id="student-form" onSubmit={submit}>
        {error && <Notice tone="error">{error}</Notice>}
        {!editing && <Notice>Required fields are in the first section. Anything left blank is stored as “not measured”, never as zero.</Notice>}
        <div className="form-grid">
          {!editing && (
            <label className="form-field wide">Student ID <small>Optional — format STU########. Leave blank to generate the next ID.</small>
              <input value={studentId} onChange={e => setStudentId(e.target.value)} pattern="STU[0-9]{8}" placeholder="STU20260501" />
            </label>
          )}
          {sections.map(s => (
            <FormSection key={s.title} title={s.title}>
              {s.list.map(f => (
                <label className="form-field" key={f.key}>{f.label}{f.required && ' *'}
                  {f.kind === 'select' ? (
                    <select value={values[f.key]} onChange={e => set(f.key, e.target.value)} required={f.required && !editing}>
                      <option value="">{f.required ? 'Select…' : '— not set —'}</option>
                      {f.options?.map(o => <option key={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input value={values[f.key]} onChange={e => set(f.key, e.target.value)} required={f.required && !editing}
                      type={f.kind === 'text' ? (f.key === 'student_email' ? 'email' : 'text') : 'number'}
                      step={f.kind === 'int' ? '1' : 'any'} min={f.min} max={f.max} />
                  )}
                </label>
              ))}
            </FormSection>
          ))}
        </div>
      </form>
    </Modal>
  )
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <><div className="form-section">{title}</div>{children}</>
}
