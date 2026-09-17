import { verdictOf, VERDICT_COPY, type ToolAttempt } from '../api'

export type AuditEntry = ToolAttempt & { id: string; seq: number; at: Date }

const timeFormat = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const formatParams = (params: Record<string, string | number>) =>
  Object.entries(params)
    .map(([key, value]) => `${key}=${typeof value === 'number' ? value.toLocaleString('en-US') : value}`)
    .join(' · ')

/**
 * Every attempt the session has made, decided or not. This is the view that
 * shows the same payload landing differently under each mode — the Cedar
 * column and the Executed column disagreeing is what LOG_ONLY looks like.
 */
export default function AuditTrail({ entries, sessionId }: { entries: AuditEntry[]; sessionId: string }) {
  return (
    <section className="audit" aria-labelledby="audit-title">
      <div className="panel-bar">
        <h2 id="audit-title">Audit trail</h2>
        <p className="audit-meta">
          <span>newest first</span>
          <span translate="no">session {sessionId.slice(0, 8)}</span>
          <span>
            {entries.length} {entries.length === 1 ? 'attempt' : 'attempts'}
          </span>
        </p>
      </div>

      {entries.length === 0 ? (
        <p className="audit-empty">Each attempt lands here with Cedar’s decision and whether the tool ran.</p>
      ) : (
        <div className="audit-scroll">
          <table className="audit-table">
            <caption className="sr-only">Tool call attempts for this session, newest first</caption>
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Tool</th>
                <th scope="col">Parameters</th>
                <th scope="col">Cedar</th>
                <th scope="col">Mode</th>
                <th scope="col">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const verdict = verdictOf(entry)
                return (
                  <tr key={entry.id} data-verdict={verdict}>
                    <td className="num">{timeFormat.format(entry.at)}</td>
                    <td className="mono">{entry.tool}</td>
                    <td className="mono">{formatParams(entry.params)}</td>
                    <td data-decision={entry.policyDecision}>{entry.policyDecision}</td>
                    <td>{entry.mode}</td>
                    <td className="outcome">{verdict === 'unenforced' ? 'Ran anyway' : VERDICT_COPY[verdict]}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
