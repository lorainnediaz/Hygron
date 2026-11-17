"""Pure demo batch simulation, intentionally independent of Streamlit UI."""
from datetime import timedelta
from edge_gateway import EdgeGateway
from sensor_simulator import VirtualESP32

ROOM_BASE_RH = {'room_101': 64, 'room_102': 73, 'room_103': 84, 'room_104': 91}


def generate_bulk(bridge, room_ids, cycles, scenario, start, progress_callback=None):
    """Generate five-minute summaries for ONLY selected rooms via the gateway/bridge path.

    Caller must ensure that the simulated Internet is online. Each successful
    bridge.send delivers to SQLite; processed is the count of Pi summaries.
    """
    room_ids = list(dict.fromkeys(room_ids))
    if not room_ids or any(r not in ROOM_BASE_RH for r in room_ids):
        raise ValueError('Select one or more valid room IDs')
    if cycles < 1:
        raise ValueError('cycles must be positive')
    if start.tzinfo is None:
        raise ValueError('start must be timezone-aware')
    nodes = {rid: VirtualESP32(rid, f'esp32_{rid}', base_rh=ROOM_BASE_RH[rid],
                              seed=100 + list(ROOM_BASE_RH).index(rid)) for rid in room_ids}
    for node in nodes.values():
        node.set_scenario(scenario, start=start, duration_hours=max(1, cycles / 12))
    processed = delivered = 0
    for n in range(cycles):
        tick = start + timedelta(minutes=5 * n)
        gateway = EdgeGateway()
        for node in nodes.values():
            for i in range(10):
                gateway.receive(node.read(tick + timedelta(seconds=30 * i)))
        for summary in gateway.summaries():
            processed += 1
            if bridge.send(summary):
                delivered += 1
        if progress_callback and (n % 12 == 0 or n == cycles - 1):
            progress_callback(n + 1, cycles)
    return {'processed': processed, 'delivered': delivered}
