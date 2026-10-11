import { useState, type FormEvent } from 'react'
import { LockKeyhole } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { errorMessage } from '../lib/hooks'
import { Notice } from '../components/Primitives'

export default function Login() {
  const { signIn } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try { await signIn(username, password) } catch (err) { setError(errorMessage(err)); setBusy(false) }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <img src="/academia-mark.png" alt="" width={40} height={40} />
          <div><strong>Academia</strong><span>Campus Intelligence</span></div>
        </div>
        <h1>Sign in</h1>
        <p>Use your staff account to view student success analytics.</p>
        {error && <Notice tone="error">{error}</Notice>}
        <div className="stack">
          <label className="form-field">Username
            <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" autoFocus required />
          </label>
          <label className="form-field">Password
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          <button className="button button-primary" type="submit" disabled={busy || !username || !password}>
            <LockKeyhole size={16} />{busy ? 'Signing in…' : 'Sign in'}
          </button>
        </div>
      </form>
    </div>
  )
}
