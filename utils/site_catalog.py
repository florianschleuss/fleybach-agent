"""Offline catalog; native IDs/names and user overrides remain authoritative."""
from functools import lru_cache
from pathlib import Path
import json
import re

@lru_cache(maxsize=1)
def catalog():
    data=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
    if data.get('schemaVersion')!=1:raise ValueError('Unsupported catalog')
    return data

def measurement_name(name):
    definition=catalog()['measurements'].get(name)
    if definition:return definition['label']
    module=re.fullmatch(r'pack\.([^.]+)\.(.+)',name)
    if module:return 'Akkumodul '+module[1][-4:]+' · '+measurement_name(module[2])
    return name

def default_label(name, label=None):
    if label and ' · ' in label:
        prefix,metric=label.split(' · ',1)
        return prefix.replace('Netzzaehler','Netzzähler')+' · '+measurement_name(metric)
    return label or measurement_name(name)

def role_features():
    return {key[12:]:value['requiredFeatures']['sensor']
            for key,value in catalog()['roles'].items() if key.startswith('temperature.')}
