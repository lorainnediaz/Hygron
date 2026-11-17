"""Hygron: single-page hotel-facing HCI dashboard, with optional trained RF models.

Start: py -m streamlit run app.py
All sensor and cloud activity is software-simulated. No actual Internet traffic.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
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

st.set_page_config(page_title="Hygron | Room Monitoring", page_icon="🌡️", layout="wide", initial_sidebar_state="collapsed")

ROOMS = {"room_101": ("Room 101", 64), "room_102": ("Room 102", 73),
         "room_103": ("Room 103", 84), "room_104": ("Room 104", 91)}
TIMEZONE = timezone(timedelta(hours=8))
COLOR = {"Low": "#237d58", "Medium": "#b37a21", "High": "#c54a42", "Unavailable": "#717b89"}
RANK = {"High": 0, "Medium": 1, "Low": 2, "Unavailable": 3}

st.markdown("""<style>
.block-container{padding-top:1.6rem;max-width:1350px}
[data-testid="stMetric"]{background:#f4f6f8;border:1px solid #e0e5e9;border-radius:12px;padding:14px}
@media (prefers-color-scheme:dark){[data-testid="stMetric"]{background:#222a30;border-color:#394047}}
.hy-card{border:1px solid #dce2e8;border-radius:13px;padding:14px 17px;margin-bottom:8px}
.hy-muted{font-size:.84rem;color:#778390}.hy-title{font-size:1.8rem;font-weight:750}
.hy-pill{display:inline-block;border-radius:999px;padding:4px 10px;font-size:.8rem;font-weight:700;color:white}
.hy-small{font-size:.87rem;line-height:1.65}
</style>""", unsafe_allow_html=True)


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


with st.sidebar:
    st.markdown('### Hygron')
    view = st.radio('Pages', ['Overview', 'Methodology'], label_visibility='collapsed')
    st.caption('Demo only · Simulated sensor readings')

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
    st.caption('The simulator opens separately, but both applications read the same local SQLite summaries. Refresh this page to see newly delivered readings.')
    sim_url = os.environ.get('HYGRON_SIMULATION_URL', 'http://localhost:8502')
    from html import escape as html_escape
    safe_url = html_escape(sim_url, quote=True)
    st.markdown(f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">Open IoT simulation in a new tab ↗</a>', unsafe_allow_html=True)
else:
    st.title('Room overview')
    last_synced = s["cloud"].latest_timestamp()
    st.caption(f"Latest shared simulated reading: {last_synced.strftime('%d %b %Y, %I:%M %p') if last_synced else 'None'} PHT · Four virtual guest rooms")
    if models is None:
        st.error('Risk unavailable: trained model files could not be loaded. Sensor readings remain simulated.')
        with st.expander('Technical details'):
            st.code(model_issue or 'Unknown model loading error')
    col_refresh, col_info = st.columns([1, 3], vertical_alignment='center')
    if col_refresh.button('↻ Refresh shared readings', type='primary', help='Re-read SQLite summaries generated by the Virtual IoT Board. Does not create measurements.'):
        st.rerun()
    col_info.caption('Simulation controls are in the separate IoT workbench. Risk is not direct mold detection.')

    statuses = {rid:get_status(rid) for rid in ROOMS}
    sync_alerts(statuses)
    counts = {k:sum(v['current']==k for v in statuses.values()) for k in ['High','Medium','Low','Unavailable']}
    k1,k2,k3,k4 = st.columns(4)
    k1.metric('High priority', counts['High'], help='Rooms with High estimated mold-conducive conditions; inspect first.')
    k2.metric('Medium priority', counts['Medium'], help='Rooms with Medium estimated risk; monitor environmental conditions.')
    k3.metric('Low priority', counts['Low'], help='Rooms with Low estimated risk; continue normal monitoring.')
    k4.metric('No status', counts['Unavailable'], help='Missing, stale, or unavailable model data. Not equivalent to low risk.')

    st.subheader('Rooms')
    st.caption('Sorted by current estimated risk. Select a room to inspect its history and 24-hour outlook.')
    def risk_icon(label):
        return {'High':'▲ High','Medium':'◆ Medium','Low':'● Low','Unavailable':'— Unavailable'}.get(label,'—')
    summary = []
    for rid in sorted(ROOMS, key=lambda k:(RANK[statuses[k]['current']],k)):
        status = statuses[rid]
        summary.append({'Room':ROOMS[rid][0], 'Current risk':risk_icon(status['current']),
                        'Humidity (%)':status.get('rh'), 'Temperature (°C)':status.get('temp'),
                        'Reading': 'Unavailable' if status.get('error') else 'Simulated'})
    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
    selected_room = st.selectbox('Room details', list(ROOMS), format_func=lambda rid:ROOMS[rid][0])
    cur = statuses[selected_room]
    with st.expander('What do the risk labels mean?'):
        st.write('High, Medium and Low are machine-learning classifications of environmental conditions associated with potential mold growth, not diagnoses of mold. A missing reading is shown separately as Unavailable.')
    if cur.get('error'):
        st.warning('Room assessment unavailable: '+cur['error'])

    st.subheader('Alerts')
    active = [a for a in s['alerts'] if a['id'] not in s['acknowledged']]
    st.caption(f'{len(active)} unacknowledged high-risk alert(s) · acknowledge after reviewing a room, not as proof of resolution.')
    if active:
        for alert in active[:5]:
            lhs,rhs = st.columns([4,1],vertical_alignment='center')
            lhs.write(f"**{ROOMS[alert['room']][0]} · High risk** — {alert['timestamp'].strftime('%d %b %H:%M')}")
            if rhs.button('Acknowledge',key='ack_'+alert['id']):
                s['acknowledged'].add(alert['id'])
                st.rerun()
    else:
        st.caption('No unacknowledged High-risk alerts in this simulation session.')
    with st.expander('Alert history'):
        if s['alerts']:
            st.dataframe(pd.DataFrame([{'Room':ROOMS[a['room']][0], 'Time':a['timestamp'].strftime('%d %b %H:%M'), 'Status':'Acknowledged' if a['id'] in s['acknowledged'] else 'Action needed'} for a in s['alerts']]),hide_index=True,use_container_width=True)
        else:
            st.caption('No alerts have been triggered. This does not mean conditions are mold-free.')

    st.subheader('Room history')
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
            x=alt.X('timestamp:T',title='Simulated time'),
            y=alt.Y('rh:Q',title='Relative humidity (%)',scale=alt.Scale(domain=[0,100])),
            tooltip=['timestamp:T',alt.Tooltip('rh:Q',format='.1f'),alt.Tooltip('temp:Q',format='.1f')]
        ).properties(height=230)
        threshold = alt.Chart(pd.DataFrame({'rh':[80]})).mark_rule(color='#9e6b24',strokeDash=[5,5]).encode(y='rh:Q')
        st.altair_chart(chart+threshold,use_container_width=True)
        st.caption('Dashed line: 80% RH reference. Not a clinical or biological mold-detection threshold.')
        with st.expander('Chart text alternative'):
            st.write(f"For {ROOMS[selected_room][0]}, {len(frame)} displayed simulated readings. RH range: {frame['rh'].min():.1f}%–{frame['rh'].max():.1f}%; most recent {frame['rh'].iloc[-1]:.1f}%.")
    else:
        st.info('No valid cloud readings for this room.')

    st.subheader('24-hour outlook')
    current = cur['current']; future = cur['future']
    if future == 'Unavailable':
        st.write('Forecast unavailable.')
    else:
        order={'Low':0,'Medium':1,'High':2}
        direction=('Higher' if order[future]>order[current] else 'Lower' if order[future]<order[current] else 'Unchanged') if current in order else 'Unknown'
        st.write(f"**{risk_icon(future)}** estimated in 24 hours · {direction} versus now")
    with st.expander('How to use this forecast · limitations'):
        st.write('This is one predicted category at +24 hours, not an hourly curve. The trained forecast did not outperform a current-risk persistence comparator on the simulated test (macro-F1 ≈ 0.652 vs. ≈ 0.662). No calibrated confidence estimate is available. Staff should confirm conditions before taking action.')
