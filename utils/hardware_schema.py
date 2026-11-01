"""Additive source configuration; never part of the strict legacy config v1."""
import hashlib,ipaddress,json,re,uuid

from utils.site_catalog import catalog
DRIVERS={key:value['label'] for key,value in catalog()['hardwareDrivers'].items()}

def validate_source(raw, *, testing=False):
    if not isinstance(raw,dict) or set(raw)-{'id','driver','label','host','port','unitId','expectedSerial','intervalSeconds','enabled','role'}:
        raise ValueError('Ungültige Anschlussdaten')
    source=dict(raw)
    source['id']=str(uuid.UUID(source.get('id') or str(uuid.uuid4())))
    if source.get('driver') not in DRIVERS:raise ValueError('Nicht unterstützte Anschlussart')
    address=ipaddress.ip_address(source.get('host',''))
    if address.version!=4 or not any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('Eine lokale IPv4-Adresse des Geräts eingeben')
    source['host']=str(address)
    if not isinstance(source.get('label'),str) or not 1<=len(source['label'].strip())<=120:raise ValueError('Name erforderlich (maximal 120 Zeichen)')
    source['label']=source['label'].strip()
    source.setdefault('port',502 if source['driver']=='sma_modbus' else 80)
    source.setdefault('unitId',3);source.setdefault('intervalSeconds',10);source.setdefault('enabled',False)
    for key,low,high in [('port',1,65535),('unitId',1,247),('intervalSeconds',5,300)]:
        if type(source[key]) is not int or not low<=source[key]<=high:raise ValueError('Ungültiger Wert für '+key)
    if source['driver']!='sma_modbus' and source['port']!=80:raise ValueError('Zendure verwendet Port 80')
    if type(source['enabled']) is not bool:raise ValueError('Ungültige Aktivierung')
    serial=source.get('expectedSerial','')
    if not isinstance(serial,str) or (serial and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',serial)):raise ValueError('Ungültige Seriennummer')
    if not testing and source['enabled'] and not serial:raise ValueError('Zuerst die Verbindung testen')
    source.setdefault('role','additional')
    if source['role'] not in ('additional','solar.main') or source['role']=='solar.main' and source['driver']!='sma_modbus':raise ValueError('Ungültige Quellenrolle')
    source['expectedSerial']=serial
    return source

def connection_key(source):
    return (source['driver'],source['host'],source['port'],source['unitId'] if source['driver']=='sma_modbus' else 0)

def fingerprint(source):
    return hashlib.sha256(json.dumps({key:source[key] for key in ('id','driver','host','port','unitId','expectedSerial')},sort_keys=True).encode()).hexdigest()
