import { get } from '../lib/api'
import { useLoad, useMetadata } from '../lib/hooks'
import type { Health } from '../lib/types'
import { Async, Notice, PageHeading, Panel } from '../components/Primitives'

export default function DataPage() {
  const meta = useMetadata()
  const health = useLoad<Health>(() => get<Health>('/api/health'), 'health')
  const m = meta.data
  return (
    <>
      <PageHeading title="Data management" description="See which files power the dashboard and whether they loaded cleanly." />
      <Async loading={meta.loading || health.loading} error={meta.error ?? health.error} onRetry={() => { meta.reload(); health.reload() }}>
        {health.data && <Notice tone={health.data.warning_count ? 'info' : 'success'}>
          Service is <strong>{health.data.service}</strong> · {health.data.student_count} students · {health.data.intervention_count} interventions · {health.data.warning_count} warnings.
        </Notice>}
        {m?.warnings.map(w => <Notice key={w}>{w}</Notice>)}
        <Panel flush title="Working data files" subtitle="Student and intervention changes are written to these CSV files in the backend's data folder">
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Dataset</th><th>File</th><th>Rows</th><th>Columns</th></tr></thead>
              <tbody>
                {Object.entries(m?.datasets ?? {}).map(([name, d]) => (
                  <tr key={name}><td><strong>{name}</strong></td><td>{d.file}</td><td className="num">{d.rows}</td><td style={{ maxWidth: 480, color: 'var(--muted)' }}>{d.columns.join(', ')}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <div style={{ marginTop: 16 }}>
          <Panel title="Notes"><ul className="risk-reasons">{m?.data_notes.map(n => <li key={n}>{n}</li>)}</ul></Panel>
        </div>
      </Async>
    </>
  )
}
