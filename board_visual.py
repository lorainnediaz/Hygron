"""Layered architecture diagram for Hygron's virtual IoT simulator."""
from __future__ import annotations

from base64 import b64encode
from html import escape
from pathlib import Path

STEPS = [
    "Idle", "BME680 → ESP32", "ESP32 → Raspberry Pi",
    "Raspberry Pi → Internet", "Internet → SQLite", "SQLite → Dashboard",
]


def _image_data_uri(filename: str) -> str:
    """Embed local photos so the isolated Streamlit iframe can display them."""
    image_path = Path(__file__).resolve().parent / "images" / filename
    if not image_path.is_file():
        return ""
    return "data:image/jpeg;base64," + b64encode(image_path.read_bytes()).decode("ascii")


def render_board(stage=0, sensor_online=True, internet_online=True,
                 latest_summary=None, cloud_count=0, queue_count=0, clock="—") -> str:
    """Build a self-contained three-layer SVG with live simulator state."""
    stage = max(0, min(5, int(stage)))
    summary = latest_summary or {}
    complete = bool(summary.get("complete"))
    quality = "COMPLETE" if complete else "INCOMPLETE" if summary else "WAITING"
    quality_color = "#39d8a0" if complete else "#f1b85b" if summary else "#9aabc0"
    sensor_status, sensor_color = ("ONLINE", "#39d8a0") if sensor_online else ("OFFLINE", "#ff647c")
    internet_status, internet_color = ("ONLINE", "#39d8a0") if internet_online else ("OFFLINE", "#ff647c")
    cloud_status = f"{int(cloud_count):,} STORED" if cloud_count else "READY"
    queued = max(0, int(queue_count))
    active = escape(STEPS[stage])
    bme = _image_data_uri("bme680.jpg")
    esp = _image_data_uri("esp32.jpg")
    pi = _image_data_uri("raspberry-pi.jpg")

    # Stage 1 stays within the room. Stage 2 crosses to the edge gateway;
    # stages 3–4 cross the simulated Internet boundary; stage 5 reaches the UI.
    routes = [
        ("M 220 353 V 429", 1, sensor_online, "SENSOR BUS", 145, 395, False),
        ("M 380 535 H 433 Q 448 535 448 520 V 425 Q 448 410 463 410 H 525", 2, sensor_online, "VIA Wi-Fi", 440, 568, True),
        ("M 825 395 H 880", 3, internet_online, "EDGE → WAN", 852, 354, True),
        ("M 926 395 H 1000", 4, internet_online, "UPLOAD", 964, 354, True),
        ("M 1160 495 V 520", 5, internet_online, "DASHBOARD READ", 1282, 513, True),
    ]
    route_groups = []
    for path, hop, available, label, label_x, label_y, dashed in routes:
        group = []
        active_hop = stage == hop and available
        color = "#45d6ae" if active_hop else "#637991" if not available else "#58a6ff"
        dash = ' stroke-dasharray="8 8"' if dashed else ""
        group.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="4"{dash}'
            ' stroke-linecap="round" marker-end="url(#arrow)"/>'
        )
        group.append(f'<text x="{label_x}" y="{label_y}" text-anchor="middle" class="wire-label">{label}</text>')
        if active_hop:
            for offset in ("0s", "-.45s", "-.9s"):
                group.append(
                    f'<circle r="5" fill="#b5ffea" filter="url(#glow)">'
                    f'<animateMotion dur="1.1s" begin="{offset}" repeatCount="indefinite" path="{path}"/>'
                    "</circle>"
                )
        route_groups.append(group)

    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    * {{ box-sizing:border-box }} html,body {{ margin:0; background:transparent; color:#e8f1fa;
      font-family:Inter,system-ui,"Segoe UI",Arial,sans-serif }}
    .canvas {{ width:100%; overflow-x:auto; border:1px solid #2a4059; border-radius:16px;
      background:#101a29; box-shadow:0 12px 34px #050a1280 }}
    svg {{ display:block; width:100%; min-width:900px }}
    .eyebrow {{ fill:#93abc2; font-size:12px; letter-spacing:2px; font-weight:650 }}
    .title {{ fill:#f1f7fd; font-size:23px; font-weight:750 }}
    .sub {{ fill:#a8bacd; font-size:12px }} .layer-title {{ fill:#79d6bf; font-size:17px; font-weight:700 }}
    .name {{ fill:#f3f7fc; font-size:14px; font-weight:750 }} .detail {{ fill:#afc2d5; font-size:11px }}
    .status {{ font-size:10px; font-weight:750; letter-spacing:.5px }}
    .wire-label {{ fill:#9db0c4; font-size:9px; font-weight:700; letter-spacing:.7px }}
    </style></head><body><div class="canvas">
    <svg viewBox="0 0 1400 760" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Hygron room, edge, and cloud user interface layers">
      <defs>
        <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#26374b"/></pattern>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 10 5 0 10z" fill="#58a6ff"/></marker>
        <filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <rect width="1400" height="760" fill="#101a29"/><rect width="1400" height="760" fill="url(#grid)"/>
      <text x="40" y="39" class="eyebrow">HYGRON  /  VIRTUAL IoT WORKBENCH</text>
      <text x="40" y="68" class="title">System architecture</text>
      <text x="40" y="89" class="sub">Synthetic room readings move through the edge gateway to local storage and the hotel dashboard.</text>
      <rect x="910" y="27" width="450" height="46" rx="10" fill="#1a2b3e" stroke="#2b4561"/>
      <circle cx="931" cy="50" r="5" fill="#45d6ae"/><text x="946" y="54" fill="#b9cad9" font-size="11" font-weight="600">ACTIVE STEP</text>
      <text x="1040" y="54" fill="#76e8c9" font-size="12" font-weight="700">{active}</text>

      <!-- Layer panels -->
      <rect x="35" y="112" width="390" height="574" rx="18" fill="#142233" stroke="#2e465d" stroke-width="1.5"/>
      <rect x="475" y="112" width="400" height="574" rx="18" fill="#142a2c" stroke="#31574f" stroke-width="1.5"/>
      <rect x="960" y="112" width="405" height="574" rx="18" fill="#142233" stroke="#2e465d" stroke-width="1.5"/>
      <text x="62" y="145" class="layer-title">1. Room Layer</text>
      <text x="504" y="145" class="layer-title">2. Edge Layer</text>
      <text x="988" y="145" class="layer-title">3. Cloud &amp; UI Layer</text>

      <!-- Room layer: sensor above the ESP32 -->
      <g>
        <rect x="80" y="167" width="300" height="183" rx="16" fill="#1c2d3f" stroke="#405a70" stroke-width="1.5"/>
        <text x="86" y="195" class="name">SENSORS</text>
        <rect x="97" y="207" width="266" height="94" rx="8" fill="#eef0f2"/>
        {f'<image href="{bme}" x="97" y="207" width="266" height="94" preserveAspectRatio="xMidYMid meet"/>' if bme else '<text x="230" y="258" text-anchor="middle" fill="#183044" font-size="15" font-weight="700">BME680 module</text>'}
        <text x="86" y="326" class="detail">BME680 · Temp / RH / Gas · every 30s</text>
        <circle cx="86" cy="342" r="4.5" fill="{sensor_color}"/><text x="98" y="346" class="status" fill="{sensor_color}">{sensor_status}</text>
      </g>
      <g>
        <rect x="80" y="429" width="300" height="215" rx="16" fill="#1c2d3f" stroke="#405a70" stroke-width="1.5"/>
        {f'<image href="{esp}" x="180" y="440" width="100" height="143" preserveAspectRatio="xMidYMid meet"/>' if esp else '<text x="230" y="510" text-anchor="middle" fill="#e8f1fa" font-size="22" font-weight="700">ESP32</text>'}
        <text x="230" y="605" text-anchor="middle" class="name">ESP32 MCU</text>
        <text x="230" y="624" text-anchor="middle" class="detail">Packets sensor readings over Wi-Fi</text>
      </g>
      {''.join(route_groups[0])}
      {''.join(route_groups[1])}

      <!-- Edge layer: Raspberry Pi gateway -->
      <g>
        <rect x="525" y="240" width="300" height="300" rx="18" fill="#1a3938" stroke="#4b8b79" stroke-width="2"/>
        <rect x="550" y="265" width="250" height="154" rx="9" fill="#e9edef"/>
        {f'<image href="{pi}" x="550" y="265" width="250" height="154" preserveAspectRatio="xMidYMid meet"/>' if pi else '<text x="675" y="350" text-anchor="middle" fill="#183044" font-size="17" font-weight="700">Raspberry Pi</text>'}
        <text x="675" y="456" text-anchor="middle" class="name">RASPBERRY PI GATEWAY</text>
        <text x="675" y="481" text-anchor="middle" class="detail">Validates sensor packets</text>
        <text x="675" y="500" text-anchor="middle" class="detail">Aggregates ten readings into 5-min summaries</text>
        <circle cx="555" cy="522" r="5" fill="{quality_color}"/><text x="570" y="526" class="status" fill="{quality_color}">{quality}</text>
      </g>

      <!-- Simulated Internet boundary between edge and local SQLite -->
      <g>
        <circle cx="903" cy="395" r="23" fill="#1d3045" stroke="#58a6ff" stroke-width="2"/>
        <path d="M882 395h42M903 374c-10 12-10 30 0 42M903 374c10 12 10 30 0 42M887 386h32M887 404h32" fill="none" stroke="#8ccaff" stroke-width="1.8"/>
        <text x="903" y="433" text-anchor="middle" class="wire-label">SIM INTERNET</text>
      </g>
      {''.join(route_groups[2])}{''.join(route_groups[3])}

      <!-- Cloud & UI layer: local SQLite plus separate hotel dashboard -->
      <g>
        <rect x="1000" y="220" width="320" height="275" rx="16" fill="#1c2d3f" stroke="#405a70" stroke-width="1.5"/>
        <text x="1020" y="253" class="name">LOCAL CLOUD STORE</text>
        <text x="1020" y="275" class="detail">SQLite database · shared by both apps</text>
        <ellipse cx="1160" cy="344" rx="68" ry="22" fill="#29465d" stroke="#7dc8ff" stroke-width="2.5"/>
        <path d="M1092 344v73c0 12 30 22 68 22s68-10 68-22v-73" fill="#20374a" stroke="#7dc8ff" stroke-width="2.5"/>
        <path d="M1092 380c0 12 30 22 68 22s68-10 68-22M1092 417c0 12 30 22 68 22s68-10 68-22" fill="none" stroke="#7dc8ff" stroke-width="2"/>
        <text x="1160" y="383" text-anchor="middle" fill="#d4edff" font-size="14" font-weight="700">SQLite</text>
        <circle cx="1025" cy="475" r="5" fill="#39d8a0"/><text x="1040" y="479" class="status" fill="#39d8a0">{escape(cloud_status)}</text>
      </g>
      <g>
        <rect x="1000" y="520" width="320" height="137" rx="16" fill="#3a2a31" stroke="#75494b" stroke-width="1.5"/>
        <rect x="1020" y="545" width="54" height="40" rx="5" fill="#17283a" stroke="#7dc8ff" stroke-width="2"/>
        <path d="M1028 554h14v8h23v12h-37M1035 593h25M1047 585v8" fill="none" stroke="#7dc8ff" stroke-width="2"/>
        <text x="1085" y="560" class="name">HOTEL DASHBOARD</text>
        <text x="1085" y="582" class="detail">Displays trends and risk predictions</text>
        <text x="1085" y="601" class="detail">ML inference runs in the dashboard app</text>
        <circle cx="1025" cy="636" r="5" fill="#39d8a0"/><text x="1040" y="640" class="status" fill="#39d8a0">READY</text>
      </g>
      {''.join(route_groups[4])}

      <!-- Legend and simulation state -->
      <rect x="35" y="706" width="1330" height="34" rx="9" fill="#17283a" stroke="#30475e"/>
      <text x="55" y="728" class="detail">SOLID: SENSOR / GPIO</text>
      <text x="255" y="728" class="detail">DASHED: SIMULATED NETWORK</text>
      <text x="525" y="728" class="detail">QUEUE <tspan fill="#f2c56f" font-weight="700">{queued}</tspan></text>
      <text x="685" y="728" class="detail">SIMULATION TIME <tspan fill="#eaf2f8" font-weight="700">{escape(str(clock))}</tspan></text>
      <text x="1010" y="728" class="detail">NO PHYSICAL OR HOSTED CLOUD</text>
    </svg></div></body></html>'''
