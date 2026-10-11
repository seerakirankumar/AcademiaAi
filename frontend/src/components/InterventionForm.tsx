import { useState, type FormEvent } from 'react'
import { write } from '../lib/api'
import { errorMessage } from '../lib/hooks'
import type { Intervention, Metadata } from '../lib/types'
import Modal from './Modal'
import { Notice } from './Primitives'

export default function InterventionForm({ metadata, studentId, defaultType, onClose, onSaved }: {
  metadata: Metadata; studentId?: string; defaultType?: string | null; onClose: () => void; onSaved: (i: Intervention) => void
}) {
  const [sid, setSid] = useState(studentId ?? '')
  const [type, setType] = useState(defaultType && metadata.intervention_types.includes(defaultType) ? defaultType : metadata.intervention_types[0] ?? '')
  const [status, setStatus] = useState(metadata.intervention_statuses[0] ?? 'Recommended')
  const [date, setDate] = useState(new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10))
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null)
    try {
      onSaved(await write<Intervention>('POST', '/api/interventions', {
        student_id: sid.trim().toUpperCase(), intervention_type: type, status, assigned_date: date, follow_up_notes: notes,
      }))
    } catch (err) { setError(errorMessage(err)); setBusy(false) }
  }

  return (
    <Modal title="Record intervention" onClose={onClose}
      footer={<>
        <button type="button" className="button button-secondary" onClick={onClose}>Cancel</button>
        <button type="submit" form="iv-form" className="button button-primary" disabled={busy || !sid}>{busy ? 'Saving…' : 'Save intervention'}</button>
      </>}>
      <form id="iv-form" onSubmit={submit}>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="form-grid">
          <label className="form-field">Student ID<input value={sid} onChange={e => setSid(e.target.value)} readOnly={!!studentId} required placeholder="STU20260001" /></label>
          <label className="form-field">Type<select value={type} onChange={e => setType(e.target.value)}>{metadata.intervention_types.map(t => <option key={t}>{t}</option>)}</select></label>
          <label className="form-field">Status<select value={status} onChange={e => setStatus(e.target.value)}>{metadata.intervention_statuses.map(t => <option key={t}>{t}</option>)}</select></label>
          <label className="form-field">Assigned date<input type="date" value={date} onChange={e => setDate(e.target.value)} required /></label>
          <label className="form-field wide">Follow-up notes<textarea value={notes} onChange={e => setNotes(e.target.value)} maxLength={500} /></label>
        </div>
      </form>
    </Modal>
  )
}
