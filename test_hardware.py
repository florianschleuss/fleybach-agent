import copy,json,os,tempfile,time,unittest,uuid
from pathlib import Path
from unittest.mock import Mock,patch
from utils.hardware_schema import validate_source,fingerprint
from utils.hardware_drivers import read_source,IdentityMismatch,modbus_read
from utils.hardware_manager import HardwareManager

def source(**changes):
    return validate_source(dict(id=str(uuid.uuid4()),driver='sma_modbus',host='192.168.1.10',label='PV test',**changes),testing=True)

class HardwareTests(unittest.TestCase):
    def test_private_targets_and_fixed_protocol_only(self):
        for host in ('8.8.8.8','127.0.0.1','169.254.1.1','http://192.168.1.1','::1'):
            with self.assertRaises(ValueError):validate_source({**source(),'host':host},testing=True)
        with self.assertRaises(ValueError):validate_source({**source(),'driver':'shell'},testing=True)
        with self.assertRaises(ValueError):validate_source({**source(),'driver':'zendure_meter','port':8080},testing=True)
        with self.assertRaises(ValueError):validate_source({**source(),'enabled':True})

    def test_sma_identity_scaling_and_night_sentinels(self):
        values={30057:123456,30775:900,30513:12345000,30777:300,30779:300,30781:300}
        def read(s,address,words):return values[address].to_bytes(words*2,'big')
        with patch('utils.hardware_drivers.modbus_read',side_effect=read):
            verified,rows,telemetry=read_source(source())
            self.assertEqual(verified['expectedSerial'],'123456');self.assertIsNone(telemetry)
            self.assertEqual(next(row['value'] for row in rows if row['metric']=='totalProduction'),12345)
            with self.assertRaises(IdentityMismatch):read_source(source(expectedSerial='OTHER'))
            values[30775]=2147483648
            _,rows,_=read_source(source())
            self.assertFalse(any(row['metric']=='acWOut' for row in rows))

    def test_modbus_transport_can_only_issue_read_holding_registers(self):
        import struct
        sock=Mock();sock.recv.side_effect=[struct.pack('>HHHB',1,0,7,3),b'\x03\x04\x00\x00\x00\x2a']
        connection=Mock();connection.__enter__=Mock(return_value=sock);connection.__exit__=Mock(return_value=None)
        with patch('utils.hardware_drivers.socket.create_connection',return_value=connection):
            self.assertEqual(modbus_read(source(),30057,2),b'\x00\x00\x00\x2a')
        self.assertEqual(sock.sendall.call_args.args[0][7],3)

    def test_hardware_bundle_persists_without_modifying_legacy_config(self):
        from utils.site_store import apply,configuration
        from utils.site_schema import DEFAULT
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'SITE_STATE_PATH':str(Path(folder)/'site.sqlite3'),'CUSTOMER_DOMAIN':'test'}):
            plan=dict(schemaVersion=1,sources=[source(expectedSerial='123',enabled=True)])
            apply(1,DEFAULT,hardware=plan)
            self.assertEqual(configuration()['config'],DEFAULT)
            self.assertEqual(configuration()['hardware'],plan)
            with self.assertRaises(ValueError):apply(1,DEFAULT,hardware=dict(schemaVersion=1,sources=[]))

    def test_read_only_test_never_publishes_or_activates_source(self):
        manager=HardwareManager();self.addCleanup(manager.test_worker.close)
        spec=source();job=dict(id=str(uuid.uuid4()),source=spec)
        verified={**spec,'expectedSerial':'123'};rows=[dict(metric='acWOut',unit='W',value=900,sampledAt=time.time())]
        with patch('utils.hardware_manager.read_source',return_value=(verified,rows,None)),patch('utils.hardware_manager.publish') as publish:
            manager.queue_tests([job])
            deadline=time.monotonic()+2
            while not manager.outgoing() and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(manager.outgoing()[0]['ok']);publish.assert_not_called()
            self.assertEqual(manager.running,{})

if __name__=='__main__':unittest.main(verbosity=2)
