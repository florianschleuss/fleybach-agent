"""Read-only Zendure zenSDK protocol, shared unchanged with the agent.

No device writes, guessed zero values, cumulative energy estimates or control
settings. Version-3 voltage scales are verified against our live 2400 AC reports.
"""
import math
import re
import time

PROTOCOL_VERSION = 1
PRODUCTS = {'solarFlow2400AC'}
IDENTIFIER = re.compile(r'^[A-Za-z0-9_-]{1,64}$')


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Invalid device identifier')
    return value


def number(value, minimum=-1e9, maximum=1e9):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Expected finite numeric measurement')
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('Measurement outside supported range')
    return value


def normalize(report, now=None):
    now = time.time() if now is None else now
    if not isinstance(report, dict):
        raise ValueError('Expected device report object')
    timestamp = number(report.get('timestamp'), 0, 1e11)
    if not now - 120 <= timestamp <= now + 30:
        raise ValueError('Device timestamp is stale or in the future')
    metrics = {}

    def add(data, raw, key, unit, kind, low=-1e9, high=1e9, scale=1, offset=0):
        if raw in data:
            value = round(number(data[raw]) * scale + offset, 6)
            number(value, low, high)
            # Keep existing house/SMA type queries unchanged. New sources have
            # their own API and an explicit namespace in the generic sensor API.
            metrics[key] = {'value': value, 'unit': unit, 'type': 'zendure_'+kind}

    if report.get('product') in PRODUCTS:
        if report.get('version') != 3:
            raise ValueError('Unsupported SolarFlow report version')
        serial = identifier(report.get('sn'))
        kind, model = 'battery', report['product']
        p = report.get('properties')
        if not isinstance(p, dict) or 'electricLevel' not in p:
            raise ValueError('Missing battery properties')
        add(p, 'electricLevel', 'soc', '%', 'battery_soc', 0, 100)
        for raw, key in [('packInputPower', 'discharge_power'),
                         ('outputPackPower', 'charge_power'),
                         ('outputHomePower', 'home_output_power'),
                         ('gridInputPower', 'grid_input_power'),
                         ('solarInputPower', 'solar_input_power'),
                         ('gridOffPower', 'offgrid_output_power')]:
            add(p, raw, key, 'W', 'power', 0, 100000)
        add(p, 'hyperTmp', 'temperature', '°C', 'temperature', -60, 150, .1, -273.1)
        add(p, 'BatVolt', 'voltage', 'V', 'voltage', 0, 1000, .01)
        for raw, key in [('packState', 'state'), ('packNum', 'pack_count'),
                         ('gridState', 'grid_state'), ('faultLevel', 'fault_level'),
                         ('is_error', 'error_flag')]:
            add(p, raw, key, '', 'status', 0, 1000)
        packs = report.get('packData', [])
        if not isinstance(packs, list) or len(packs) > 16:
            raise ValueError('Invalid battery pack list')
        seen = set()
        for pack in packs:
            if not isinstance(pack, dict):
                raise ValueError('Invalid battery pack')
            pack_id = identifier(pack.get('sn'))
            if pack_id in seen:
                raise ValueError('Duplicate battery pack')
            seen.add(pack_id)
            prefix = 'pack.' + pack_id + '.'
            add(pack, 'socLevel', prefix+'soc', '%', 'battery_soc', 0, 100)
            add(pack, 'state', prefix+'state', '', 'status', 0, 2)
            add(pack, 'power', prefix+'power', 'W', 'power', -100000, 100000)
            add(pack, 'maxTemp', prefix+'temperature', '°C', 'temperature', -60, 150, .1, -273.1)
            add(pack, 'totalVol', prefix+'voltage', 'V', 'voltage', 0, 1000, .01)
    elif 'total_power' in report and not report.get('product'):
        serial = identifier(report.get('deviceId'))
        kind, model = 'smart_meter', 'zendure-grid-meter'
        add(report, 'total_power', 'grid_power', 'W', 'power', -1000000, 1000000)
        # Phase readings are watts, confirmed by the installation owner.
        for phase in 'abc':
            add(report, phase+'_aprt_power', 'phase_'+phase+'_reported_power',
                'W', 'reported_power', -1000000, 1000000)
    else:
        raise ValueError('Unsupported Zendure device report')
    if len(metrics) > 128:
        raise ValueError('Too many metrics')
    return {'id': 'zendure:'+serial, 'vendor': 'zendure', 'serial': serial,
            'kind': kind, 'model': model, 'sampledAt': timestamp,
            'protocolVersion': PROTOCOL_VERSION, 'metrics': metrics}
