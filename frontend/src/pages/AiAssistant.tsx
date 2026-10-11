import { useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AlertCircle, Bot, Database, RotateCcw, Send, ShieldCheck, Sparkles, UserRound } from 'lucide-react'
import { write } from '../lib/api'
import { PageHeading } from '../components/Primitives'


type Turn = { id: string; role: 'user' | 'assistant'; text: string; error?: boolean }
type ChatResponse = { answer: string; model: string; context_scope: string; privacy: string }
const STARTERS = [
  'Summarize student success across the campus.',
  'Which departments have the lowest average attendance?',
  'How many students have high academic or placement risk?',
  'What patterns should we focus on to improve placement readiness?',
]

export default function AiAssistant() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const userQuestions = useMemo(() => turns.filter(t => t.role === 'user').map(t => t.text), [turns])

  const ask = async (text: string) => {
    const clean = text.trim()
    if (!clean || busy) return
    const previousHistory = userQuestions.slice(-4)
    setQuestion('')
    setNotice('')
    setBusy(true)
    setTurns(current => [...current, { id: `${Date.now()}-user`, role: 'user', text: clean }])
    try {
      const result = await write<ChatResponse>('POST', '/api/ai/chat', { message: clean, history: previousHistory })
      setTurns(current => [...current, { id: `${Date.now()}-assistant`, role: 'assistant', text: result.answer }])
      setNotice(`Answered using ${result.context_scope}.`)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'The assistant could not answer this question.'
      setTurns(current => [...current, { id: `${Date.now()}-error`, role: 'assistant', text: message, error: true }])
    } finally {
      setBusy(false)
      window.setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }), 40)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void ask(question)
  }
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void ask(question)
    }
  }

  return (
    <div className="ai-assistant-page">
      <PageHeading title="AI data assistant" description="Ask questions in plain language. Answers use the student datasets currently loaded by this workspace." />

      <div className="ai-assistant-layout">
        <section className="ai-chat-panel" aria-label="Chat with campus data assistant">
          <header className="ai-chat-header">
            <div className="ai-bot-mark"><Sparkles size={21} /></div>
            <div className="ai-chat-title"><strong>Academia AI</strong><span><i /> Connected to campus data</span></div>
            <button className="button button-secondary ai-clear" onClick={() => { setTurns([]); setNotice(''); setQuestion('') }} disabled={busy || turns.length === 0} title="Clear conversation"><RotateCcw size={15} /> Clear</button>
          </header>

          <div className="ai-chat-scroll">
            {turns.length === 0 ? (
              <div className="ai-welcome">
                <div className="ai-welcome-icon"><Bot size={28} /></div>
                <h2>What would you like to understand?</h2>
                <p>Ask about attendance, academic performance, student success, risk indicators, departments, or placement readiness.</p>
                <div className="ai-prompt-grid">
                  {STARTERS.map(prompt => <button key={prompt} className="ai-prompt" onClick={() => void ask(prompt)} disabled={busy}><span>{prompt}</span><Send size={14} /></button>)}
                </div>
              </div>
            ) : (
              <div className="ai-turn-list">
                {turns.map(turn => (
                  <article className={`ai-turn ai-turn-${turn.role} ${turn.error ? 'ai-turn-error' : ''}`} key={turn.id}>
                    <div className="ai-turn-avatar">{turn.role === 'user' ? <UserRound size={17} /> : turn.error ? <AlertCircle size={17} /> : <Sparkles size={17} />}</div>
                    <div className="ai-turn-body">
                      <strong>{turn.role === 'user' ? 'You' : turn.error ? 'Could not answer' : 'Academia AI'}</strong>
                      <p>{turn.text}</p>
                    </div>
                  </article>
                ))}
                {busy && <article className="ai-turn ai-turn-assistant"><div className="ai-turn-avatar"><Sparkles size={17} /></div><div className="ai-turn-body"><strong>Academia AI</strong><p className="ai-thinking"><span /><span /><span /> Reading the available data…</p></div></article>}
                <div ref={endRef} />
              </div>
            )}
          </div>

          {notice && <div className="ai-context-note"><Database size={14} />{notice}</div>}
          <form className="ai-composer" onSubmit={submit}>
            <label className="sr-only" htmlFor="ai-question">Ask a question about the student datasets</label>
            <textarea id="ai-question" value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={handleKeyDown} placeholder="Ask a question about your campus data…" rows={2} maxLength={2000} disabled={busy} />
            <div className="ai-composer-footer"><span>Enter to send · Shift + Enter for a new line</span><span>{question.length}/2000</span><button type="submit" className="button button-primary" disabled={busy || !question.trim()}><Send size={16} />{busy ? 'Thinking…' : 'Ask AI'}</button></div>
          </form>
        </section>

        <aside className="ai-info-column">
          <section className="ai-info-card"><div className="ai-info-icon"><Database size={18} /></div><h3>Grounded in your datasets</h3><p>The assistant uses loaded CSV data and calculated dashboard metrics. If a value is missing, it should say so instead of guessing.</p></section>
          <section className="ai-info-card"><div className="ai-info-icon"><ShieldCheck size={18} /></div><h3>Privacy-aware by design</h3><p>Names, student IDs and emails are removed from dataset context before it is sent to Groq. Authorized staff labels are restored locally.</p></section>
          <section className="ai-info-disclaimer"><strong>Use AI as an assistant, not a decision-maker</strong><p>Answers can be imperfect. Verify important numbers in the dashboard or CSV files. Risk indicators are rule-based support prompts, not probabilities or final decisions.</p></section>
        </aside>
      </div>
    </div>
  )
}
