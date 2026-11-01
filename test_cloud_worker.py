import ast
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from utils.cloud_worker import CloudWorker
from utils.sensor_upload import SensorUploader


class StopPolling(BaseException): pass


class CloudTests(unittest.TestCase):
    def test_hung_cloud_never_blocks_producer_and_only_latest_pending_sample_is_sent(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();received=[]
        worker=CloudWorker('test',capacity=1,retry_seconds=.01)
        self.addCleanup(worker.close);self.addCleanup(release.set)
        def blocked():
            entered.set();release.wait(5);return True
        worker.submit('snapshot',blocked)
        self.assertTrue(entered.wait(1))
        start=time.monotonic()
        for value in range(1000):
            worker.submit('snapshot',lambda x=value: (received.append(x),done.set(),True)[-1])
        self.assertLess(time.monotonic()-start,1)
        self.assertEqual(len(worker._pending),1)
        release.set();self.assertTrue(done.wait(1));self.assertEqual(received,[999])

    def test_failures_retry_and_recovery_is_observed(self):
        done=threading.Event();states=[];attempts=[]
        def action():
            attempts.append(1)
            if len(attempts)==1:raise TimeoutError()
            return True
        def observe(failed):
            states.append(failed)
            if not failed:done.set()
        worker=CloudWorker('retry-test',retry_seconds=.01,observer=observe)
        self.addCleanup(worker.close);worker.submit('sample',action)
        self.assertTrue(done.wait(2));self.assertEqual(states,[True,False])

    def test_expired_pending_sample_is_not_uploaded(self):
        entered=threading.Event();release=threading.Event();done=threading.Event();expired=Mock()
        worker=CloudWorker('expiry-test',capacity=3)
        self.addCleanup(worker.close);self.addCleanup(release.set)
        worker.submit('block',lambda:(entered.set(),release.wait(2),True)[-1])
        self.assertTrue(entered.wait(1));worker.submit('old',expired,max_age=-1)
        worker.submit('fresh',lambda:(done.set(),True)[-1]);release.set()
        self.assertTrue(done.wait(1));expired.assert_not_called()

    def test_real_power_polling_keeps_sampling_while_cloud_callback_hangs(self):
        entered=threading.Event();release=threading.Event();samples=[]
        worker=CloudWorker('power-test',capacity=1)
        self.addCleanup(worker.close);self.addCleanup(release.set)
        def upload(rows):entered.set();release.wait(3);return True
        count=[0]
        def read(name):
            count[0]+=1;samples.append(count[0]);return dict(value=count[0],unit='W',type='power')
        def sleep(_):
            self.assertTrue(entered.wait(1))
            if count[0]>=4:raise StopPolling()
        tree=ast.parse(Path('power/power.py').read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='update_loop')
        sensor=SimpleNamespace(enabled=True,on_timeout=lambda:False,name='solar',device_id='solar',type='power')
        sml=SimpleNamespace(get_energy_data=lambda:SimpleNamespace(to_dict=lambda:{'total':1},sampled_at=time.time()))
        scope=dict(Dict=dict,List=list,config=SimpleNamespace(sensors=[sensor]),sml_parser=sml,
            time=SimpleNamespace(time=time.time,monotonic=time.monotonic,sleep=sleep),
            get_inverter_data=read,cloud_upload=worker,upload_snapshot=upload,REFRESH_TIME_SECONDS=10,logger=Mock())
        exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_power_loop','exec'),scope)
        with self.assertRaises(StopPolling):scope['update_loop']()
        self.assertEqual(samples,[1,2,3,4])

    def test_sensor_upload_preserves_wire_values_and_excludes_expired_samples(self):
        auth=SimpleNamespace(v=Mock(),token=SimpleNamespace(_token='test-only',exp=time.time()+3600,customer_id='fixture'))
        uploader=SensorUploader(auth,'api.example.invalid');uploader.session=Mock()
        uploader.session.patch.return_value.status_code=200
        sample=dict(id='water',name='water',unit='°C',type='temperature',value=14.5,sampledAt=time.time())
        self.assertTrue(uploader.upload([sample,{**sample,'id':'old','sampledAt':time.time()-120}]))
        self.assertEqual(uploader.session.patch.call_count,2)
        batch=uploader.session.patch.call_args.kwargs
        self.assertEqual(batch['json'],{'sensors':[dict(id='water',name='water',value=14.5)]})
        self.assertEqual(batch['timeout'],(3,8))
        self.assertNotIn('sampledAt',str(batch['json']))

    def test_real_temperature_polling_keeps_sampling_while_upload_is_blocked(self):
        entered=threading.Event();release=threading.Event();count=[0]
        worker=CloudWorker('temperature-test',capacity=1)
        self.addCleanup(worker.close);self.addCleanup(release.set)
        def upload(rows):entered.set();release.wait(3);return True
        sensor=SimpleNamespace(enabled=True,serial_connected=True,device_id='water',
            name='water',unit='°C',type='temperature',last_updated=time.time())
        def read():
            count[0]+=1;sensor.last_updated=time.time()
            return [dict(id='water',value=14+count[0])]
        def sleep(_):
            self.assertTrue(entered.wait(1))
            if count[0]>=4:raise StopPolling()
        tree=ast.parse(Path('temperature/temperature.py').read_text(encoding='utf-8'))
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='update_loop')
        from datetime import datetime
        scope=dict(datetime=datetime,List=list,Dict=dict,config=SimpleNamespace(sensors=[sensor],get_sensor=lambda _:sensor),
            update_temperature_by_serial=read,time=SimpleNamespace(sleep=sleep),
            cloud_upload=worker,upload_snapshot=upload,REFRESH_TIME_SECONDS=10,logger=Mock())
        exec(compile(ast.Module(body=[function],type_ignores=[]),'actual_temperature_loop','exec'),scope)
        with self.assertRaises(StopPolling):scope['update_loop']()
        self.assertEqual(count[0],4)

    def test_catalog_native_identity_and_custom_labels_are_preserved(self):
        from utils.site_catalog import catalog,default_label
        self.assertEqual(catalog()['schemaVersion'],1)
        self.assertEqual(default_label('water'),'Poolwasser')
        self.assertEqual(default_label('water','Mein Pool'),'Mein Pool')
        self.assertEqual(default_label('soc','Batterie 1 · soc'),'Batterie 1 · Ladestand')


if __name__=='__main__':unittest.main(verbosity=2)
