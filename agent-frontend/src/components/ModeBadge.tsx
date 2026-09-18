import { useEffect, useRef } from 'react'
import { animate, scrambleText } from 'animejs'
import type { Mode } from '../api'

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const CAPTION: Record<Mode, string> = {
  LOG_ONLY: 'Denials are recorded, not blocked',
  ENFORCE: 'Denials block the call',
}

/**
 * The state the demo turns on, kept on screen at all times so the LOG_ONLY →
 * ENFORCE flip is legible in a recording. The mode is read back from the
 * gateway's own response, so it reflects what actually decided the last call
 * rather than anything this UI assumes.
 */
export default function ModeBadge({ mode }: { mode: Mode | null }) {
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

  return (
    <div className="mode-chip" data-mode={mode ?? 'unread'}>
      <span className="mode-chip-value" ref={label} aria-live="polite">
        {mode ?? 'Mode unread'}
      </span>
      <span className="mode-chip-caption">
        {mode ? CAPTION[mode] : 'Send a request to read it'}
      </span>
    </div>
  )
}
