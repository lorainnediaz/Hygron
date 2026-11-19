"""Hygron interactive Wokwi-style SIL board. Run: python -m streamlit run app.py"""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from board_visual import render_board, STEPS
from sensor_simulator import VirtualESP32
from edge_gateway import EdgeGateway
from network_cloud import SimulatedInternet, EdgeToCloudBridge
from shared_store import SQLiteCloud, DB_PATH
from simulation.bulk_engine import ROOM_BASE_RH, generate_bulk

st.set_page_config(page_title="Hygron | Virtual IoT Board", layout="wide")


def reset_state():
    """Reset the walkthrough, not previously delivered SQLite history."""
    selected = st.session_state.get("selected_room", "room_101")
    st.session_state.node = VirtualESP32(selected, f"esp32_{selected}", base_rh=ROOM_BASE_RH[selected])
    st.session_state.gateway = EdgeGateway()  # virtual Raspberry Pi
    st.session_state.internet = SimulatedInternet()
    st.session_state.cloud = SQLiteCloud()
    st.session_state.bridge = EdgeToCloudBridge(st.session_state.internet, st.session_state.cloud)
    latest = st.session_state.cloud.latest_timestamp()
    st.session_state.clock = latest + timedelta(minutes=5) if latest else datetime(2026, 8, 30, tzinfo=timezone(timedelta(hours=8)))
    st.session_state.phase = 0
    st.session_state.pending_packets = []
    st.session_state.latest_packet = None
    st.session_state.latest_summary = None
    st.session_state.delivered_last = 0
    st.session_state.completed_cycles = 0
    st.session_state.gateway_processed = 0
    st.session_state.log = []


if 'node' not in st.session_state:
    reset_state()


def add_log(message):
    st.session_state.log.insert(0, message)
    st.session_state.log = st.session_state.log[:25]


def advance_phase():
    """Move data once through one actual simulation stage."""
    s = st.session_state
    next_phase = 1 if s.phase >= 5 else s.phase + 1
    if next_phase == 1:
        s.pending_packets = [s.node.read(s.clock + timedelta(seconds=30 * i)) for i in range(10)]
        s.latest_packet = s.pending_packets[-1]
        add_log(f"BME680 generated {len(s.pending_packets)} 30-second synthetic sensor packets")
    elif next_phase == 2:
        for packet in s.pending_packets:
            s.gateway.receive(packet)
        s.latest_summary = next(summary for summary in s.gateway.summaries()
                                if summary['room_id'] == s.node.room_id
                                and summary['timestamp'] == s.clock.isoformat(timespec='seconds'))
        s.gateway_processed += 1
        add_log(f'Virtual Raspberry Pi processed a 5-minute summary for {s.node.room_id}')
    elif next_phase == 3:
        # Pi -> internet transport queue; upload takes place at phase 4.
        s.bridge.pending.append(dict(s.latest_summary))
        add_log('Raspberry Pi queued one summary for simulated Internet transmission')
    elif next_phase == 4:
        s.delivered_last = s.bridge.flush()
        if s.internet.online:
            add_log(f'Internet delivered {s.delivered_last} queued summarie(s) to virtual cloud')
        else:
            add_log('Simulated Internet offline: data remains queued at the Raspberry Pi')
    elif next_phase == 5:
        s.completed_cycles += 1
        s.clock += timedelta(minutes=5)
        add_log('Dashboard read current cloud state; simulated clock advanced five minutes')
    s.phase = next_phase


st.caption('Standalone technical demonstration · shares its delivered summaries with the hotel dashboard through SQLite')
st.title('Virtual IoT workbench')
st.caption('A Wokwi-inspired demonstration of how simulated room readings move between components.')
with st.expander('ⓘ How does clicking Simulate move the data?'):
    st.write('A virtual BME680 reading is packaged by ESP32 every 30 seconds. The Raspberry Pi combines 10 readings into a five-minute summary. The summary enters a simulated Internet queue, reaches shared SQLite storage if connected, and can then be read by the separate dashboard after refresh. Each Next stage button runs just one part of that journey.')
with st.expander('ⓘ Why not run this entirely in Wokwi?'):
    st.write('Wokwi focuses on microcontroller and circuit emulation. This prototype also needs a custom five-minute gateway aggregation, simulated transport queue and SQLite-backed cloud storage, plus a trained-model dashboard. This interactive board represents all stages together in one Python simulation; its drawn devices are not real hardware or a claim of full Wokwi hardware emulation.')

def change_room():
    """Switch the active virtual ESP32 without erasing cloud data or queued uploads."""
    s = st.session_state
    rid = s.selected_room
    s.node = VirtualESP32(rid, f'esp32_{rid}', base_rh=ROOM_BASE_RH[rid])
    s.phase = 0
    s.pending_packets = []
    s.latest_packet = None
    s.latest_summary = None
    # Stale sidebar widget values should not overwrite the newly chosen room's defaults.
    s.base_rh_widget = int(s.node.base_rh)
    s.base_temp_widget = int(s.node.base_temp)
    add_log(f'Selected {rid}; unfinished staged packets cleared; SQLite history retained')


with st.sidebar:
    st.header('Room & environment')
    st.selectbox('Room to simulate', list(ROOM_BASE_RH),
                 format_func=lambda rid: rid.replace('room_', 'Room '),
                 key='selected_room', on_change=change_room,
                 help='Manual stages and full five-minute cycles apply only to this room. Existing SQLite records remain intact.')
    scenario = st.selectbox('Environment scenario', ['normal', 'humid_spike', 'prolonged_damp', 'condensation'],
                            format_func=lambda x: x.replace('_', ' ').title())
    sensor_online = st.toggle('ESP32 / sensor online', value=st.session_state.node.online)
    internet_online = st.toggle('Simulated Internet online', value=st.session_state.internet.online)
    st.session_state.node.online = sensor_online
    st.session_state.internet.online = internet_online
    st.session_state.node.set_scenario(scenario, start=st.session_state.clock, duration_hours=48)
    st.slider('Room base relative humidity (%)', 40, 95, int(st.session_state.node.base_rh), key='base_rh_widget')
    st.session_state.node.base_rh = float(st.session_state.base_rh_widget)
    st.slider('Room base temperature (°C)', 18, 36, int(st.session_state.node.base_temp), key='base_temp_widget')
    st.session_state.node.base_temp = float(st.session_state.base_temp_widget)
    st.divider()
    if st.button('Reset simulation', use_container_width=True):
        reset_state()
        st.rerun()
    st.caption('Next stage animates each step; completed uploads are visible in the dashboard after refresh.')

left, mid, right = st.columns([1.2, 1.1, 1.3])
with left:
    next_click = st.button('▶ Next stage', type='primary', use_container_width=True)
with mid:
    full_click = st.button('⏭ Run full 5-min cycle', use_container_width=True)
with right:
    retry_click = st.button('↻ Retry Internet queue', use_container_width=True)

if next_click:
    advance_phase()
if full_click:
    remaining = 5 if st.session_state.phase == 0 or st.session_state.phase == 5 else 5-st.session_state.phase
    for _ in range(remaining):
        advance_phase()
if retry_click:
    n = st.session_state.bridge.flush()
    add_log(f'Retried Internet upload: {n} summaries delivered')

# Demo-only bulk generation: uses the same packet -> gateway -> simulated Internet -> SQLite path.
with st.expander('Bulk simulation · demonstration only'):
    st.caption('Generate a shared timeline for selected demo rooms. Every cycle represents five simulated minutes, not elapsed wall-clock time. No physical sensors are used.')
    bulk_rooms = st.multiselect('Rooms to include', list(ROOM_BASE_RH), default=list(ROOM_BASE_RH),
                                format_func=lambda rid: rid.replace('room_', 'Room '),
                                help='Select one or more rooms. Only selected rooms will receive generated summaries.')
    bulk_cycles = st.select_slider('Duration', options=[1, 12, 72, 288], value=12,
                                    format_func=lambda x: {1:'5 minutes',12:'1 hour',72:'6 hours',288:'24 hours'}[x])
    bulk_mode = st.selectbox('All-room scenario', ['normal','humid_spike','prolonged_damp','condensation'],
                             format_func=lambda x:x.replace('_',' ').title(), key='bulk_mode')
    st.caption('Default humidity: Room 101 = 64%, 102 = 73%, 103 = 84%, 104 = 91%. These are synthetic demonstration settings.')
    if st.button('▶ Generate bulk demo data', type='secondary', use_container_width=True):
        if not bulk_rooms:
            st.warning('Select at least one room for bulk generation.')
        elif st.session_state.phase not in (0,5):
            st.warning('Finish the current staged cycle first to avoid mixing packets.')
        elif not st.session_state.internet.online:
            st.warning('Turn the simulated Internet on before starting bulk generation.')
        else:
            s = st.session_state
            start = s.cloud.latest_timestamp()
            start = start + timedelta(minutes=5) if start else s.clock
            progress = st.progress(0)
            result = generate_bulk(s.bridge, bulk_rooms, bulk_cycles, bulk_mode, start,
                                   progress_callback=lambda done,total: progress.progress(done/total))
            s.clock = start + timedelta(minutes=5 * bulk_cycles)
            s.phase = 0
            s.completed_cycles += bulk_cycles
            s.gateway_processed += result['processed']
            add_log(f"Bulk demo: {bulk_cycles} cycles × {len(bulk_rooms)} rooms, "
                    f"{result['processed']} gateway summaries, {result['delivered']} delivered")
            st.success(f"Generated {result['processed']} five-minute summaries for "
                       f"{', '.join(r.replace('room_', 'Room ') for r in bulk_rooms)}. "
                       f"{result['delivered']} delivered to SQLite. Refresh the dashboard to see them.")

s = st.session_state
stage_label = STEPS[s.phase]
st.info(f'**{s.node.room_id.replace("room_", "Room")} — Step {s.phase}/5 — {stage_label}**  ·  Simulation clock: {s.clock.strftime("%Y-%m-%d %H:%M %Z")}')
components.html(render_board(
    stage=s.phase, sensor_online=s.node.online, internet_online=s.internet.online,
    latest_summary=s.latest_summary, cloud_count=s.cloud.status()['stored_summaries'],
    queue_count=len(s.bridge.pending), clock=s.clock.strftime('%H:%M')),
    height=440, scrolling=False)

m1,m2,m3,m4 = st.columns(4)
m1.metric('Sensor / ESP32', 'Online' if s.node.online else 'Offline')
m2.metric('Raspberry Pi summaries', s.gateway_processed, help='Summaries processed during manual and bulk runs in this simulator session. This is not the lifetime database count.')
m3.metric('Internet queue', len(s.bridge.pending))
m4.metric('Cloud records', s.cloud.status()['stored_summaries'])

with st.expander('Inspect data packets at each stage'):
    st.caption('Technical details are optional; most users can follow the highlighted path above.')
    st.subheader('Data as it moves through the virtual hardware')
    a,b,c = st.columns(3)
    with a:
        st.markdown('**1. ESP32 JSON payload**')
        st.json(s.latest_packet or {'status': 'Press Next stage to generate sensor packets'})
    with b:
        st.markdown('**2. Raspberry Pi 5-minute output**')
        st.json(s.latest_summary or {'status': 'Waiting for validated readings'})
    with c:
        st.markdown('**3. Internet / cloud**')
        st.json({'internet_online': s.internet.online, 'queued_summaries': len(s.bridge.pending),
                 'cloud_records': s.cloud.status()['stored_summaries'],
                 'cloud_valid_history': s.cloud.status()['valid_for_history']})

with st.expander('Simulation event log'):
    for event in s.log[:12]:
        st.write('• ' + event)

st.caption('All readings are simulated. This board stores five-minute summaries; trained-model inference happens in the separate dashboard. No mold detection.')
