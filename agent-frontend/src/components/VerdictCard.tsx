import GatewayPipeline from './GatewayPipeline'
import { VERDICT_COPY, verdictOf, type ToolAttempt } from '../api'

const formatParams = (params: Record<string, string | number>) =>
  Object.entries(params)
    .map(([key, value]) => `${key}=${typeof value === 'number' ? value.toLocaleString('en-US') : value}`)
    .join('  ')

/**
 * The gateway appends a "[LOG_ONLY mode: not blocked]" marker to the reason in
 * log-only mode. The card already says Unenforced and shows the mode, so the
 * marker would be a third statement of the same fact.
 */
const trimReason = (reason: string) => reason.replace(/\s*\[LOG_ONLY mode: not blocked\]\s*$/, '')

export default function VerdictCard({ attempt }: { attempt: ToolAttempt }) {
  const verdict = verdictOf(attempt)
  const reason = trimReason(attempt.reason)

  return (
    <section className="verdict-card" data-verdict={verdict} aria-label={`${VERDICT_COPY[verdict]}: ${attempt.tool}`}>
      <div className="verdict-stage">
        <GatewayPipeline verdict={verdict} toolLabel={attempt.tool} />
      </div>

      <div className="verdict-strip">
        <span className="verdict-word">{VERDICT_COPY[verdict]}</span>
        <code className="verdict-call" translate="no">
          {attempt.tool} {formatParams(attempt.params)}
        </code>
        <span className="verdict-mode" translate="no">{attempt.mode}</span>
      </div>

      <p className="verdict-reason">{reason}</p>
    </section>
  )
}
