"""Offline checks: run `python -m unittest test_integration.py -v`."""
import ast
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import math, random
import pandas as pd
from sensor_simulator import VirtualESP32
from edge_gateway import EdgeGateway
from network_cloud import VirtualCloud, SimulatedInternet, EdgeToCloudBridge
from ml_bridge import latest_features, HISTORY_ROWS

# Load just the pure history generator; do not import the Streamlit page.
app_source = (Path(__file__).parent / 'dashboard' / 'app.py').read_text()
parsed = ast.parse(app_source)
warm_ast = next(node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name == 'warm_history')
module = ast.fix_missing_locations(ast.Module(body=[warm_ast], type_ignores=[]))
ns = {'datetime':datetime,'timedelta':timedelta,'random':random,'math':math,'HISTORY_ROWS':HISTORY_ROWS}
exec(compile(module, '<history>', 'exec'), ns)
warm_history = ns['warm_history']

class IntegrationTests(unittest.TestCase):
    def test_warm_history_feature_contract(self):
        end = datetime(2026,8,29,23,55,tzinfo=timezone(timedelta(hours=8)))
        rows = warm_history('room_101', 73.0, end)
        self.assertEqual(len(rows), HISTORY_ROWS)
        x = latest_features(rows)
        self.assertEqual(x.shape, (1,9))
        self.assertFalse(x.isna().any().any())
        self.assertAlmostEqual(x['rh_mean_60D'].iloc[0], sum(r['rh'] for r in rows)/len(rows), places=7)
    def test_stages_transfer_to_cloud_and_keep_history_valid(self):
        end = datetime(2026,8,29,23,55,tzinfo=timezone(timedelta(hours=8)))
        history = warm_history('room_101', 73.0, end)
        cloud=VirtualCloud()
        for r in history: cloud.receive(r)
        node=VirtualESP32('room_101','esp32_room_101',base_rh=73)
        gateway=EdgeGateway()
        t=end+timedelta(minutes=5)
        for n in range(10): gateway.receive(node.read(t+timedelta(seconds=30*n)))
        bridge=EdgeToCloudBridge(SimulatedInternet(),cloud)
        self.assertTrue(bridge.send(gateway.summaries()[0]))
        self.assertEqual(len(cloud.history('room_101')), HISTORY_ROWS+1)
        self.assertEqual(latest_features(cloud.history('room_101')).shape,(1,9))
    def test_internet_queue(self):
        link=SimulatedInternet(online=False)
        cloud=VirtualCloud()
        bridge=EdgeToCloudBridge(link,cloud)
        payload={'room_id':'room_101','node_id':'esp32_room_101','timestamp':'2026-08-30T00:00:00+08:00','complete':True,'temp':27,'rh':73,'voc_resistance':42000,'source':'synthetic_sil'}
        self.assertFalse(bridge.send(payload))
        self.assertEqual(len(bridge.pending),1)
        link.online=True
        self.assertEqual(bridge.flush(),1)
        self.assertEqual(len(cloud.history('room_101')),1)

if __name__=='__main__':unittest.main()

class SharedStorageTests(unittest.TestCase):
    def test_sqlite_bridge_and_reopen(self):
        import tempfile
        import shared_store
        old=shared_store.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                shared_store.DB_PATH=Path(tmp)/'test.sqlite3'
                cloud=shared_store.SQLiteCloud()
                packet={'room_id':'room_101','node_id':'esp32_room_101',
                        'timestamp':'2026-08-30T00:00:00+08:00','complete':True,
                        'temp':27.0,'rh':83.0,'voc_resistance':40000.0,'source':'synthetic_sil'}
                bridge=EdgeToCloudBridge(SimulatedInternet(),cloud)
                self.assertTrue(bridge.send(packet))
                from_another_instance=shared_store.SQLiteCloud()
                self.assertEqual(from_another_instance.history('room_101')[-1]['rh'],83.0)
                self.assertEqual(from_another_instance.status()['stored_summaries'],1)
                self.assertEqual(from_another_instance.latest_timestamp('room_101').minute,0)
        finally:
            shared_store.DB_PATH=old

    def test_offline_does_not_publish_early(self):
        import tempfile
        import shared_store
        old=shared_store.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                shared_store.DB_PATH=Path(tmp)/'test.sqlite3'
                cloud=shared_store.SQLiteCloud()
                internet=SimulatedInternet(online=False)
                bridge=EdgeToCloudBridge(internet,cloud)
                data={'room_id':'room_101','node_id':'esp32_room_101',
                      'timestamp':'2026-08-30T00:00:00+08:00','complete':True,
                      'temp':27,'rh':83,'voc_resistance':40000,'source':'synthetic_sil'}
                self.assertFalse(bridge.send(data))
                self.assertFalse(cloud.history('room_101'))
                internet.online=True
                self.assertEqual(bridge.flush(),1)
                self.assertEqual(len(cloud.history('room_101')),1)
        finally:
            shared_store.DB_PATH=old

class RoomSelectionBulkTests(unittest.TestCase):
    def test_bulk_respects_room_selection_and_count(self):
        import tempfile
        import shared_store
        from simulation.bulk_engine import generate_bulk
        old = shared_store.DB_PATH
        try:
            with tempfile.TemporaryDirectory() as tmp:
                shared_store.DB_PATH = Path(tmp) / 'bulk_test.sqlite3'
                cloud = shared_store.SQLiteCloud()
                bridge = EdgeToCloudBridge(SimulatedInternet(), cloud)
                start = datetime(2026, 8, 30, tzinfo=timezone(timedelta(hours=8)))
                result = generate_bulk(bridge, ['room_102', 'room_104'], 3, 'normal', start)
                self.assertEqual(result, {'processed': 6, 'delivered': 6})
                self.assertEqual(len(cloud.history('room_102')), 3)
                self.assertEqual(len(cloud.history('room_104')), 3)
                self.assertEqual(len(cloud.history('room_101')), 0)
                self.assertEqual(len(cloud.history('room_103')), 0)
                self.assertEqual(cloud.status()['stored_summaries'], 6)
        finally:
            shared_store.DB_PATH = old

    def test_bulk_validation(self):
        from simulation.bulk_engine import generate_bulk
        start = datetime(2026, 8, 30, tzinfo=timezone.utc)
        bridge = EdgeToCloudBridge(SimulatedInternet(), VirtualCloud())
        with self.assertRaises(ValueError):
            generate_bulk(bridge, [], 1, 'normal', start)
        with self.assertRaises(ValueError):
            generate_bulk(bridge, ['room_999'], 1, 'normal', start)
