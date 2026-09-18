import { useEffect, useRef } from 'react'
import { animate, scrambleText } from 'animejs'
import type { Mode } from '../api'

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const CAPTION: Record<Mode, string> = {
  LOG_ONLY: 'Denials are recorded, not blocked',
  ENFORCE: 'Denials block the call',
}

const OPPOSITE: Record<Mode, Mode> = {
  LOG_ONLY: 'ENFORCE',
  ENFORCE: 'LOG_ONLY',
}

type Props = {
  mode: Mode | null
  /** Flips to the opposite mode. Disabled (and a no-op) while pending or unread. */
  onToggle: () => void
  pending: boolean
}

/**
 * The control the demo turns on. Kept on screen at all times so the flip is
 * legible in a recording, and now a real button rather than a read-only
 * status: clicking it calls the gateway's own /mode endpoint directly (see
 * api.ts) — never through the agent or the model, since the whole point of
 * Cell-Guard is that enforcement is not something the model has a say in.
 * The mode shown still comes back from the gateway's own response after
 * every flip and every chat request, so this never just assumes success.
 */
export default function ModeBadge({ mode, onToggle, pending }: Props) {
  const label = useRef<HTMLSpanElement>(null)
  const previous = useRef<Mode | null>(null)

  useEffect(() => {
    const changed = mode !== null && previous.current !== null && previous.current !== mode
    previous.current = mode
    if (!changed || !label.current || prefersReducedMotion()) return

    animate(label.current, {
      innerHTML: scrambleText({ text: mode as string, chars: 'uppercase', duration: 560 }),
    })
  }, [mode])

  const value = pending ? 'Flipping…' : (mode ?? 'Mode unread')
  const caption = pending ? 'Updating the gateway…' : mode ? CAPTION[mode] : 'Reading current mode…'
  const nextMode = mode ? OPPOSITE[mode] : null

  return (
    <button
      type="button"
      className="mode-chip"
      data-mode={pending ? 'pending' : (mode ?? 'unread')}
      onClick={onToggle}
      disabled={pending || mode === null}
      aria-label={nextMode ? `Switch gateway to ${nextMode} mode` : 'Gateway mode'}
    >
      <span className="mode-chip-value" ref={label} aria-live="polite">
        {value}
      </span>
      <span className="mode-chip-caption">{caption}</span>
    </button>
  )
}
