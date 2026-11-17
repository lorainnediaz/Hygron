"""Self-contained, browser-animated circuit-board SVG for the simulated IoT path.

Physical wiring is drawn only between the virtual BME680 and ESP32 board.
Remaining links represent wireless/data-network signals, not copper wiring.
"""
from __future__ import annotations
from html import escape

# Source/target x coordinates of the arrows; the active path is highlighted during a step.
NODES = [
    ("sensor", "BME680 SENSOR", "Temp · RH · Gas", 36, 126),
    ("esp", "ESP32 NODE", "30-second packets", 270, 126),
    ("rpi", "RASPBERRY PI", "5-minute aggregation", 504, 126),
    ("net", "INTERNET", "simulated link", 738, 126),
    ("cloud", "CLOUD", "in-memory storage", 972, 126),
    ("dash", "DASHBOARD", "Streamlit UI", 1206, 126),
]

# 0: idle, 1: sensor->ESP, 2: ESP->RPi, 3: RPi->Internet,
# 4: Internet->Cloud, 5: Cloud->Dashboard
STEPS = ["Idle", "BME680 → ESP32", "ESP32 → Raspberry Pi",
         "Raspberry Pi → Internet", "Internet → Cloud", "Cloud → Dashboard"]


def _symbol(kind: str, x: int, y: int) -> str:
    cx = x + 87
    if kind == "sensor":
        return f'<g stroke="#62d9d5" stroke-width="4" fill="none"><path d="M {cx-18} {y+67} v 33 a 20 20 0 1 0 16 0 v -33 a 8 8 0 0 0 -16 0"/><path d="M {cx-10} {y+81} v 25"/></g>'
    if kind == "esp":
        return f'<g fill="none" stroke="#62d9d5" stroke-width="3"><rect x="{cx-25}" y="{y+60}" width="50" height="49" rx="7"/><rect x="{cx-12}" y="{y+74}" width="24" height="20" rx="2"/><path d="M {cx-42} {y+72} h 16 M {cx-42} {y+86} h 16 M {cx+26} {y+72} h 16 M {cx+26} {y+86} h 16"/></g>'
    if kind == "rpi":
        return f'<g stroke="#62d9d5" fill="none" stroke-width="3"><rect x="{cx-31}" y="{y+60}" width="62" height="49" rx="6"/><rect x="{cx-9}" y="{y+71}" width="21" height="21" rx="3"/><path d="M {cx-19} {y+53} v 7 M {cx-5} {y+53} v 7 M {cx+9} {y+53} v 7 M {cx+23} {y+53} v 7"/></g>'
    if kind == "net":
        return f'<g stroke="#62d9d5" fill="none" stroke-width="3"><circle cx="{cx}" cy="{y+85}" r="27"/><ellipse cx="{cx}" cy="{y+85}" rx="10" ry="27"/><path d="M {cx-27} {y+85} h 54 M {cx-22} {y+72} h44 M {cx-22} {y+98} h44"/></g>'
    if kind == "cloud":
        return f'<path d="M {cx-32} {y+101} h 63 a 16 16 0 0 0 0 -32 a 26 26 0 0 0 -49 -6 a 19 19 0 0 0 -14 38z" stroke="#62d9d5" stroke-width="3.5" fill="none"/>'
    return f'<g stroke="#62d9d5" stroke-width="3" fill="none"><rect x="{cx-37}" y="{y+57}" width="74" height="49" rx="4"/><path d="M {cx-27} {y+67} h 27 v 16 h 26 M {cx-16} {y+114} h 32 M {cx} {y+106} v 8"/></g>'


def render_board(stage=0, sensor_online=True, internet_online=True,
                 latest_summary=None, cloud_count=0, queue_count=0, clock="—") -> str:
    """Return standalone SVG/HTML, no script or external assets needed."""
    stage = max(0, min(5, int(stage)))
    summary = latest_summary or {}
    quality = "Complete" if summary.get("complete") else "Incomplete" if summary else "No summary"
    badges = {
        "sensor": ("ONLINE", "#55e2a4") if sensor_online else ("OFFLINE", "#f77981"),
        "esp": ("ONLINE", "#55e2a4") if sensor_online else ("OFFLINE", "#f77981"),
        "rpi": (quality.upper(), "#55e2a4" if summary.get("complete") else "#f2c06d"),
        "net": ("ONLINE", "#55e2a4") if internet_online else ("OFFLINE", "#f77981"),
        "cloud": (f"{cloud_count} RECORDS", "#55e2a4"),
        "dash": ("READY", "#55e2a4"),
    }
    cards = []
    for key, name, desc, x, y in NODES:
        label, color = badges[key]
        cards.append(f'''
          <g>
          <rect x="{x}" y="{y}" width="174" height="216" rx="15" fill="#151e2e" stroke="#3c5065" stroke-width="1.5"/>
          <rect x="{x+11}" y="{y+11}" width="152" height="194" rx="10" fill="#19273b" stroke="#22344a"/>
          {_symbol(key,x,y)}
          <text x="{x+87}" y="{y+137}" fill="#eef8ff" font-size="14" text-anchor="middle" font-weight="700">{name}</text>
          <text x="{x+87}" y="{y+158}" fill="#a9bccb" font-size="12" text-anchor="middle">{desc}</text>
          <circle cx="{x+21}" cy="{y+185}" r="5" fill="{color}"/>
          <text x="{x+33}" y="{y+189}" fill="{color}" font-size="11" font-weight="600">{escape(label)}</text>
          </g>''')
    wires = []
    # The only hardware-style wires: I2C sensor on the ESP32 board.
    for dy, color, tag in [(0, "#5be2c0", "SDA"), (8, "#ffcb65", "SCL"), (16, "#fc8a96", "3V3"), (24, "#8fa4bd", "GND")]:
        y = 199 + dy
        wires.append(f'<path d="M 210 {y} L 270 {y}" stroke="{color}" stroke-width="3" fill="none" stroke-linecap="round"/>')
    wires.append('<text x="240" y="185" text-anchor="middle" fill="#bdccd9" font-size="11">I²C WIRES</text>')
    paths = [
        'M 210 211 L 270 211',
        'M 444 211 L 504 211',
        'M 678 211 L 738 211',
        'M 912 211 L 972 211',
        'M 1146 211 L 1206 211',
    ]
    for idx, p in enumerate(paths):
        if idx:
            blocked = (idx == 1 and not sensor_online) or (idx >= 2 and not internet_online)
            color = '#5a6c86' if blocked else '#66aef8'
            wires.append(f'<path d="{p}" stroke="{color}" stroke-width="3" stroke-dasharray="4 8" fill="none"/>')
            wires.append(f'<path d="{p}" stroke="{color}" stroke-width="2" fill="none" marker-end="url(#arrow)"/>')
            wires.append(f'<text x="{(210 if idx==0 else 444+(idx-1)*234)+30}" y="187" text-anchor="middle" fill="#a9bccb" font-size="11">SIGNAL</text>')
        if idx + 1 == stage and not ((idx == 1 and not sensor_online) or (idx >= 2 and not internet_online)):
            # Flow particles animate along the currently active hop only.
            for offset in ['0s', '-0.45s', '-0.9s']:
                wires.append(f'''<circle r="5" fill="#67f5ca" filter="url(#glow)">
                    <animateMotion dur="1.35s" begin="{offset}" repeatCount="indefinite" path="{p}"/>
                </circle>''')
    active = escape(STEPS[stage])
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
       html,body {{ margin:0; background:transparent; color:#e8f1fa; font-family:system-ui,Segoe UI,Arial,sans-serif; }}
       .viewport {{ overflow-x:auto; background:linear-gradient(135deg,#0c1321,#141e2e); border-radius:16px;
                   border:1px solid #2a3e53; }}
       .hint {{ padding:12px 18px; font-size:13px; color:#a7bed1; }}
       .hint b {{ color:#77e9c9; }}
    </style></head><body><div class="viewport">
       <svg viewBox="0 0 1416 465" width="100%" style="min-width:920px" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Hygron simulated IoT component board">
       <defs>
         <pattern id="dots" width="25" height="25" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#31425b"/></pattern>
         <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#66aef8"/></marker>
         <filter id="glow"><feGaussianBlur stdDeviation="2.5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
       </defs>
       <rect x="0" y="0" width="1416" height="465" fill="url(#dots)"/>
       <text x="38" y="52" font-weight="700" font-size="24" fill="#f1f7fd">HYGRON  /  VIRTUAL IoT BOARD</text>
       <text x="39" y="77" font-size="13" fill="#a2b8c9">Software-in-the-loop · no physical hardware, external requests, or real cloud</text>
       <text x="1370" y="54" fill="#7de6cb" font-size="14" text-anchor="end">ACTIVE STEP: {active}</text>
       <g>{''.join(wires)}</g>
       <g>{''.join(cards)}</g>
       <rect x="34" y="381" width="1348" height="56" rx="11" fill="#18283a" stroke="#35506a"/>
       <text x="54" y="405" fill="#d7e9f5" font-size="14">WIRE: Sensor → ESP32 (I²C)</text>
       <text x="385" y="405" fill="#d7e9f5" font-size="14">DASHED: wireless/network messages</text>
       <text x="865" y="405" fill="#d7e9f5" font-size="14">QUEUED: {int(queue_count)}</text>
       <text x="1125" y="405" fill="#d7e9f5" font-size="14">TIME: {escape(str(clock))}</text>
       <text x="54" y="426" fill="#9cb2c3" font-size="12">Glowing particles indicate the current simulated transmission stage, not actual electronics or network traffic.</text>
       </svg></div></body></html>'''
