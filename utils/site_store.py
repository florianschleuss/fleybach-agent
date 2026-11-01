"""Local WAL-backed inventory; cloud failures never gate measurement writes."""
import copy
import json
import math
import os
from pathlib import Path
import sqlite3
import time
from contextlib import contextmanager
from utils.site_schema import DEFAULT, validate

@contextmanager
def database():
    path=os.environ.get('SITE_STATE_PATH')
    if not path: raise RuntimeError('Local site store is not configured')
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path, timeout=2)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS inventory (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY, customer TEXT NOT NULL)')
    customer=os.environ.get('CUSTOMER_DOMAIN')
    if customer:
        db.execute('INSERT OR IGNORE INTO identity VALUES (1,?)',(customer,))
        stored=db.execute('SELECT customer FROM identity WHERE id=1').fetchone()[0]
        if stored!=customer:
            db.close()
            raise RuntimeError('Local site database belongs to a different customer')
        db.commit()
    try:
        yield db
        db.commit()
    finally: db.close()

def publish(identifier, name, unit, value, sampled_at, source, kind='measurement', **extra):
    if not os.environ.get('SITE_STATE_PATH'): return
    if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
        return
    item=dict(id=identifier,name=name,unit=unit,value=value,sampledAt=sampled_at,
              receivedAt=time.time(),source=source,kind=kind,**extra)
    try:
        with database() as db:
            db.execute('INSERT INTO inventory VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                       (identifier,json.dumps(item,allow_nan=False)))
    except (OSError,sqlite3.Error):
        # Preserve hardware polling; the reader will expire the previous sample.
        pass

def configuration():
    with database() as db:
        row=db.execute('SELECT payload FROM settings WHERE id=1').fetchone()
    return json.loads(row[0]) if row else dict(revision=0,config=copy.deepcopy(DEFAULT))

def inventory(now=None):
    now=time.time() if now is None else now
    with database() as db:
        items=[json.loads(row[0]) for row in db.execute('SELECT payload FROM inventory ORDER BY id')]
    cfg=configuration()['config']
    for item in items:
        override=cfg.get('devices' if item['kind']=='device' else 'measurements',{}).get(item['id'],{})
        item.update({k:v for k,v in override.items() if k in ('label','location','enabled','maxAgeSeconds')})
        item['rawValue']=item['value']
        if item['value'] is not None:
            item['value']=item['value']*override.get('scale',1)+override.get('offset',0)
        sampled=item['sampledAt']
        item['quality']='disabled' if not override.get('enabled',True) else (
            'unavailable' if item['value'] is None or not sampled else
            'invalid' if sampled>now+10 else
            'stale' if now-sampled>override.get('maxAgeSeconds',60) else 'valid')
    return items

def apply(revision,config):
    config=validate(config,inventory())
    if isinstance(revision,bool) or not isinstance(revision,int) or revision<0: raise ValueError('Invalid revision')
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT payload FROM settings WHERE id=1').fetchone()
        if old:
            current=json.loads(old[0])
            if revision<current['revision'] or (revision==current['revision'] and config!=current['config']):
                raise ValueError('Stale/conflicting configuration')
        db.execute('INSERT INTO settings VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                   (json.dumps(dict(revision=revision,config=config)),))

def role_value(role,legacy_name=None,source=None):
    cfg=configuration()['config']
    explicit=cfg['bindings'].get(role)
    candidates=[x for x in inventory() if x['kind']=='measurement' and
                (x['id']==explicit if explicit else x['name']==legacy_name and x['source']==source)]
    if len(candidates)!=1 or candidates[0]['quality']!='valid':
        raise ConnectionError('Required local source unavailable: '+role)
    return candidates[0]['value']

def temperatures():
    cfg=configuration()['config']; items=inventory()
    values={x['name']:x['value'] for x in items if x['source']=='temperature' and x['quality']=='valid' and x['unit']=='°C'}
    for role in cfg['bindings']:
        if role.startswith('temperature.'):
            name=role[len('temperature.'):]
            try: values[name]=role_value(role)
            except ConnectionError: values.pop(name,None)
    return values
