import { useEffect, useRef, useState } from 'react'
import { animate, useReducedMotion } from 'motion/react'

/**
 * Counts up to `value`. Screen readers get only the final number; the moving
 * digits are hidden from them. Shows the number directly when reduced motion is on.
 */
export function CountUp({ value }) {
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    if (reduce) return undefined
    const controls = animate(from.current, value, {
      duration: 0.8,
      ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (latest) => setShown(Math.round(latest)),
    })
    from.current = value
    return () => controls.stop()
  }, [value, reduce])

  if (reduce) return value
  return (
    <>
      <span aria-hidden="true">{shown}</span>
      <span className="sr-only">{value}</span>
    </>
  )
}

/** One bar split by risk level in proportion to the room counts. */
export function RiskBar({ counts, order }) {
  const total = order.reduce((sum, risk) => sum + (counts[risk] || 0), 0)
  const label = `Risk distribution: ${order.map((risk) => `${counts[risk] || 0} ${risk}`).join(', ')}`
  return (
    <div className="risk-bar" role="img" aria-label={label}>
      {total === 0
        ? <span className="risk-bar-segment empty" />
        : order.filter((risk) => counts[risk]).map((risk) => (
          <span key={risk} className={`risk-bar-segment ${risk.toLowerCase()}`} style={{ flexGrow: counts[risk] }} />
        ))}
    </div>
  )
}

/** Humidity on a 0 to 100% track with a marker at the 80% reference. */
export function HumidityBar({ rh }) {
  if (rh == null) return null
  const value = Math.max(0, Math.min(100, Number(rh)))
  const above = value >= 80
  return (
    <div className="rh-bar">
      <div className="rh-bar-track" aria-hidden="true">
        <span className={above ? 'rh-bar-fill above' : 'rh-bar-fill'} style={{ width: `${value}%` }} />
        <span className="rh-bar-marker" />
      </div>
      <span className="rh-bar-caption">{above ? 'At or above' : 'Below'} the 80% reference</span>
    </div>
  )
}
