"""Hygron interactive Wokwi-style SIL board. Run: python -m streamlit run app.py"""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st

from simulation.board_widget import hygron_board
from sensor_simulator import VirtualESP32
from edge_gateway import EdgeGateway
from network_cloud import SimulatedInternet, EdgeToCloudBridge
from shared_store import SQLiteCloud
from simulation.bulk_engine import ROOM_BASE_RH, generate_bulk

st.set_page_config(page_title="Hygron Virtual Breadboard", layout="wide")


def reset_state():
    """Reset the walkthrough, not previously delivered SQLite history."""
    selected = st.session_state.get("selected_room", "room_101")
    sensor_online = st.session_state.get('sensor_online_toggle', True)
    internet_online = st.session_state.get('internet_online_toggle', True)
    st.session_state.node = VirtualESP32(selected, f"esp32_{selected}", base_rh=ROOM_BASE_RH[selected],
                                         online=sensor_online)
    st.session_state.gateway = EdgeGateway()  # virtual Raspberry Pi
    st.session_state.internet = SimulatedInternet(online=internet_online)
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
    st.session_state.walkthrough_step = 0
    st.session_state.autoplay = False


if 'node' not in st.session_state:
    reset_state()
if 'walkthrough_step' not in st.session_state:
    st.session_state.walkthrough_step = 0
if 'autoplay' not in st.session_state:
    st.session_state.autoplay = False
if 'board_fullscreen' not in st.session_state:
    st.session_state.board_fullscreen = False
if 'sensor_online_toggle' not in st.session_state:
    st.session_state.sensor_online_toggle = st.session_state.node.online
if 'internet_online_toggle' not in st.session_state:
    st.session_state.internet_online_toggle = st.session_state.internet.online
if '_board_internet_toggle_pending' in st.session_state:
    st.session_state.internet_online_toggle = st.session_state['_board_internet_toggle_pending']
    del st.session_state['_board_internet_toggle_pending']


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


@st.dialog('Bulk simulation · demonstration only', width='large')
def bulk_simulation_dialog():
    s = st.session_state
    st.caption('Generate a shared timeline for selected demo rooms. Each cycle represents five simulated minutes. No physical sensors are used.')
    bulk_rooms = st.multiselect('Rooms to include', list(ROOM_BASE_RH), default=list(ROOM_BASE_RH),
                                format_func=lambda rid: rid.replace('room_', 'Room '),
                                help='Only selected rooms receive generated summaries.')
    bulk_cycles = st.select_slider('Duration', options=[1, 12, 72, 288], value=12,
                                   format_func=lambda x: {1:'5 minutes',12:'1 hour',72:'6 hours',288:'24 hours'}[x])
    bulk_mode = st.selectbox('Environment scenario', ['normal','humid_spike','prolonged_damp','condensation'],
                             format_func=lambda x:x.replace('_',' ').title(), key='bulk_mode')
    st.caption('Default room humidity: 101 = 64%, 102 = 73%, 103 = 84%, 104 = 91%.')
    if st.button('Generate bulk demo data', type='primary', use_container_width=True):
        if not bulk_rooms:
            st.warning('Select at least one room for bulk generation.')
        elif s.phase not in (0,5):
            st.warning('Finish the current staged cycle first to avoid mixing packets.')
        elif not s.internet.online:
            st.warning('Turn the simulated Internet on before starting bulk generation.')
        else:
            start = s.cloud.latest_timestamp()
            start = start + timedelta(minutes=5) if start else s.clock
            progress = st.progress(0)
            result = generate_bulk(s.bridge, bulk_rooms, bulk_cycles, bulk_mode, start,
                                   progress_callback=lambda done,total: progress.progress(done/total))
            s.clock = start + timedelta(minutes=5 * bulk_cycles)
            s.phase = 0
            s.walkthrough_step = 0
            s.autoplay = False
            s.completed_cycles += bulk_cycles
            s.gateway_processed += result['processed']
            add_log(f"Bulk demo: {bulk_cycles} cycles × {len(bulk_rooms)} rooms, "
                    f"{result['processed']} gateway summaries, {result['delivered']} delivered")
            st.success(f"Generated {result['processed']} five-minute summaries for "
                       f"{', '.join(r.replace('room_', 'Room ') for r in bulk_rooms)}. "
                       f"{result['delivered']} delivered to SQLite.")


@st.dialog('Inspect data packets at each stage', width='large')
def packet_inspector_dialog():
    s = st.session_state
    st.caption('Inspect the readings, Raspberry Pi summary, and transmission state from the current walkthrough.')
    a, b, c = st.columns(3)
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


@st.dialog('Simulation event log')
def event_log_dialog():
    events = st.session_state.log[:25]
    if events:
        for event in events:
            st.write('• ' + event)
    else:
        st.caption('No simulation events yet.')


st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Aptos', 'Segoe UI', Arial, sans-serif;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #efe6d6;
    color: #234f45;
}
[data-testid="stSidebar"] {
    background: #2c2c2e;
    color: #f5f5f7;
}
[data-testid="stSidebar"] * { color: #f5f5f7; }
[data-testid="stHeader"] {
    background: rgba(239, 230, 214, .96);
}
[data-testid="stHeader"] button { color: #2f6652 !important; }
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {
    color: #2f6652;
}
[data-testid="stMain"] h1 {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 2rem;
    color: #c8603f;
    margin: .35rem 0 .75rem;
    width: 100%;
    padding-inline: 28px;
    box-sizing: border-box;
}
[data-testid="stMain"] h2 { color: #2f6652; }
[data-testid="stMain"] p, [data-testid="stMain"] label,
[data-testid="stMain"] [data-testid="stMetricLabel"] { color: #345e53; }
[data-testid="stMain"] [data-testid="stMetricValue"] { color: #286557; }
[data-testid="stMain"] [data-testid="stExpander"] {
    background: #fffefa;
    border: 1px solid #d4c8b3;
    border-radius: 12px;
}
[data-testid="stStatusWidget"],
[data-testid="stFooter"], footer { visibility: hidden !important; height: 0 !important; }
[data-testid="stMain"] .block-container { padding: 1rem; max-width: 100%; box-sizing:border-box; overflow-x:hidden; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow-x:hidden !important; }
[data-testid="stDialog"] section[role="dialog"] {
    width: min(90vw, 900px) !important;
    max-width: 900px !important;
    max-height: 88vh !important;
    overflow-y: auto !important;
    border: 1px solid #d4c8b3 !important;
    border-radius: 18px !important;
    background: #fffefa !important;
    color: #284b40 !important;
    box-shadow: 0 18px 48px rgba(40, 55, 45, .24) !important;
}
[data-testid="stDialog"] { background: rgba(40, 75, 64, .28) !important; backdrop-filter: blur(2px); }
[data-testid="stDialog"] section[role="dialog"] h1,
[data-testid="stDialog"] section[role="dialog"] h2,
[data-testid="stDialog"] section[role="dialog"] h3 { color: #2f6652 !important; }
[data-testid="stDialog"] section[role="dialog"] p,
[data-testid="stDialog"] section[role="dialog"] label,
[data-testid="stDialog"] section[role="dialog"] [data-testid="stMarkdownContainer"] { color: #526d61 !important; }
[data-testid="stDialog"] section[role="dialog"] input,
[data-testid="stDialog"] section[role="dialog"] textarea,
[data-testid="stDialog"] section[role="dialog"] [role="combobox"] {
    background: #fffefa !important;
    color: #284b40 !important;
    border-color: #d4c8b3 !important;
}
[data-testid="stDialog"] section[role="dialog"] [data-testid="stVerticalBlock"] { gap: .8rem; }
[data-testid="stDialog"] [data-testid="stBaseButton-primary"],
[data-testid="stDialog"] button[kind="primary"] {
    background: #c8603f !important;
    border-color: #c8603f !important;
    color: #fffefa !important;
}
[data-testid="stDialog"] [data-testid="stBaseButton-primary"]:hover,
[data-testid="stDialog"] button[kind="primary"]:hover {
    background: #984329 !important;
    border-color: #984329 !important;
}
[data-testid="stDialog"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #c8603f !important;
    color: #fffefa !important;
}
[data-testid="stDialog"] [data-testid="stMultiSelect"] [data-baseweb="tag"] * { color: #fffefa !important; }
[data-testid="stDialog"] [data-testid="stSlider"] [role="slider"] {
    background-color: #c8603f !important;
    border-color: #c8603f !important;
}
[data-testid="stDialog"] [data-testid="stSlider"] [data-baseweb="slider"] > div:first-child > div {
    background-color: #c8603f !important;
}
[data-testid="stDialog"] [data-testid="stSlider"] [data-baseweb="slider"] * { --slider-color: #c8603f; }
/* Global orange accents for Streamlit controls, including the sidebar. */
:root, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
    --primary-color: #c8603f !important;
    --primaryColor: #c8603f !important;
    accent-color: #c8603f !important;
}
[data-baseweb="tag"] { background-color: #c8603f !important; color: #fffefa !important; }
[data-baseweb="tag"] * { color: #fffefa !important; }
[role="group"]:has(> button[aria-label^="Remove "]) {
    border-radius: 7px !important;
    background: #c8603f !important;
    color: #fffefa !important;
}
[role="group"]:has(> button[aria-label^="Remove "]) * { color: #fffefa !important; }
[role="slider"] { accent-color: #c8603f !important; }
[data-testid="stSlider"] [role="slider"] {
    background-color: #c8603f !important;
    border-color: #c8603f !important;
}
[data-baseweb="slider"] [role="slider"] {
    background-color: #c8603f !important;
    border-color: #c8603f !important;
    box-shadow: 0 0 0 2px rgba(200, 96, 63, .2) !important;
}
[data-baseweb="slider"] [aria-hidden="true"] { background-color: #c8603f !important; }
[data-baseweb="slider"] [aria-hidden="true"]::before,
[data-baseweb="slider"] [aria-hidden="true"]::after { background-color: #c8603f !important; }
[data-baseweb="slider"] div[style*="width"] { background-color: #c8603f !important; }
[data-baseweb="slider"] > div > div:first-child > div,
[data-baseweb="slider"] > div > div > div:first-child { background-color: #c8603f !important; }
[role="switch"][aria-checked="true"],
[data-testid="stToggle"] [role="switch"][aria-checked="true"],
[data-testid="stSidebar"] [role="switch"][aria-checked="true"] {
    background-color: #c8603f !important;
    border-color: #c8603f !important;
}
[role="switch"][aria-checked="true"] > div,
[data-testid="stToggle"] [role="switch"] > div,
[data-testid="stSidebar"] [role="switch"] > div { background-color: #fffefa !important; }
[data-baseweb="select"]:focus-within > div,
[data-baseweb="input"]:focus-within,
[data-baseweb="textarea"]:focus-within { border-color: #c8603f !important; }
[role="option"][aria-selected="true"] { background-color: #f7e8df !important; color: #984329 !important; }
[data-testid="stBaseButton-primary"], button[kind="primary"] {
    background: #c8603f !important;
    border-color: #c8603f !important;
    color: #fffefa !important;
}
[data-testid="stBaseButton-primary"] *, button[kind="primary"] * { color: #fffefa !important; }
[data-testid="stBaseButton-primary"]:hover, button[kind="primary"]:hover {
    background: #984329 !important;
    border-color: #984329 !important;
}
[data-testid="stSidebar"] button:not([role="switch"]) {
    background: #353538 !important;
    border: 1px solid #56565b !important;
    color: #f5f5f7 !important;
}
[data-testid="stSidebar"] button:not([role="switch"]):hover { background: #444448 !important; }
[data-testid="stSidebar"] button:not([role="switch"]) * { color: #f5f5f7 !important; }
[data-testid="stSidebar"] [role="combobox"],
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #353538 !important;
    border-color: #56565b !important;
    color: #f5f5f7 !important;
}
[data-testid="stSidebar"] [role="combobox"] *,
[data-testid="stSidebar"] [data-baseweb="select"] * { color: #f5f5f7 !important; }
[data-testid="stDialog"] [data-testid="stBaseButton-primary"] *,
[data-testid="stDialog"] button[kind="primary"] * { color: #fffefa !important; }
[data-testid="stDialog"] section[role="dialog"] [data-testid="stBaseButton-primary"] p,
[data-testid="stDialog"] section[role="dialog"] button[kind="primary"] p {
    color: #fffefa !important;
}
</style>
""", unsafe_allow_html=True)
if not st.session_state.board_fullscreen:
    st.title('Hygron Virtual Breadboard')

def change_room():
    """Switch the active virtual ESP32 without erasing cloud data or queued uploads."""
    s = st.session_state
    rid = s.selected_room
    s.node = VirtualESP32(rid, f'esp32_{rid}', base_rh=ROOM_BASE_RH[rid],
                          online=s.get('sensor_online_toggle', True))
    s.phase = 0
    s.walkthrough_step = 0
    s.autoplay = False
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
    sensor_online = st.toggle(
        'ESP32 / sensor online', key='sensor_online_toggle',
        help='When off, generated packets have no valid readings and the Raspberry Pi marks the five-minute interval incomplete. Turning it on affects future sensor reads; readings already generated are preserved.'
    )
    was_internet_online = st.session_state.internet.online
    internet_online = st.toggle(
        'Simulated Internet online', key='internet_online_toggle',
        help='When off, the transmission queue keeps summaries pending. Turning it on automatically retries delivery to SQLite.'
    )
    st.session_state.node.online = sensor_online
    st.session_state.internet.online = internet_online
    if internet_online and not was_internet_online and st.session_state.bridge.pending:
        delivered = st.session_state.bridge.flush()
        st.session_state.delivered_last = delivered
        add_log(f'Internet reconnected; delivered {delivered} queued summary/s to SQLite')
    st.session_state.node.set_scenario(scenario, start=st.session_state.clock, duration_hours=48)
    st.slider('Room base relative humidity (%)', 40, 95, int(st.session_state.node.base_rh), key='base_rh_widget')
    st.session_state.node.base_rh = float(st.session_state.base_rh_widget)
    st.slider('Room base temperature (°C)', 18, 36, int(st.session_state.node.base_temp), key='base_temp_widget')
    st.session_state.node.base_temp = float(st.session_state.base_temp_widget)
    st.divider()
    if st.button('Reset simulation', use_container_width=True):
        reset_state()
        st.rerun()
    st.caption('Sensor outages mark summaries incomplete. Internet outages retain queued summaries; reconnecting delivers them automatically.')
    st.divider()
    st.subheader('Tools & data')
    if st.button('Bulk simulation', use_container_width=True):
        bulk_simulation_dialog()
    if st.button('Inspect data packets', use_container_width=True):
        packet_inspector_dialog()
    if st.button('Simulation event log', use_container_width=True):
        event_log_dialog()

def handle_board_action(event):
    if not isinstance(event, dict) or not event.get('nonce'):
        return
    if event['nonce'] == st.session_state.get('_last_board_action_nonce'):
        return
    st.session_state._last_board_action_nonce = event['nonce']
    if event.get('action') == 'next':
        step = st.session_state.walkthrough_step
        next_step = 1 if step >= 6 else step + 1
        phase_for_step = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
        if (step == 6 and next_step == 1) or st.session_state.phase < phase_for_step[next_step]:
            advance_phase()
        st.session_state.walkthrough_step = next_step
    elif event.get('action') == 'previous':
        st.session_state.walkthrough_step = max(0, st.session_state.walkthrough_step - 1)
    elif event.get('action') == 'toggle_play':
        st.session_state.autoplay = not st.session_state.autoplay
    elif event.get('action') == 'full':
        remaining = 5 if st.session_state.phase in (0, 5) else 5-st.session_state.phase
        for _ in range(remaining):
            advance_phase()
        st.session_state.walkthrough_step = 6
        st.session_state.autoplay = False
    elif event.get('action') == 'retry':
        delivered = st.session_state.bridge.flush()
        add_log(f'Retried Internet upload: {delivered} summaries delivered')
    elif event.get('action') == 'toggle_internet':
        st.session_state._board_internet_toggle_pending = not st.session_state.internet.online
    elif event.get('action') == 'reset':
        reset_state()
    elif event.get('action') == 'fullscreen':
        st.session_state.board_fullscreen = True
    elif event.get('action') == 'exit_fullscreen':
        st.session_state.board_fullscreen = False


def render_board_component(component_key, fullscreen=False):
    s = st.session_state
    cloud_status = s.cloud.status()
    latest_stored_timestamp = s.cloud.latest_timestamp()
    return hygron_board(
        stage=s.phase,
        walkthrough_step=s.walkthrough_step,
        autoplay=s.autoplay,
        fullscreen=fullscreen,
        room_id=s.node.room_id,
        node_id=s.node.node_id,
        clock=s.clock.strftime('%Y-%m-%d %H:%M %Z'),
        sensor_online=s.node.online,
        internet_online=s.internet.online,
        latest_packet=s.latest_packet,
        latest_summary=s.latest_summary,
        gateway_count=s.gateway_processed,
        queue_count=len(s.bridge.pending),
        queue_records=[dict(row) for row in s.bridge.pending[:4]],
        uploaded_count=s.bridge.uploaded,
        cloud_count=cloud_status['stored_summaries'],
        valid_cloud_count=cloud_status['valid_for_history'],
        latest_stored_timestamp=(latest_stored_timestamp.isoformat(timespec='seconds')
                                 if latest_stored_timestamp else None),
        key=component_key,
        height=900 if fullscreen else 1080,
        scrolling=False,
    )


if st.session_state.board_fullscreen:
    st.markdown('''<style>
    body { overflow:hidden !important; }
    [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stToolbar"] { display:none !important; }
    iframe[data-testid="stCustomComponentV1"] { position:fixed !important; inset:0 !important; z-index:2147483000 !important; width:100vw !important; height:100vh !important; max-width:none !important; margin:0 !important; border:0 !important; }
    </style>''', unsafe_allow_html=True)
board_action = render_board_component('hygron_board', fullscreen=st.session_state.board_fullscreen)
if isinstance(board_action, dict) and board_action.get('nonce') != st.session_state.get('_last_board_action_nonce'):
    handle_board_action(board_action)
    st.rerun()
if not st.session_state.board_fullscreen:
    st.subheader('Frequently asked questions')
    with st.expander('How does clicking Simulate move the data?'):
        st.write('A virtual BME680 reading is packaged by ESP32 every 30 seconds. The Raspberry Pi combines 10 readings into a five-minute summary. The summary enters a simulated Internet queue, reaches shared SQLite storage if connected, and can then be read by the separate dashboard after refresh. Each Next stage button runs just one part of that journey.')
    with st.expander('Why not run this entirely in Wokwi?'):
        st.write('Wokwi focuses on microcontroller and circuit emulation. This prototype also needs a custom five-minute gateway aggregation, simulated transport queue and SQLite-backed cloud storage, plus a trained-model dashboard. This interactive board represents all stages together in one Python simulation; its drawn devices are not real hardware or a claim of full Wokwi hardware emulation.')
