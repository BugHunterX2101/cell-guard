import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import GatewayPipeline from './components/GatewayPipeline'
import VerdictCard from './components/VerdictCard'
import ModeBadge from './components/ModeBadge'
import AuditTrail, { type AuditEntry } from './components/AuditTrail'
import { SCENARIOS, type Scenario } from './scenarios'
import { sendChat, TOOL_LABELS, type Mode, type ToolAttempt } from './api'

type Message = {
  id: string
  role: 'user' | 'assistant'
  text: string
  attempts?: ToolAttempt[]
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export default function App() {
  const composer = useRef<HTMLTextAreaElement>(null)
  const conversation = useRef<HTMLDivElement>(null)

  const [runId, setRunId] = useState(0)
  const sessionId = useMemo(() => crypto.randomUUID(), [runId])
  const [message, setMessage] = useState(SCENARIOS[0].message)
  const [note, setNote] = useState('')
  const [activeScenario, setActiveScenario] = useState<string>(SCENARIOS[0].id)
  const [messages, setMessages] = useState<Message[]>([])
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [mode, setMode] = useState<Mode | null>(null)
  const [pendingTool, setPendingTool] = useState<string>('a tool')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  /**
   * Keep the newest verdict card fully in view. A verdict card is much taller
   * than the message that introduces it, and its height is not final on the
   * commit that adds it, so scrolling on that commit lands short and leaves the
   * card below the fold. Watching the content box instead scrolls once the real
   * height exists — including after the diagram and web fonts settle.
   */
  useEffect(() => {
    const feed = conversation.current
    if (!feed || typeof ResizeObserver === 'undefined') return

    const pinToBottom = () =>
      feed.scrollTo({ top: feed.scrollHeight, behavior: prefersReducedMotion() ? 'auto' : 'smooth' })

    const observer = new ResizeObserver(() => {
      const distanceFromBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight
      if (distanceFromBottom < feed.clientHeight) pinToBottom()
    })

    for (const child of feed.children) observer.observe(child)
    pinToBottom()
    return () => observer.disconnect()
  }, [messages, busy])

  function applyScenario(scenario: Scenario) {
    setActiveScenario(scenario.id)
    setMessage(scenario.message)
    setNote(scenario.note)
    setPendingTool(TOOL_LABELS[scenario.tool])
    setError('')
    composer.current?.focus()
  }

  function resetRun() {
    setMessages([])
    setEntries([])
    setError('')
    setRunId((n) => n + 1)
    applyScenario(SCENARIOS[0])
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (busy) return

    const text = message.trim()
    if (!text) {
      setError('Write a request for the assistant before sending.')
      composer.current?.focus()
      return
    }

    setError('')
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', text }])
    setBusy(true)

    try {
      const result = await sendChat(text, note.trim(), sessionId)
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', text: result.message, attempts: result.tool_attempts },
      ])

      if (result.tool_attempts.length > 0) {
        const at = new Date()
        setEntries((current) => [
          ...result.tool_attempts
            .map((attempt, index) => ({
              ...attempt,
              id: crypto.randomUUID(),
              seq: current.length + result.tool_attempts.length - index,
              at,
            }))
            .reverse(),
          ...current,
        ])
        setMode(result.tool_attempts[result.tool_attempts.length - 1].mode)
      }
      setMessage('')
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The request did not reach the agent. Check the API URL, then send it again.',
      )
    } finally {
      setBusy(false)
    }
  }

  function onComposerKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <>
      <a className="skip-link" href="#console">Skip to the agent console</a>

      <div className="app">
        <header className="toolbar">
          <span className="wordmark" translate="no">CELL·GUARD</span>
          <h1 className="claim">
            Cedar policy checks every tool call before it runs — the model can’t talk past it.
          </h1>
          <ModeBadge mode={mode} />
        </header>

        <div className="workspace">
          <aside className="rig">
            <div className="panel-bar">
              <h2>Scenario</h2>
            </div>

            <ul className="scenarios">
              {SCENARIOS.map((scenario) => (
                <li key={scenario.id}>
                  <button
                    type="button"
                    className="scenario"
                    data-hostile={scenario.hostile}
                    aria-pressed={activeScenario === scenario.id}
                    onClick={() => applyScenario(scenario)}
                  >
                    <span className="scenario-label">{scenario.label}</span>
                    <span className="scenario-rule">{scenario.rule}</span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="note-field">
              <div className="panel-bar">
                <label htmlFor="customer-note">Customer note</label>
                <span className="tag" translate="no">injected_doc</span>
              </div>
              <textarea
                id="customer-note"
                name="customer-note"
                value={note}
                autoComplete="off"
                spellCheck={false}
                onChange={(event) => {
                  setNote(event.target.value)
                  setActiveScenario('')
                }}
                placeholder="Paste a customer note for the assistant to process…"
              />
            </div>
          </aside>

          <section id="console" className="console" aria-labelledby="console-title">
            <div className="panel-bar">
              <h2 id="console-title">Finance operations assistant</h2>
              <button type="button" className="ghost-button" onClick={resetRun} disabled={busy}>
                Reset run
              </button>
            </div>

            <div className="feed" ref={conversation} aria-busy={busy}>
              {messages.length === 0 && (
                <p className="feed-empty">
                  Pick a scenario, then send it. The gateway’s decision appears here.
                </p>
              )}

              {messages.map((item) => (
                <article key={item.id} className={`bubble ${item.role}`}>
                  <p className="bubble-who">{item.role === 'user' ? 'You' : 'Assistant'}</p>
                  <p className="bubble-text">{item.text}</p>
                  {item.attempts?.map((attempt, index) => (
                    <VerdictCard key={`${item.id}-${index}`} attempt={attempt} />
                  ))}
                </article>
              ))}

              {busy && (
                <article className="bubble assistant">
                  <p className="bubble-who">Assistant</p>
                  <p className="bubble-text">Posting the tool call to the gateway…</p>
                  <div className="pending-stage">
                    <GatewayPipeline toolLabel={pendingTool} />
                  </div>
                </article>
              )}
            </div>

            <div aria-live="polite" className="sr-only">
              {busy ? 'Checking the gateway.' : messages.at(-1)?.role === 'assistant' ? messages.at(-1)?.text : ''}
            </div>

            <form className="composer" onSubmit={onSubmit}>
              <label className="sr-only" htmlFor="message">Request for the assistant</label>
              <textarea
                id="message"
                name="message"
                ref={composer}
                rows={2}
                value={message}
                autoComplete="off"
                onKeyDown={onComposerKeyDown}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Ask the assistant to take an action…"
              />
              <button type="submit" disabled={busy}>
                {busy ? 'Checking…' : 'Send request'}
                <kbd translate="no">⌘↵</kbd>
              </button>
            </form>

            {error && <p className="error" role="alert">{error}</p>}
          </section>
        </div>

        <AuditTrail entries={entries} sessionId={sessionId} />
      </div>
    </>
  )
}
