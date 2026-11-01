"""Autonomous source polling; the VPS only distributes desired config/tests."""
import copy,json,os,threading,time,uuid
from pathlib import Path
from utils.hardware_drivers import read_source,IdentityMismatch
from utils.hardware_schema import validate_source
from utils.site_store import publish,configuration
from utils.cloud_worker import CloudWorker
from utils.sensor_upload import SensorUploader

class HardwareManager:
    def __init__(self):
        self.lock=threading.Lock();self.running={};self.status={};self.results={};self.tests=set()
        self.test_worker=CloudWorker('hardware-tests',capacity=8)

    def legacy_sources(self):
        result=[]
        path=os.environ.get('SITE_ZENDURE_CONFIG')
        if path and Path(path).exists():
            data=json.loads(Path(path).read_text())
            for source in data.get('sources',[]):
                if not source.get('enabled',True):continue
                driver='zendure_battery' if source['kind']=='battery' else 'zendure_meter'
                result.append(validate_source(dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,driver+source['expectedSerial'])),
                    driver=driver,label=source['label'],host=source['host'],expectedSerial=source['expectedSerial'],enabled=True),testing=True))
        host=os.environ.get('SMA_MODBUS_IP')
        if host:
            result.append(validate_source(dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL,'sma:'+host)),driver='sma_modbus',
                label='Bestehender SMA Wechselrichter',host=host,port=int(os.environ.get('SMA_MODBUS_PORT','502')),enabled=True),testing=True))
        return result

    def report(self):
        with self.lock:return dict(schemaVersion=1,legacySources=self.legacy_sources(),sources=copy.deepcopy(self.status))

    def outgoing(self):
        with self.lock:return list(copy.deepcopy(self.results).values())[:8]

    def acknowledge(self,results):
        with self.lock:
            for result in results:self.results.pop(result['id'],None)

    def queue_tests(self,tasks):
        for task in tasks:
            with self.lock:
                if task['id'] in self.tests:continue
                self.tests.add(task['id'])
                if len(self.tests)>256:self.tests={task['id'],*self.results.keys()}
            def execute(job=task):
                try:
                    source,readings,_=read_source(job['source'])
                    result=dict(id=job['id'],ok=True,code='ok',source=source,readings=readings)
                except Exception as exc:
                    result=dict(id=job['id'],ok=False,code='identity_mismatch' if isinstance(exc,IdentityMismatch) else 'connection_failed')
                with self.lock:self.results[job['id']]=result
                return True
            self.test_worker.submit(task['id'],execute,max_age=150)

    def reconcile(self):
        sources=configuration().get('hardware',{}).get('sources',[])
        desired={source['id']:source for source in sources if source.get('enabled')}
        with self.lock:
            for key,(old,stop,_) in list(self.running.items()):
                if key not in desired or old!=desired[key]:stop.set()
            for key,source in desired.items():
                old=self.running.get(key)
                if old and old[2].is_alive():continue
                stop=threading.Event()
                worker=threading.Thread(target=self._poll,args=(copy.deepcopy(source),stop),name='hardware-'+key,daemon=True)
                self.running[key]=(copy.deepcopy(source),stop,worker);worker.start()

    def _poll(self,source,stop):
        from utils.auth import JWTValidator
        auth=JWTValidator(os.environ['AUTH_URL'],os.environ['CUSTOMER_DOMAIN'],os.environ['CUSTOMER_SECRET'])
        uploader=SensorUploader(auth,os.environ['AUTH_URL'])
        cloud=CloudWorker('hardware-upload-'+source['id'],capacity=1)
        def upload(rows,telemetry):
            if telemetry:
                auth.v();token=auth.token
                if not token._token or token.exp<=time.time():raise ConnectionError('Authentication unavailable')
                response=uploader.session.post(uploader.base+'/sensor/telemetry/zendure',params={'customer_id':token.customer_id},
                    headers={'x-access-token':token._token},json=telemetry,timeout=(3,8))
                if response.status_code==401:token.exp=0
                response.raise_for_status()
            else:
                if not uploader.upload(rows):return False
                token=auth.token
                response=uploader.session.post(uploader.base+'/sensor/sensors/names/history',params={'customer_id':token.customer_id},
                    headers={'x-access-token':token._token},json={'names':[row['name'] for row in rows]},timeout=(3,8))
                response.raise_for_status()
            return True
        try:
            while not stop.is_set():
                start=time.monotonic()
                try:
                    _,readings,telemetry=read_source(source)
                    if stop.is_set():break
                    rows=[]
                    from utils.site_catalog import measurement_name
                    for reading in readings:
                        identifier='hw:'+source['id']+':'+reading['metric']
                        publish(identifier,reading['metric'],reading['unit'],reading['value'],reading['sampledAt'],'hardware',
                            label=source['label']+' · '+measurement_name(reading['metric']))
                        rows.append(dict(id=identifier,name='hw_'+source['id'].replace('-','')+'_'+reading['metric'],unit=reading['unit'],
                            value=reading['value'],sampledAt=reading['sampledAt'],type='site_hardware'))
                    cloud.submit('snapshot',lambda snapshot=rows,payload=telemetry:upload(snapshot,payload))
                    with self.lock:self.status[source['id']]=dict(ok=True,sampledAt=max(r['sampledAt'] for r in readings))
                except Exception:
                    with self.lock:self.status[source['id']]=dict(ok=False,sampledAt=self.status.get(source['id'],{}).get('sampledAt',0))
                stop.wait(max(.1,source['intervalSeconds']-(time.monotonic()-start)))
        finally:cloud.close()

    def run(self):
        while True:
            try:self.reconcile()
            except Exception:pass
            time.sleep(2)
