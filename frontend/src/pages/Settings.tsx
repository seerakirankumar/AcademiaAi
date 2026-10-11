import { useMetadata } from '../lib/hooks'
import { Async, Meter, PageHeading, Panel } from '../components/Primitives'
import { chartColors } from '../components/chartTheme'

const LABELS: Record<string, string> = { academic: 'Academic performance', attendance: 'Attendance', lms: 'Learning activity', placement_readiness: 'Placement readiness' }
const RULES: Record<string, string> = {
  priority_score_below: 'Priority support: success score below',
  priority_high_risk_score_below: 'Priority support: high risk together with a score below',
  needs_support_score_below: 'Needs support: success score below',
  high_readiness_min_score: 'High readiness: success score of at least',
}

export default function Settings() {
  const meta = useMetadata()
  const m = meta.data
  return (
    <>
      <PageHeading title="Methodology" description="How the Student Success Score, risk levels and segments are calculated." />
      <Async loading={meta.loading} error={meta.error} onRetry={meta.reload}>
        {m && (<>
          <Panel flush title="Student Success Score weights" subtitle="Weights add up to 100%; missing data is reweighted rather than treated as zero">
            <div className="weights">
              {Object.entries(m.score_weights).map(([k, w]) => (
                <div className="indicator" key={k}>
                  <div className="indicator-head"><span>{LABELS[k] ?? k}</span><strong>{Math.round(w * 100)}%</strong></div>
                  <Meter wide value={w * 100 * 2} color={chartColors.academic} label={`${LABELS[k] ?? k} weight`} />
                </div>
              ))}
            </div>
          </Panel>
          <div style={{ marginTop: 16 }}>
            <Panel flush title="Segment rules" subtitle="Thresholds used to place students in a support segment">
              <div className="weights">
                {Object.entries(m.segment_rules).map(([k, v]) => (
                  <div className="kv-row" key={k}><span>{RULES[k] ?? k}</span><strong>{v}</strong></div>
                ))}
              </div>
            </Panel>
          </div>
        </>)}
      </Async>
    </>
  )
}
