"""Hygron: single-page hotel-facing HCI dashboard, with optional trained RF models.

Start: py -m streamlit run app.py
All sensor and cloud activity is software-simulated. No actual Internet traffic.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from html import escape
import math
import random

import pandas as pd
import streamlit as st
import altair as alt

from sensor_simulator import VirtualESP32
from edge_gateway import EdgeGateway
from shared_store import SQLiteCloud, DB_PATH
from ml_bridge import latest_features, HISTORY_ROWS
from inference import load_models, estimate_risk

st.set_page_config(page_title="Hygron | Room Monitoring", layout="wide", initial_sidebar_state="collapsed")

ROOMS = {"room_101": ("Room 101", 64), "room_102": ("Room 102", 73),
         "room_103": ("Room 103", 84), "room_104": ("Room 104", 91)}
TIMEZONE = timezone(timedelta(hours=8))
COLOR = {"Low": "#237d58", "Medium": "#b37a21", "High": "#c54a42", "Unavailable": "#717b89"}
RANK = {"High": 0, "Medium": 1, "Low": 2, "Unavailable": 3}
RISK_HELP = {
    "High": "Conditions need attention first. Inspect the room and check whether humidity is improving.",
    "Medium": "Conditions should be monitored. Review the trend and plan a follow-up check.",
    "Low": "Conditions are currently lower risk. Continue normal monitoring.",
    "Unavailable": "There is not enough valid data for a risk estimate. This is not the same as Low risk.",
}
RISK_ACTION = {
    "High": "Inspect first and check for moisture, condensation, or ventilation issues.",
    "Medium": "Monitor the trend and plan a follow-up check.",
    "Low": "Continue normal monitoring.",
    "Unavailable": "Review data availability before making a risk decision.",
}

dark_mode = st.session_state.get('dashboard_dark_mode', True)

st.markdown("""<style>
:root{
    --hy-bg:var(--background-color,#f5f5f7);
    --hy-surface:var(--secondary-background-color,#fff);
    --hy-text:var(--text-color,#1d1d1f);
    --hy-muted:var(--secondary-text-color,#6e6e73);
    --hy-primary:var(--primary-color,#0071e3);
    --hy-border:rgba(128,128,128,.22);
}
.stApp{background:var(--hy-bg)}
.block-container{padding-top:1.8rem;max-width:1240px;font-size:17px}
[data-testid="stMain"]{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
[data-testid="stMain"] h1{font-size:2.55rem;letter-spacing:-.04em;color:var(--hy-text);margin-bottom:.35rem}
[data-testid="stMain"] h2{font-size:1.65rem;letter-spacing:-.02em;color:var(--hy-text);margin-top:2rem}
[data-testid="stMain"] h3{font-size:1.25rem;letter-spacing:-.01em;color:var(--hy-text)}
[data-testid="stMain"] p,[data-testid="stMain"] label,[data-testid="stMain"] li{color:var(--hy-muted);font-size:1.05rem;line-height:1.55}
[data-testid="stCaptionContainer"]{font-size:.95rem!important}
[data-testid="stMetric"]{background:var(--hy-surface);border:1px solid var(--hy-border);border-radius:16px;padding:18px 18px;box-shadow:0 6px 20px rgba(0,0,0,.045)}
[data-testid="stMetric"]{min-height:125px}
[data-testid="stMetricLabel"]{color:var(--hy-muted)!important;font-size:.92rem!important;font-weight:700!important;letter-spacing:.01em}
[data-testid="stMetricValue"]{color:var(--hy-text)!important;font-size:2.25rem!important;margin-top:5px}
[data-testid="stHorizontalBlock"]{gap:14px}
[data-testid="stDataFrame"]{border:1px solid var(--hy-border);border-radius:16px;overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,.035);font-size:16px}
[data-testid="stDataFrame"] th{font-size:15px!important;font-weight:700!important}
[data-testid="stDataFrame"] td{font-size:16px!important;height:44px!important}
button[kind="primary"]{background:var(--hy-primary);border-color:var(--hy-primary);border-radius:999px;color:#fff!important}
button[kind="primary"] p,button[kind="primary"] span{color:#fff!important}
button[kind="secondary"]{border-radius:999px}
[data-testid="stAlert"]{border:0;border-radius:16px;box-shadow:none}
[data-testid="stSidebar"]{
    border-right:1px solid var(--hy-border);
    padding:18px 16px;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3{
    font-size:.76rem!important;
    font-weight:750;
    letter-spacing:.12em;
    text-transform:uppercase;
    margin:6px 8px 14px;
}
[data-testid="stSidebarNavLink"],
[data-testid="stSidebarNav"] a{
    border-radius:11px;
    margin:3px 0;
    min-height:42px;
}
[data-testid="stSidebarNav"] a:hover{
    background:rgba(128,128,128,.12);
}
[data-testid="stSidebar"] [data-testid="stPageLink"]{
    border-radius:11px;
    padding:3px 5px;
}
.hy-priority{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:18px 20px;margin:1.25rem 0 1.8rem;border-radius:14px;background:var(--hy-surface);border:1px solid var(--hy-border);box-shadow:0 2px 8px rgba(0,0,0,.035)}
.hy-priority-copy{display:flex;align-items:flex-start;gap:14px}
.hy-priority-dot{width:8px;height:8px;border-radius:50%;margin-top:6px;flex:none}
.hy-priority.high .hy-priority-dot{background:#ff3b30}.hy-priority.medium .hy-priority-dot{background:#ff9f0a}.hy-priority.low .hy-priority-dot{background:#34c759}.hy-priority.unavailable .hy-priority-dot{background:#8e8e93}
.hy-priority-kicker{font-size:.72rem;font-weight:650;color:var(--hy-muted);letter-spacing:.02em}
.hy-priority-title{font-size:1.08rem;font-weight:700;color:var(--hy-text);margin-top:2px}
.hy-priority-detail{font-size:.82rem;color:var(--hy-muted);margin-top:3px}
.hy-priority-action{font-size:.82rem;font-weight:600;color:var(--hy-primary);white-space:nowrap;padding:8px 10px;border-radius:999px}
.hy-priority.high{background:rgba(255,69,58,.07)}
.hy-priority.medium{background:rgba(255,159,10,.07)}
.hy-priority.low{background:rgba(48,209,88,.07)}
.hy-priority.unavailable{background:rgba(142,142,147,.07)}
.hy-status{display:inline-flex;align-items:center;gap:7px;font-weight:750}
.hy-status-icon{display:inline-block;flex:none;vertical-align:-3px}
.hy-status.high{color:#ff453a}.hy-status.medium{color:#ff9f0a}.hy-status.low{color:#30d158}.hy-status.unavailable{color:#98989f}
.hy-note{font-size:.82rem;color:var(--hy-muted)}
.hy-flow{padding:14px 16px;border:1px solid var(--hy-border);border-radius:16px;background:var(--hy-surface)}
</style>""", unsafe_allow_html=True)

if dark_mode:
    st.markdown(
        """<style>:root{
        --hy-bg:#1c1c1e;--hy-surface:#2c2c2e;--hy-text:#f5f5f7;
        --hy-muted:#d1d1d6;--hy-primary:#0a84ff;--hy-border:rgba(255,255,255,.18);
        --hy-sidebar:#161618;--hy-sidebar-text:#f5f5f7;
        --hy-input:#2c2c2e;
        } [data-testid="stSidebar"]{background:var(--hy-sidebar)!important}
        [data-testid="stSidebar"] *{color:var(--hy-sidebar-text)!important}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#a1a1a6!important}
        [data-testid="stSidebar"] [data-testid="stCheckbox"]{margin-top:12px}
        [data-testid="stHeader"]{background:var(--hy-bg)!important}
        [data-baseweb="select"]>div,[data-baseweb="input"]{background:var(--hy-input)!important;color:var(--hy-text)!important;border-color:var(--hy-border)!important}
        [data-testid="stExpander"]{background:var(--hy-surface)!important;border-color:var(--hy-border)!important}
        [data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{color:var(--hy-text)!important}
        footer, [data-testid="stFooter"], a[href*="streamlit.io"], [class*="viewerBadge"]{display:none!important;visibility:hidden!important;height:0!important}
        }</style>""",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """<style>:root{
        --hy-bg:#f5f5f7;--hy-surface:#ffffff;--hy-text:#1d1d1f;
        --hy-muted:#6e6e73;--hy-primary:#0071e3;--hy-border:rgba(128,128,128,.22);
        --hy-sidebar:#ffffff;--hy-sidebar-text:#1d1d1f;--hy-input:#ffffff;
        } [data-testid="stSidebar"]{background:var(--hy-sidebar)!important}
        [data-testid="stSidebar"] *{color:var(--hy-sidebar-text)!important}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{color:#6e6e73!important}
        [data-testid="stHeader"]{background:var(--hy-bg)!important}
        [data-baseweb="select"]>div,[data-baseweb="input"]{background:var(--hy-input)!important;color:var(--hy-text)!important;border-color:var(--hy-border)!important}
        [data-testid="stExpander"]{background:var(--hy-surface)!important;border-color:var(--hy-border)!important}
        [data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{color:var(--hy-text)!important}
        footer, [data-testid="stFooter"], a[href*="streamlit.io"], [class*="viewerBadge"]{display:none!important;visibility:hidden!important;height:0!important}
        }</style>""",
        unsafe_allow_html=True,
    )


def warm_history(room_id: str, base_rh: float, end: datetime) -> list[dict]:
    """One independent, explicitly synthetic 60-day warm start (not ML labels)."""
    rng = random.Random(107 + int(room_id.split('_')[-1]))
    start = end - timedelta(minutes=5 * (HISTORY_ROWS - 1))
    values = []
    for n in range(HISTORY_ROWS):
        ts = start + timedelta(minutes=5*n)
        hour = ts.hour + ts.minute / 60
        cycle = math.sin((hour - 8) * math.pi / 12)
        rh = max(2.0, min(99.9, base_rh - 4.5*cycle + rng.gauss(0, 0.6)))
        temp = 27 + 1.5*cycle + rng.gauss(0, .1)
        values.append({"room_id":room_id, "node_id":f"esp32_{room_id}",
            "timestamp":ts.isoformat(timespec='seconds'), "complete":True,
            "rh":round(rh,3), "temp":round(temp,3),
            "voc_resistance":round(max(5000, 47000-rh*85+rng.gauss(0,200)),1),
            "source":"synthetic_sil"})
    return values


def initialize():
    """Shared persistent data; simulated history seeded only once per room."""
    start = datetime(2026, 8, 30, 0, 0, tzinfo=TIMEZONE)
    cloud = SQLiteCloud()
    for rid, (_, rh) in ROOMS.items():
        cloud.seed_room_if_empty(rid, lambda rid=rid, rh=rh: warm_history(rid, rh, start-timedelta(minutes=5)))
    st.session_state.client = {
        "cloud": cloud, "alerts": [], "acknowledged": set(), "last_status": {},
        "messages": [], "selected": "room_101", "seen_timestamps": {},
    }


if "client" not in st.session_state:
    initialize()
s = st.session_state.client


@st.cache_resource(show_spinner=False)
def cached_models():
    folder = Path(__file__).resolve().parents[1] / 'models'
    return load_models(str(folder))

try:
    models = cached_models()
    model_issue = None
except (FileNotFoundError, ImportError, KeyError, ValueError, OSError) as exc:
    models = None
    model_issue = f"{type(exc).__name__}: {exc}"


def get_status(room_id: str) -> dict:
    rows = s['cloud'].history(room_id, complete_only=True, limit=HISTORY_ROWS)
    if not rows:
        return {"current":"Unavailable", "future":"Unavailable", "error":"No valid data"}
    latest = rows[-1]
    result = {"rh":latest['rh'], "temp":latest['temp'], "at":latest['timestamp'],
              "current":"Unavailable", "future":"Unavailable", "error":None}
    if models is None:
        result['error'] = 'ML model files not installed'
        return result
    try:
        row = latest_features(rows)
        output = estimate_risk(row, models)
        result.update(current=output['current_risk'], future=output['forecast_24h_risk'])
    except (ValueError, KeyError, IndexError) as exc:
        result['error'] = str(exc)
    return result


def risk_icon(label: str) -> str:
    return {'High':'High','Medium':'Medium','Low':'Low','Unavailable':'Unavailable'}.get(label,'Unavailable')


def risk_badge(label: str) -> str:
    def icon(path: str) -> str:
        return (
            '<svg class="hy-status-icon" viewBox="0 0 24 24" width="16" height="16" '
            'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
        )

    return {
        'High': f'<span class="hy-status high">{icon("<path d=\"M10.3 2.8a2 2 0 0 1 3.4 0l8 13.8a2 2 0 0 1-1.7 3H4a2 2 0 0 1-1.7-3z\"/><path d=\"M12 9v4\"/><path d=\"M12 17h.01\"/>")} HIGH</span>',
        'Medium': f'<span class="hy-status medium">{icon("<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M12 8v5\"/><path d=\"M12 16h.01\"/>")} MEDIUM</span>',
        'Low': f'<span class="hy-status low">{icon("<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M8 12l3 3 5-6\"/>")} LOW</span>',
        'Unavailable': f'<span class="hy-status unavailable">{icon("<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M8 12h8\"/>")} UNAVAILABLE</span>',
    }.get(label, f'<span class="hy-status unavailable">{icon("<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M8 12h8\"/>")} UNAVAILABLE</span>')


def display_timestamp(value: str | None) -> str:
    if not value:
        return 'Unavailable'
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=TIMEZONE)
        return timestamp.astimezone(TIMEZONE).strftime('%d %b %Y, %I:%M %p PHT')
    except ValueError:
        return value


def risk_table_label(label: str) -> str:
    return {
        'High': 'HIGH — Inspect first',
        'Medium': 'MEDIUM — Monitor',
        'Low': 'LOW — Normal monitoring',
        'Unavailable': 'UNAVAILABLE — Check data',
    }.get(label, 'UNAVAILABLE — Check data')


def sync_alerts(statuses):
    """Local dashboard acknowledgements; alert history is per browser session."""
    for rid, status in statuses.items():
        stamp = status.get('at')
        if not stamp or s['seen_timestamps'].get(rid) == stamp:
            continue
        previous = s['last_status'].get(rid)
        if status['current'] == 'High' and previous != 'High':
            key = f"{rid}_{stamp}"
            s['alerts'].insert(0, {'id':key, 'room':rid,
                'timestamp':datetime.fromisoformat(stamp),
                'text':'High estimated mold-growth risk', 'type':'Current risk'})
        s['last_status'][rid] = status['current']
        s['seen_timestamps'][rid] = stamp


view = 'Overview'
if view == 'Methodology':
    st.title('Methodology')
    st.caption('How the prototype works, from room conditions to staff decisions.')
    st.markdown("""
**1. Collect room conditions.** A simulated BME680 sensor and ESP32 node generate temperature, relative humidity, and gas-resistance readings. These are examples, not physical measurements.

**2. Prepare the readings.** A simulated Raspberry Pi validates incoming packets and summarizes them into five-minute readings. A virtual network queue passes summaries to shared SQLite storage on the same computer. Network disconnections can delay delivery.

**3. Estimate risk.** Two trained Random Forest models classify the current condition and estimate one category **24 hours ahead**. They use engineered environmental features and were trained on simulated VTT-derived labels, not confirmed real-room mold observations.

**4. Support hotel decisions.** The dashboard organizes room risk, environmental trends and alerts so staff can prioritize inspection. An alert is a prompt to investigate conditions, not confirmation that mold is present.

**5. Understand limitations.** Forecasts are not hourly curves and are not proof of future mold. An evaluated direct 24-hour forecast had a macro-F1 of about 0.652 on held-out synthetic data; confidence intervals and calibrated probabilities are not available here.
""")
    st.divider()
    st.markdown('**Explore the virtual IoT demonstration**')
    st.caption('Use the IoT Workbench page in the Hygron navigation. Both pages read the same local SQLite summaries; refresh this page after delivering new readings.')
else:
    st.title('Hygron room monitoring')
    st.caption('A calm overview of simulated room conditions and estimated mold-growth risk.')
    with st.expander('New here? Start with these three steps', expanded=False):
        st.markdown("""
        1. **Check the priority rooms** below to see where attention may be needed first.
        2. **Choose a room** to review its latest humidity, temperature, history, and 24-hour outlook.
        3. **Use the IoT Workbench** to run a simulated reading, then return here and refresh this dashboard.

        All readings are simulated. A risk estimate is not confirmation that mold is present.
        """)

    last_synced = s["cloud"].latest_timestamp()
    st.caption(f"Latest shared reading: {last_synced.strftime('%d %b %Y, %I:%M %p') if last_synced else 'None'} PHT · Four virtual guest rooms")
    if models is None:
        st.error('Risk unavailable: trained model files could not be loaded. Sensor readings remain simulated.')
        with st.expander('Technical details'):
            st.code(model_issue or 'Unknown model loading error')
    col_refresh, col_info = st.columns([1, 3], vertical_alignment='center')
    if col_refresh.button('↻ Refresh shared readings', type='primary', help='Re-read SQLite summaries generated by the Virtual IoT Board. Does not create measurements.'):
        st.rerun()
    col_info.caption('Refresh after completing a simulation cycle to view newly delivered readings. Risk estimates are not mold detection.')

    statuses = {rid:get_status(rid) for rid in ROOMS}
    sync_alerts(statuses)
    counts = {k:sum(v['current']==k for v in statuses.values()) for k in ['High','Medium','Low','Unavailable']}
    priority_room = sorted(ROOMS, key=lambda k:(RANK[statuses[k]['current']], k))[0]
    priority_status = statuses[priority_room]
    if priority_status['current'] == 'High':
        details = []
        if priority_status.get('rh') is not None:
            details.append(f"humidity is {priority_status['rh']:.1f}%")
        if priority_status.get('temp') is not None:
            details.append(f"temperature is {priority_status['temp']:.1f} °C")
        context = f" ({', '.join(details)})" if details else ""
        st.markdown(
            f'<div class="hy-priority high" role="alert" aria-label="High risk: {ROOMS[priority_room][0]} needs attention">'
            f'<div class="hy-priority-copy"><div><div class="hy-priority-kicker">Recommended first check</div>'
            f'<div class="hy-priority-title">{ROOMS[priority_room][0]} · <span class="hy-status high">High risk</span></div>'
            f'<div class="hy-priority-detail">{context.strip(" ()")} · Risk estimates do not confirm physical mold.</div>'
            f'</div></div><div class="hy-priority-action">Inspect for moisture or ventilation issues →</div></div>',
            unsafe_allow_html=True,
        )
    elif priority_status['current'] == 'Medium':
        st.markdown(
            f'<div class="hy-priority medium"><div class="hy-priority-copy"><span class="hy-priority-dot"></span><div><div class="hy-priority-kicker">Recommended first check</div><div class="hy-priority-title">{ROOMS[priority_room][0]} · Medium estimated risk</div><div class="hy-priority-detail">Review the trend and plan a follow-up check.</div></div></div><div class="hy-priority-action">Monitor room →</div></div>',
            unsafe_allow_html=True,
        )
    elif priority_status['current'] == 'Unavailable':
        st.markdown(
            '<div class="hy-priority unavailable"><div class="hy-priority-copy"><span class="hy-priority-dot"></span><div><div class="hy-priority-kicker">Data needs attention</div><div class="hy-priority-title">No usable risk estimate is available</div><div class="hy-priority-detail">Review room readings and data availability before making a decision.</div></div></div><div class="hy-priority-action">Review data →</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="hy-priority low"><div class="hy-priority-copy"><span class="hy-priority-dot"></span><div><div class="hy-priority-kicker">Recommended action</div><div class="hy-priority-title">All rooms currently have Low estimated risk</div><div class="hy-priority-detail">Continue normal monitoring. Risk estimates do not confirm physical mold.</div></div></div><div class="hy-priority-action">Monitoring is normal →</div></div>',
            unsafe_allow_html=True,
        )

    st.subheader('Risk at a glance')
    k1,k2,k3,k4 = st.columns(4)
    k1.metric('HIGH', counts['High'], help=RISK_HELP['High'])
    k1.caption('**Inspect first**')
    k2.metric('MEDIUM', counts['Medium'], help=RISK_HELP['Medium'])
    k2.caption('**Monitor the trend**')
    k3.metric('LOW', counts['Low'], help=RISK_HELP['Low'])
    k3.caption('**Normal monitoring**')
    k4.metric('UNAVAILABLE', counts['Unavailable'], help=RISK_HELP['Unavailable'])
    k4.caption('**Check data first**')

    st.subheader('Rooms needing attention first')
    st.caption('Rooms are sorted from highest to lowest estimated risk. Start with the first room, then select another to compare.')
    summary = []
    for rid in sorted(ROOMS, key=lambda k:(RANK[statuses[k]['current']],k)):
        status = statuses[rid]
        summary.append({'Room':ROOMS[rid][0], 'Estimated risk':risk_table_label(status['current']),
                        'Relative humidity': f"{status['rh']:.1f}%" if status.get('rh') is not None else 'Unavailable',
                        'Temperature': f"{status['temp']:.1f} °C" if status.get('temp') is not None else 'Unavailable',
                        'Latest reading': display_timestamp(status.get('at')),
                        'Staff action': RISK_ACTION[status['current']]})
    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
    selected_room = st.selectbox(
        'Choose a room to inspect',
        list(ROOMS),
        index=list(ROOMS).index(priority_room),
        format_func=lambda rid:ROOMS[rid][0],
    )
    cur = statuses[selected_room]
    st.subheader(f'{ROOMS[selected_room][0]} details')
    detail_cols = st.columns(4)
    detail_cols[0].metric('Estimated current risk', cur['current'].upper())
    detail_cols[1].metric('Relative humidity', f"{cur['rh']:.1f}%" if cur.get('rh') is not None else 'Unavailable')
    detail_cols[2].metric('Temperature', f"{cur['temp']:.1f} °C" if cur.get('temp') is not None else 'Unavailable')
    detail_cols[3].metric('Recommended action', 'Inspect' if cur['current'] == 'High' else 'Monitor' if cur['current'] == 'Medium' else 'Review data' if cur['current'] == 'Unavailable' else 'Continue')
    st.caption(f"Latest reading: {display_timestamp(cur.get('at'))}")
    st.info(
        f"**Staff action:** {RISK_ACTION[cur['current']]}\n\n"
        f"**Why:** {RISK_HELP[cur['current']]}"
    )
    if cur.get('error'):
        st.warning('Room assessment unavailable: '+cur['error'])

    st.subheader('Alerts')
    active = [a for a in s['alerts'] if a['id'] not in s['acknowledged']]
    st.caption(f'{len(active)} active alert(s) · review the room before acknowledging. An acknowledgment records review; it does not confirm that conditions are resolved.')
    if active:
        for alert in active[:5]:
            lhs,rhs = st.columns([4,1],vertical_alignment='center')
            alert_status = statuses.get(alert['room'], {})
            humidity = alert_status.get('rh')
            reading = f"Humidity: {humidity:.1f}%" if humidity is not None else "Humidity unavailable"
            lhs.write(
                f"### {ROOMS[alert['room']][0]} needs attention\n"
                f"**Estimated risk:** High  \n"
                f"**Condition:** {reading}  \n"
                f"**Latest reading:** {display_timestamp(alert_status.get('at'))}  \n"
                f"**Staff action:** {RISK_ACTION['High']}"
            )
            if rhs.button('Acknowledge',key='ack_'+alert['id']):
                s['acknowledged'].add(alert['id'])
                st.rerun()
    else:
        st.success('No active High-risk alerts in this simulation session.')
    with st.expander('Alert history'):
        if s['alerts']:
            st.dataframe(pd.DataFrame([{
                'Room': ROOMS[a['room']][0],
                'Time': display_timestamp(a['timestamp'].isoformat()),
                'Status': 'Acknowledged' if a['id'] in s['acknowledged'] else 'Action needed',
            } for a in s['alerts']]), hide_index=True, use_container_width=True)
        else:
            st.caption('No alerts have been triggered. This does not mean conditions are mold-free.')

    st.subheader('Humidity history')
    st.caption('Review the selected room’s simulated relative-humidity trend. The latest reading is marked on the chart.')
    timeframe = st.selectbox('Time period', ['24 hours','7 days','30 days','60 days'],help='Filter the selected room’s simulated humidity history.')
    rows = s['cloud'].history(selected_room,complete_only=True, limit=HISTORY_ROWS)
    if rows:
        frame = pd.DataFrame(rows)
        frame['timestamp'] = pd.to_datetime(frame['timestamp'],utc=True).dt.tz_convert('Asia/Manila')
        days = {'24 hours':1,'7 days':7,'30 days':30,'60 days':60}[timeframe]
        frame = frame[frame['timestamp'] >= frame['timestamp'].max()-pd.Timedelta(days=days)]
        if len(frame)>1300:
            frame=frame.iloc[::max(1,len(frame)//1200)]
        chart = alt.Chart(frame).mark_line(color='#357b9e').encode(
            x=alt.X(
                'timestamp:T',
                title='Simulated time',
                axis=alt.Axis(labelFontSize=12, titleFontSize=14),
            ),
            y=alt.Y(
                'rh:Q',
                title='Relative humidity (%)',
                scale=alt.Scale(domain=[0,100]),
                axis=alt.Axis(labelFontSize=12, titleFontSize=14),
            ),
            tooltip=[
                alt.Tooltip('timestamp:T', title='Simulated time'),
                alt.Tooltip('rh:Q', title='Relative humidity', format='.1f'),
                alt.Tooltip('temp:Q', title='Temperature', format='.1f'),
            ]
        ).properties(height=250, title=f'{ROOMS[selected_room][0]} relative humidity')
        threshold = alt.Chart(pd.DataFrame({'rh':[80]})).mark_rule(
            color='#9e6b24',
            strokeDash=[5,5],
            size=2,
        ).encode(
            y=alt.Y('rh:Q'),
            tooltip=alt.value('80% RH reference'),
        )
        latest_point = alt.Chart(frame.tail(1)).mark_point(
            color='#c54a42',
            filled=True,
            size=85,
        ).encode(
            x='timestamp:T',
            y='rh:Q',
            tooltip=[
                alt.Tooltip('timestamp:T', title='Latest simulated reading'),
                alt.Tooltip('rh:Q', title='Relative humidity', format='.1f'),
                alt.Tooltip('temp:Q', title='Temperature', format='.1f'),
            ],
        )
        st.altair_chart(chart + threshold + latest_point, use_container_width=True)
        current_rh = float(frame['rh'].iloc[-1])
        recent_above = float((frame['rh'] >= 80).mean() * 100)
        trend_cols = st.columns(3)
        trend_cols[0].metric('Latest RH', f'{current_rh:.1f}%')
        trend_cols[1].metric('Humidity range', f'{frame["rh"].min():.1f}–{frame["rh"].max():.1f}%')
        trend_cols[2].metric('Readings at/above 80%', f'{recent_above:.0f}%')
        if recent_above >= 80:
            humidity_message = 'Humidity is high across most of the displayed period.'
        elif recent_above > 0:
            humidity_message = 'Humidity reached the 80% reference during part of the displayed period.'
        else:
            humidity_message = 'Humidity stayed below the 80% reference during the displayed period.'
        st.info(
            f"**Simple summary:** The latest humidity is **{current_rh:.1f}%**. "
            f"{humidity_message}"
        )
        st.caption('The dashed line marks 80% RH for monitoring. It is not a clinical or biological mold-detection threshold. The red point marks the latest simulated reading.')
        with st.expander('Chart text alternative'):
            st.write(f"For {ROOMS[selected_room][0]}, {len(frame)} displayed simulated readings are shown. RH ranges from {frame['rh'].min():.1f}% to {frame['rh'].max():.1f}%; the latest reading is {current_rh:.1f}%, and {recent_above:.0f}% of displayed readings are at or above 80% RH.")
    else:
        st.info('No valid cloud readings for this room.')

    st.subheader('24-hour estimated outlook')
    current = cur['current']; future = cur['future']
    if future == 'Unavailable':
        st.warning('Forecast unavailable because there is not enough valid history or the model could not produce an estimate.')
    else:
        order={'Low':0,'Medium':1,'High':2}
        direction=('Higher' if order[future]>order[current] else 'Lower' if order[future]<order[current] else 'Unchanged') if current in order else 'Unknown'
        forecast_cols = st.columns(3)
        forecast_cols[0].metric('Current estimate', risk_icon(current))
        forecast_cols[1].metric('Estimated in 24 hours', risk_icon(future))
        forecast_cols[2].metric('Expected direction', direction)
        st.caption(
            f"This estimate is relative to the latest simulated reading "
            f"({display_timestamp(cur.get('at'))}). It is supplementary decision support, not a guaranteed warning."
        )
    with st.expander('How to use this forecast · limitations'):
        st.write('This is one predicted category at +24 hours, not an hourly curve. The trained forecast did not outperform a current-risk persistence comparator on the simulated test (macro-F1 ≈ 0.652 vs. ≈ 0.662). No calibrated confidence estimate is available. Staff should confirm conditions before taking action.')

    st.subheader('How a reading reaches this dashboard')
    with st.expander('View the reading flow', expanded=False):
        st.markdown('**Simulated room**  →  **Sensor + ESP32**  →  **Raspberry Pi**  →  **Internet queue**  →  **This dashboard**')
        st.caption('The workbench creates simulated readings. The dashboard displays them after processing, delivery, storage, and refresh.')
