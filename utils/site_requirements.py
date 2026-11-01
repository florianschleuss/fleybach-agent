"""Report dependencies from existing device configuration; never import GPIO code."""
from pathlib import Path

FEATURES={'air':'airTemperature','water':'waterTemperature','bufferTop':'bufferTop','bufferBottom':'bufferBottom'}
def requirements_from_config(config):
    if not isinstance(config,dict):raise ValueError('Invalid device configuration')
    result=[]
    for group in ('local_devices','remote_devices','homeassistant_devices','dynamic_devices'):
        for device in config.get(group,[]):
            name=device['name'];roles=set();features={'device':['devices']}
            if not device.get('disable_automatic_management',False):
                roles.add('grid.main');features['sensor']=['power']
                if group=='dynamic_devices':
                    for key in ('buffer_sensor','outdoor_sensor'):
                        roles.add('temperature.'+device[key])
            for step in device.get('temperature_safety',[]):
                roles.add('temperature.'+step['sensor_name'])
            for role in roles:
                if role.startswith('temperature.') and role[12:] in FEATURES:
                    features.setdefault('sensor',[]).append(FEATURES[role[12:]])
            result.append(dict(deviceId='device:'+name,label=device.get('displayed_name') or name,
                roles=sorted(roles),features={k:sorted(set(v)) for k,v in features.items()}))
    return result

def read_requirements(path):
    import yaml
    return requirements_from_config(yaml.safe_load(Path(path).read_text(encoding='utf-8')))
