"""Fixed, read-only network adapters. No user-supplied URLs/register writes."""
import json,socket,struct,time
import requests
from utils.hardware_schema import validate_source
from utils.zendure import normalize
from utils.site_catalog import catalog

class IdentityMismatch(ValueError):pass

def _exact(sock,count):
    result=b''
    while len(result)<count:
        part=sock.recv(count-len(result))
        if not part:raise ConnectionError('Incomplete Modbus response')
        result+=part
    return result

def modbus_read(source,address,words):
    transaction=1
    request=struct.pack('>HHHBBHH',transaction,0,6,source['unitId'],3,address,words)
    with socket.create_connection((source['host'],source['port']),timeout=3) as sock:
        sock.settimeout(3);sock.sendall(request)
        tx,protocol,length,unit=struct.unpack('>HHHB',_exact(sock,7))
        if (tx,protocol,unit)!=(transaction,0,source['unitId']) or not 3<=length<=253:raise ValueError('Invalid Modbus header')
        payload=_exact(sock,length-1)
        if payload[:2]!=bytes([3,words*2]) or len(payload)!=2+words*2:raise ValueError('Unsupported Modbus response')
        return payload[2:]

def read_source(raw):
    source=validate_source(raw,testing=True)
    if source['driver'].startswith('zendure_'):
        session=requests.Session();session.trust_env=False
        try:
            with session.get('http://'+source['host']+'/properties/report',timeout=(3,5),allow_redirects=False,stream=True) as response:
                response.raise_for_status()
                if response.status_code!=200:raise ValueError('Unexpected response')
                body=bytearray()
                for part in response.iter_content(chunk_size=4096):
                    body.extend(part)
                    if len(body)>60000:raise ValueError('Report too large')
            report=json.loads(body);parsed=normalize(report)
        finally:session.close()
        wanted='battery' if source['driver']=='zendure_battery' else 'smart_meter'
        if parsed['kind']!=wanted:raise IdentityMismatch('Different device type')
        serial=parsed['serial']
        readings=[dict(metric=key,unit=metric['unit'],value=metric['value'],sampledAt=report['timestamp'])
                  for key,metric in parsed['metrics'].items()]
        upload={'report':report,'label':source['label'],'staleAfterSeconds':60}
    else:
        serial_value=int.from_bytes(modbus_read(source,30057,2),'big')
        if serial_value in (0,4294967295,4294967293):raise ValueError('No valid device identity')
        serial=str(serial_value)
        readings=[]
        for name,definition in catalog()['hardwareDrivers']['sma_modbus']['measurements'].items():
            raw_value=modbus_read(source,definition['address'],definition['words'])
            value=int.from_bytes(raw_value,'big',signed=definition.get('signed',False))
            if value in (-2147483648,4294967295,18446744073709551615):continue
            readings.append(dict(metric=name,unit=definition['unit'],value=value*definition.get('scale',1),sampledAt=time.time()))
        upload=None
    if source['expectedSerial'] and source['expectedSerial']!=serial:raise IdentityMismatch('Different device identity')
    if not readings or not any(time.time()-reading['sampledAt']<60 for reading in readings):raise ValueError('No fresh usable measurements')
    source['expectedSerial']=serial
    return source,readings,upload
