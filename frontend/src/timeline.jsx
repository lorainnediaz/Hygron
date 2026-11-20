import { HOUR, TIMELINE_HOURS, hourlyBuckets, humidBlocks } from './timelineData'

function hourLabel(time) {
  return new Date(time).toLocaleTimeString([], { hour: 'numeric' })
}

export function RoomTimeline({ rooms, historyByRoom, selectedRoom, onSelect, riskStyles, staffActions, rowLabel }) {
  let latest = 0
  for (const readings of Object.values(historyByRoom)) {
    for (const reading of readings) latest = Math.max(latest, new Date(reading.timestamp).getTime())
  }
  // Round up to the end of the latest hour so the last column is the current hour.
  const end = latest ? Math.ceil((latest + 1) / HOUR) * HOUR : 0

  if (!end) return <div className="empty-state">No humidity readings to show yet.</div>

  const columns = Array.from({ length: TIMELINE_HOURS }, (_, index) => end - (TIMELINE_HOURS - index) * HOUR)

  return (
    <div className="timeline" style={{ '--cols': TIMELINE_HOURS }}>
      <div className="timeline-row timeline-head" aria-hidden="true">
        <span className="timeline-corner">Rooms</span>
        <div className="timeline-track">
          {columns.map((time, index) => (
            <span key={time} className={index === TIMELINE_HOURS - 1 ? 'timeline-hour is-now' : 'timeline-hour'}>
              {index === TIMELINE_HOURS - 1 ? 'Now' : hourLabel(time)}
            </span>
          ))}
        </div>
      </div>

      {rooms.map((room) => {
        const buckets = hourlyBuckets(historyByRoom[room.room_id] || [], end)
        const blocks = humidBlocks(buckets)
        const humidHours = blocks.reduce((sum, block) => sum + block.end - block.start + 1, 0)
        const style = riskStyles[room.current_risk] || riskStyles.Unavailable
        const Icon = style.icon
        const action = staffActions[room.current_risk] || staffActions.Unavailable
        return (
          <div className="timeline-row" key={room.room_id}>
            <button
              type="button"
              className={selectedRoom === room.room_id ? 'timeline-room selected' : 'timeline-room'}
              style={{ '--risk': style.color }}
              aria-pressed={selectedRoom === room.room_id}
              aria-label={rowLabel(room)}
              onClick={() => onSelect(room.room_id)}
            >
              <span className="timeline-room-icon" aria-hidden="true"><Icon size={16} /></span>
              <span className="timeline-room-text">
                <strong>{room.room_name}</strong>
                <small><span>{room.current_risk}</span> risk, <span>{action}</span></small>
              </span>
            </button>
            <div className="timeline-track">
              <p className="sr-only">
                {room.room_name}: humidity at or above 80% for {humidHours} of the last {TIMELINE_HOURS} hours.
              </p>
              {buckets.map((bucket, index) => (
                <span
                  key={columns[index]}
                  aria-hidden="true"
                  className={`timeline-cell${bucket ? '' : ' no-data'}${index === TIMELINE_HOURS - 1 ? ' is-now' : ''}`}
                  style={{ gridColumn: index + 1 }}
                />
              ))}
              {blocks.map((block) => (
                <span
                  key={block.start}
                  aria-hidden="true"
                  className="timeline-block"
                  style={{ gridColumn: `${block.start + 1} / ${block.end + 2}` }}
                  title={`At or above 80% RH, peak ${block.peak.toFixed(0)}%`}
                >
                  {block.end - block.start >= 2 && (
                    <>
                      <strong>Above 80% RH</strong>
                      <em>Peak {block.peak.toFixed(0)}%</em>
                    </>
                  )}
                </span>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
