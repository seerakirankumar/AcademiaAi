import { useEffect, type ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, Check, CircleAlert, Info, X } from 'lucide-react'
import type { RiskLevel } from '../lib/types'

/* ---- helpers ------------------------------------------------------------ */
export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).map(part => part[0]).slice(0, 2).join('').toUpperCase() || '?'
}
/** Same thresholds as before: 75+ strong, 60–74 on track, below 60 needs a look. */
export function scoreTone(score: number | null) {
  if (score === null) return { color: 'var(--faint)', label: 'Not enough data' }
  if (score >= 75) return { color: 'var(--green)', label: 'Strong' }
  if (score >= 60) return { color: 'var(--accent)', label: 'On track' }
  return { color: 'var(--amber)', label: 'Needs attention' }
}
export const avatarTone = (id: string) => `avatar-${(Number(id.slice(-2)) || 0) % 6}`

/* ---- page structure ------------------------------------------------------ */
export function PageHeading({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <header className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="heading-actions">{actions}</div>}
    </header>
  )
}

export function Panel({ title, subtitle, action, children, className = '', flush = false }: {
  title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string; flush?: boolean
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action && <div className="panel-action">{action}</div>}
      </div>
      {flush ? children : <div className="panel-body">{children}</div>}
    </section>
  )
}

export function Notice({ tone = 'info', children, onDismiss, icon }: {
  tone?: 'info' | 'success' | 'error'; children: ReactNode; onDismiss?: () => void; icon?: ReactNode
}) {
  return (
    <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : tone === 'success' ? 'status' : undefined}>
      {icon ?? (tone === 'success' ? <Check size={16} /> : tone === 'error' ? <CircleAlert size={16} /> : <Info size={16} />)}
      <span>{children}</span>
      {onDismiss && <button className="dismiss" aria-label="Dismiss message" onClick={onDismiss}><X size={15} /></button>}
    </div>
  )
}

/* ---- data display -------------------------------------------------------- */
export function MetricCard({ label, value, sub, change, icon }: {
  label: string; value: string | number; sub: string; change?: string; icon: ReactNode
}) {
  return (
    <article className="metric-card">
      <div className="metric-top"><span className="metric-label">{label}</span>{icon}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-bottom">
        <span>{sub}</span>
        {change && <span className="metric-change"><ArrowUpRight size={14} />{change}</span>}
      </div>
    </article>
  )
}

const riskClass = (risk: RiskLevel) => (risk === 'Low' ? 'risk-low' : risk === 'Medium' ? 'risk-moderate' : risk === 'High' ? 'risk-high' : 'risk-neutral')
export function RiskPill({ risk }: { risk: RiskLevel | null | undefined }) {
  if (!risk) return <span className="pill risk-neutral"><i />—</span>
  return <span className={`pill ${riskClass(risk)}`}><i />{risk}</span>
}

export function Avatar({ name, id, large = false }: { name: string; id: string; large?: boolean }) {
  return <span className={`avatar ${avatarTone(id)} ${large ? 'large' : ''}`} aria-hidden="true">{initials(name)}</span>
}

export function Meter({ value, color, wide = false, label }: { value: number; color: string; wide?: boolean; label: string }) {
  return (
    <div className={`meter ${wide ? 'wide' : ''}`} role="img" aria-label={`${label}: ${Math.round(value)} out of 100`}>
      <i style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  )
}

export function ScoreCell({ score, complete = true }: { score: number | null; complete?: boolean }) {
  const tone = scoreTone(score)
  return (
    <span className="score" title={tone.label}>
      <span className="score-value" style={{ color: score === null ? 'var(--faint)' : undefined }}>
        {score ?? '—'}<small>/100</small>
      </span>
      {score !== null && <Meter value={score} color={tone.color} label="Success score" />}
      {!complete && <span className="incomplete-dot" title="Some indicators are missing for this student" />}
    </span>
  )
}

export function EmptyState({ title, body, icon }: { title: string; body: string; icon?: ReactNode }) {
  return <div className="empty-state">{icon ?? <Info size={22} />}<strong>{title}</strong><span>{body}</span></div>
}

export function Trend({ positive = true, text }: { positive?: boolean; text: string }) {
  const Icon = positive ? ArrowUpRight : ArrowDownRight
  return <span className="metric-change" style={{ color: positive ? 'var(--green)' : 'var(--red)' }}><Icon size={14} />{text}</span>
}

/** Closes on Escape — shared by the drawer and the search popover. */
export function useEscape(handler: () => void, active = true) {
  useEffect(() => {
    if (!active) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') handler() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handler, active])
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return <div className="loading-state" role="status"><span className="spinner" aria-hidden="true" />{label}</div>
}

/** Standard wrapper: shows loading / error (with retry) / content. */
export function Async({ loading, error, onRetry, children }: { loading: boolean; error: string | null; onRetry?: () => void; children: ReactNode }) {
  if (error) return <Notice tone="error">{error}{onRetry && <> <button className="text-button" onClick={onRetry}>Try again</button></>}</Notice>
  if (loading) return <Loading />
  return <>{children}</>
}
