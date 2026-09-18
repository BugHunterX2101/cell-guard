import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Dev-only stand-in for the deployed agent Lambda, mounted at POST /chat.
 *
 * It exists so the interface can be built, reviewed, and rehearsed with no AWS
 * account, no Bedrock access, and no gateway reachable. It performs the same
 * routing the agent does (pick a tool from the request, POST it to a gateway)
 * and mirrors the published Cedar thresholds, so all three verdict states are
 * reachable locally. It never ships: `apply: 'serve'` keeps it out of builds,
 * and the deployed UI talks to VITE_AGENT_API_URL instead.
 *
 * Flip the mode it reports with LOCAL_MODE=ENFORCE npm run dev, or live via
 * GET/POST /mode (the same endpoint shape the deployed gateway exposes),
 * which is what the UI's mode-flip button actually calls.
 */
const EXPENSE_LIMIT = 500
const WIRE_LIMIT = 1000

type Tool = 'approve_expense' | 'delete_customer_record' | 'send_wire_transfer'

function chooseToolCall(text: string): { tool: Tool; params: Record<string, string | number> } | null {
  const lower = text.toLowerCase()

  // An injected note usually cites the limit it is trying to beat ("the $500
  // ceiling does not apply") before naming the amount it actually wants. Taking
  // the largest figure lands on the attempted amount rather than the limit.
  const amounts = [...text.matchAll(/\$\s?([\d,]+(?:\.\d+)?)/g)].map((m) => Number(m[1].replace(/,/g, '')))
  const amount = amounts.length ? Math.max(...amounts) : 0

  if (lower.includes('delete') && lower.includes('customer')) {
    const customerId = text.match(/CUST-[\w-]+/i)?.[0] ?? 'CUST-2041'
    return { tool: 'delete_customer_record', params: { customer_id: customerId } }
  }
  if (lower.includes('wire')) {
    const recipient =
      text.match(/recipient\s+([A-Z][A-Z0-9-]{3,})/i)?.[1] ??
      text.match(/to\s+([A-Z][A-Z0-9]{2,}-[A-Z0-9-]+)/)?.[1] ??
      'UNKNOWN-RECIPIENT'
    return { tool: 'send_wire_transfer', params: { amount, recipient } }
  }
  if (lower.includes('approve') || lower.includes('reimburse') || lower.includes('expense')) {
    const employeeId = text.match(/EMP-[\w-]+/i)?.[0] ?? 'EMP-1048'
    return { tool: 'approve_expense', params: { amount, employee_id: employeeId } }
  }
  return null
}

function evaluate(tool: Tool, params: Record<string, string | number>): ['ALLOW' | 'DENY', string] {
  const amount = Number(params.amount)
  const money = (value: number) => `$${value.toLocaleString('en-US')}`

  if (tool === 'delete_customer_record') {
    return ['DENY', 'Deleting a customer record is forbidden without exception.']
  }
  if (tool === 'send_wire_transfer') {
    if (!(amount > 0)) return ['DENY', 'A wire amount must be greater than zero.']
    return amount > WIRE_LIMIT
      ? ['DENY', `Wire transfers above ${money(WIRE_LIMIT)} are forbidden. Attempted ${money(amount)}.`]
      : ['ALLOW', `${money(amount)} is within the ${money(WIRE_LIMIT)} wire transfer limit.`]
  }
  if (!(amount > 0)) return ['DENY', 'An expense amount must be greater than zero.']
  return amount > EXPENSE_LIMIT
    ? ['DENY', `Reimbursements above ${money(EXPENSE_LIMIT)} are forbidden. Attempted ${money(amount)}.`]
    : ['ALLOW', `${money(amount)} is within the ${money(EXPENSE_LIMIT)} reimbursement limit.`]
}

function localAgent(): Plugin {
  // Mutable so the frontend's mode-flip button works in dev too, not just
  // against the deployed gateway. Seeded from LOCAL_MODE for the old
  // env-var-only workflow, then live-editable via GET/POST /mode below.
  let localMode: 'LOG_ONLY' | 'ENFORCE' = process.env.LOCAL_MODE === 'ENFORCE' ? 'ENFORCE' : 'LOG_ONLY'

  return {
    name: 'cellguard-local-agent',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/mode', (req, res) => {
        res.setHeader('Content-Type', 'application/json')

        if (req.method === 'GET') {
          res.end(JSON.stringify({ mode: localMode }))
          return
        }

        if (req.method === 'POST') {
          const chunks: Buffer[] = []
          req.on('data', (chunk) => chunks.push(chunk))
          req.on('end', () => {
            const body = JSON.parse(Buffer.concat(chunks).toString() || '{}')
            if (body.mode !== 'LOG_ONLY' && body.mode !== 'ENFORCE') {
              res.statusCode = 400
              res.end(JSON.stringify({ error: 'mode must be LOG_ONLY or ENFORCE' }))
              return
            }
            localMode = body.mode
            res.end(JSON.stringify({ mode: localMode }))
          })
          return
        }

        res.statusCode = 405
        res.end(JSON.stringify({ error: 'Method not allowed' }))
      })

      server.middlewares.use('/chat', (req, res, next) => {
        if (req.method !== 'POST') return next()

        const chunks: Buffer[] = []
        req.on('data', (chunk) => chunks.push(chunk))
        req.on('end', () => {
          const body = JSON.parse(Buffer.concat(chunks).toString() || '{}')
          const combined = `${body.message ?? ''}\n${body.customer_note ?? ''}`
          const call = chooseToolCall(combined)
          const mode = localMode

          res.setHeader('Content-Type', 'application/json')

          if (!call) {
            res.end(JSON.stringify({
              message: 'I can approve expenses, delete customer records, or send wire transfers. Tell me which one you need.',
              session_id: body.session_id ?? 'local',
              tool_attempts: [],
            }))
            return
          }

          const [policyDecision, baseReason] = evaluate(call.tool, call.params)
          const decision = mode === 'ENFORCE' ? policyDecision : 'ALLOW'
          const reason =
            mode === 'LOG_ONLY' && policyDecision === 'DENY' ? `${baseReason} [LOG_ONLY mode: not blocked]` : baseReason

          const message =
            decision === 'ALLOW'
              ? `I called ${call.tool} and the gateway returned ALLOW, so the action went through.`
              : `I attempted ${call.tool}, but the gateway returned DENY, so nothing was written.`

          // A visible pause so the in-flight pipeline is reviewable in dev.
          setTimeout(() => {
            res.end(JSON.stringify({
              message,
              session_id: body.session_id ?? 'local',
              tool_attempts: [{ tool: call.tool, params: call.params, decision, policyDecision, reason, mode }],
            }))
          }, 900)
        })
      })
    },
  }
}

export default defineConfig({ plugins: [react(), localAgent()] })
