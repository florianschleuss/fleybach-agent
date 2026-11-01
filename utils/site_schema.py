"""Versioned site configuration shared by backend and local agent (no secrets)."""
from utils.site_catalog import catalog as definitions
import copy
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT = {'schemaVersion': 1, 'site': {'name': '', 'timezone': 'Europe/Berlin'},
           'bindings': {}, 'measurements': {}, 'devices': {}}

def validate(data, catalog=None):
    if not isinstance(data, dict) or set(data)-set(DEFAULT) or type(data.get('schemaVersion')) is not int or data.get('schemaVersion') != 1:
        raise ValueError('Unsupported site configuration')
    out = copy.deepcopy(DEFAULT)
    out.update(copy.deepcopy(data))
    site=out['site']
    if not isinstance(site,dict) or set(site)-{'name','timezone'}:
        raise ValueError('Invalid site settings')
    if not isinstance(site.get('name'),str) or len(site['name'])>120:
        raise ValueError('Invalid site name')
    try: ZoneInfo(site['timezone'])
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        raise ValueError('Invalid timezone')
    known={x['id']:x for x in catalog or []}
    for group in ('bindings','measurements','devices'):
        if not isinstance(out[group],dict) or len(out[group])>512:
            raise ValueError('Invalid '+group)
    for role, identifier in out['bindings'].items():
        if not isinstance(role,str) or len(role)>100 or not (role=='grid.main' or (role.startswith('temperature.') and len(role)>12)):
            raise ValueError('Unsupported control role')
        if not isinstance(identifier,str) or len(identifier)>200:
            raise ValueError('Invalid source identifier')
        if identifier not in known or known[identifier].get('kind')!='measurement':
            raise ValueError('Source not present in agent inventory')
        unit=definitions()['roles'].get(role,{}).get('unit','W' if role=='grid.main' else '°C')
        if known[identifier].get('unit')!=unit:
            raise ValueError('Incompatible source unit for '+role)
    for group in ('measurements','devices'):
        for identifier, item in out[group].items():
            fields={'label','location'} if group=='devices' else {'label','location','enabled','maxAgeSeconds','scale','offset'}
            if not isinstance(identifier,str) or len(identifier)>200 or not isinstance(item,dict) or set(item)-fields:
                raise ValueError('Invalid inventory settings')
            if identifier not in known or known[identifier].get('kind') != ('device' if group=='devices' else 'measurement'):
                raise ValueError('Unknown inventory item')
            for key in ('label','location'):
                if key in item and (not isinstance(item[key],str) or len(item[key])>160):
                    raise ValueError('Invalid label/location')
            if 'enabled' in item and not isinstance(item['enabled'],bool):
                raise ValueError('Invalid enabled flag')
            for key,low,high in [('maxAgeSeconds',1,3600),('scale',-10000,10000),('offset',-1000000,1000000)]:
                if key in item:
                    n=item[key]
                    if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or not low<=n<=high or (key=='scale' and n==0):
                        raise ValueError('Invalid '+key)
    return out
