export const HOUR = 60 * 60 * 1000
export const TIMELINE_HOURS = 24
const THRESHOLD = 80

/**
 * Split one room's readings into hourly buckets ending at `end`.
 * Each bucket holds the mean and peak humidity, or null when no valid readings exist.
 */
export function hourlyBuckets(readings, end, hours = TIMELINE_HOURS) {
  const buckets = Array.from({ length: hours }, () => [])
  for (const reading of readings) {
    const rh = Number(reading.rh)
    if (!Number.isFinite(rh)) continue
    const age = end - new Date(reading.timestamp).getTime()
    const index = hours - 1 - Math.floor(age / HOUR)
    if (index >= 0 && index < hours) buckets[index].push(rh)
  }
  return buckets.map((values) => (values.length
    ? { mean: values.reduce((sum, value) => sum + value, 0) / values.length, peak: Math.max(...values) }
    : null))
}

/** Merge consecutive hours whose mean humidity is at or above 80% into blocks. */
export function humidBlocks(buckets) {
  const blocks = []
  buckets.forEach((bucket, index) => {
    if (!bucket || bucket.mean < THRESHOLD) return
    const last = blocks.at(-1)
    if (last && last.end === index - 1) {
      last.end = index
      last.peak = Math.max(last.peak, bucket.peak)
    } else {
      blocks.push({ start: index, end: index, peak: bucket.peak })
    }
  })
  return blocks
}
