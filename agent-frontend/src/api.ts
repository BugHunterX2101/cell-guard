export type Decision = 'ALLOW' | 'DENY'
export type Mode = 'LOG_ONLY' | 'ENFORCE'
export type ToolName = 'approve_expense' | 'delete_customer_record' | 'send_wire_transfer'

export type ToolAttempt = {
  tool: ToolName
  params: Record<string, string | number>
  /** What actually happened to the call. */
  decision: Decision
  /** What Cedar decided, independent of the mode that was in force. */
  policyDecision: Decision
  reason: string
  mode: Mode
}

export type ChatResponse = {
  message: string
  session_id: string
  tool_attempts: ToolAttempt[]
}

/**
 * The three outcomes worth telling apart on screen. `unenforced` is the whole
 * point of LOG_ONLY: Cedar returned DENY and the tool ran regardless.
 */
export type Verdict = 'permitted' | 'blocked' | 'unenforced'

export function verdictOf(attempt: ToolAttempt): Verdict {
  if (attempt.policyDecision === 'DENY') {
    return attempt.decision === 'ALLOW' ? 'unenforced' : 'blocked'
  }
  return attempt.decision === 'ALLOW' ? 'permitted' : 'blocked'
}

/**
 * The verdict word already encodes both the Cedar decision and whether the tool
 * ran, so the card does not restate either: Permitted = allowed and ran,
 * Blocked = denied and stopped, Unenforced = denied but ran anyway. The audit
 * trail keeps the decision broken out for the record.
 */
export const VERDICT_COPY: Record<Verdict, string> = {
  permitted: 'Permitted',
  blocked: 'Blocked',
  unenforced: 'Unenforced — ran anyway',
}

export const TOOL_LABELS: Record<ToolName, string> = {
  approve_expense: 'Approve Expense',
  delete_customer_record: 'Delete Customer Record',
  send_wire_transfer: 'Send Wire Transfer',
}

const endpoint = import.meta.env.VITE_AGENT_API_URL || '/chat'

// The gateway's own /mode endpoint (see gateway-policy/template.yaml's
// ModeControlFunction) — a different origin than the agent chat endpoint
// above, called directly from the browser rather than through the agent, so
// flipping the mode is never something the model is in the loop for.
const modeEndpoint = import.meta.env.VITE_GATEWAY_MODE_URL || '/mode'

export async function getMode(signal?: AbortSignal): Promise<Mode> {
  const response = await fetch(modeEndpoint, { signal })
  if (!response.ok) throw new Error('Could not read the current mode.')
  const body = (await response.json()) as { mode: Mode }
  return body.mode
}

export async function setMode(mode: Mode, signal?: AbortSignal): Promise<Mode> {
  const response = await fetch(modeEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({ mode }),
  })
  if (!response.ok) throw new Error('Could not change the mode.')
  const body = (await response.json()) as { mode: Mode }
  return body.mode
}

export async function sendChat(
  message: string,
  customerNote: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      message,
      customer_note: customerNote || undefined,
      session_id: sessionId,
    }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      body.message || 'The agent could not reach Bedrock. Check model access, then send the request again.',
    )
  }
  return response.json() as Promise<ChatResponse>
}
