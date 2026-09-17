import { useEffect, useRef } from 'react'
import { animate, createScope, createTimeline, stagger, svg } from 'animejs'
import type { Verdict } from '../api'

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

type Props = {
  /** Omitted while the gateway round trip is still in flight. */
  verdict?: Verdict
  toolLabel: string
}

const RAIL_Y = 36
const RAIL_A = { x1: 84, x2: 292 }
const RAIL_B = { x1: 328, x2: 536 }

/**
 * The one authored moment in this interface: a tool call leaving the agent,
 * reaching the gateway, and either continuing to the tool or being cut there.
 *
 * Three end states, drawn differently on purpose:
 *   permitted  — both rails black, tool node filled.
 *   blocked    — second rail is a dashed ghost, severed at the gateway.
 *   unenforced — second rail is drawn in red: Cedar said no, the call went anyway.
 *
 * Node labels live in HTML rather than inside the SVG so they stay at a real
 * type size when the diagram scales down on a phone.
 */
export default function GatewayPipeline({ verdict, toolLabel }: Props) {
  const root = useRef<HTMLDivElement>(null)
  const scope = useRef<ReturnType<typeof createScope> | null>(null)

  useEffect(() => {
    if (!root.current || prefersReducedMotion()) return

    scope.current = createScope({ root: root.current }).add(() => {
      if (!verdict) {
        animate('.cg-packet', {
          x: [RAIL_A.x1, RAIL_A.x2],
          opacity: [
            { to: 1, duration: 120 },
            { to: 1, duration: 700 },
            { to: 0, duration: 180 },
          ],
          duration: 1000,
          loop: true,
          ease: 'inOutQuad',
        })
        animate('.cg-node[data-node="gateway"]', {
          opacity: [1, 0.45, 1],
          duration: 1000,
          loop: true,
          ease: 'inOutSine',
        })
        return
      }

      const timeline = createTimeline({ defaults: { ease: 'outExpo' } })

      // Every resting state below is already correct in CSS; the timeline only
      // transitions into it. Nothing here animates from invisible, so a stalled
      // frame loop degrades to an un-animated diagram rather than a blank one.
      timeline
        .add('.cg-node', { scale: [0.88, 1], duration: 200 }, stagger(45))
        .add(svg.createDrawable('.cg-rail-a'), { draw: ['0 0', '0 1'], duration: 340 }, 120)
        .add('.cg-node[data-node="gateway"]', { scale: [1, 1.12, 1], duration: 300 }, '-=110')
        .add('.cg-gate-fill', { opacity: [0, 1], duration: 200 }, '<<+=70')

      if (verdict === 'blocked') {
        timeline
          .add('.cg-break line', { opacity: [0, 1], scaleY: [0.3, 1], duration: 220 }, '-=50')
          .add('.cg-ghost', { opacity: [0, 1], duration: 280 }, '<<+=60')
      } else {
        timeline
          .add(svg.createDrawable('.cg-rail-b'), { draw: ['0 0', '0 1'], duration: 340 }, '-=90')
          .add('.cg-tool-fill', { opacity: [0, 1], duration: 200 }, '-=130')
      }
    })

    return () => scope.current?.revert()
  }, [verdict])

  const state = verdict ?? 'pending'
  const description =
    verdict === 'blocked'
      ? `Diagram: the call to ${toolLabel} is stopped at the gateway and never reaches the tool.`
      : verdict === 'unenforced'
        ? `Diagram: the call to ${toolLabel} is denied by policy but still reaches the tool.`
        : verdict === 'permitted'
          ? `Diagram: the call to ${toolLabel} passes the gateway and reaches the tool.`
          : `Diagram: a call to ${toolLabel} is on its way to the gateway.`

  return (
    <div className="cg-pipeline" data-state={state} ref={root}>
      <svg viewBox="0 0 620 72" role="img" aria-label={description} preserveAspectRatio="xMidYMid meet">
        <line className="cg-rail cg-rail-a" x1={RAIL_A.x1} y1={RAIL_Y} x2={RAIL_A.x2} y2={RAIL_Y} />

        {verdict === 'blocked' ? (
          <line className="cg-rail cg-ghost" x1={RAIL_B.x1} y1={RAIL_Y} x2={RAIL_B.x2} y2={RAIL_Y} />
        ) : (
          <line className="cg-rail cg-rail-b" x1={RAIL_B.x1} y1={RAIL_Y} x2={RAIL_B.x2} y2={RAIL_Y} />
        )}

        {!verdict && <rect className="cg-packet" x={-5} y={RAIL_Y - 5} width="10" height="10" />}

        {verdict === 'blocked' && (
          <g className="cg-break" aria-hidden="true">
            <line x1="336" y1="18" x2="348" y2="54" />
            <line x1="346" y1="18" x2="358" y2="54" />
          </g>
        )}

        <g className="cg-node" data-node="agent">
          <rect className="cg-edge" x="48" y="18" width="36" height="36" />
        </g>

        <g className="cg-node" data-node="gateway">
          <rect className="cg-gate-fill" x="292" y="18" width="36" height="36" />
          <rect className="cg-edge" x="292" y="18" width="36" height="36" />
        </g>

        <g className="cg-node" data-node="tool">
          <rect className="cg-tool-fill" x="536" y="18" width="36" height="36" />
          <rect className="cg-edge" x="536" y="18" width="36" height="36" />
        </g>
      </svg>

      <p className="cg-labels" aria-hidden="true">
        <span style={{ left: '10.6%' }}>Agent</span>
        <span style={{ left: '50%' }}>Gateway</span>
        <span style={{ left: '89.4%' }}>Tool</span>
      </p>
    </div>
  )
}
