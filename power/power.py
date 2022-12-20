from datetime import datetime, timedelta
import json
import os
import time
from typing import Union

import requests as r
from pymodbus.client.sync import ModbusTcpClient

from utils.auth import JWTValidator
from sma.register import Register, registers as sma_registers

domain = os.environ.get('CUSTOMER_DOMAIN')
secret = os.environ.get('CUSTOMER_SECRET')
address = os.environ.get('SMA_MODBUS_IP')
port = os.environ.get('SMA_MODBUS_PORT', 502)
auth_utl = os.environ.get('AUTH_URL')

jwt = JWTValidator(auth_utl, domain, secret)

with open('sma/smaRegisters.json') as config:
    register_config = json.load(config)

with open('config.json') as config:
    config = json.load(config)

client = ModbusTcpClient(host=address, port=port, timeout=10)
client.connect()


def update_sensor(id: str, name: str, value: Union[int, float], unit: str, type: str) -> bool:
    jwt.v()
    sensor_config = next(s for s in config['sensors'] if s['deviceId'] == id)
    if sensor_config.get('offset') is not None:
        value = value + sensor_config['offset']

    patch = r.patch(f'http://{domain}/sensor/sensors/{id}?customer_id={jwt.token.customer_id}', json={
        'value': value
    }, headers={'x-access-token': jwt.token._token})
    if patch.status_code == 404:
        post = r.post(f'http://{domain}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
            'id': id,
            'name': name,
            'value': value,
            'unit': unit,
            'type': type
        }, headers={'x-access-token': jwt.token._token})
    return False  # TODO Validation of success


def make_history(names: list):
    jwt.v()
    post = r.post(f'http://{domain}/sensor/sensors/names/history?customer_id={jwt.token.customer_id}', json={
        'names': names
    }, headers={'x-access-token': jwt.token._token})
    return False  # TODO Validation of success


def get_inverter_data(name: str):
    try:
        config_register = next(s for s in register_config if s['name'] == name)
    except StopIteration:
        return None
    register: Register = sma_registers[config_register['register']]
    response = client.read_holding_registers(
        register.id,
        register.length,
        unit=1
    )
    register.set_registers(response.registers)
    if register.is_null() or register.get_value() == -2147483648:
        return None
    if (_f:= config_register.get('calculationFactor')) is not None and (_o:= config_register.get('calculationOperand')) is not None:
        if _o == '/':
            value = register.get_value()/_f
    else:
        value = register.get_value()
    return {'value': value, 'unit': config_register['unit'], 'type': config_register['type']}


def check_routines():
    now = datetime.now()
    timestamp = now.timestamp()
    for r in config['routines']:
        if r.get('lastCycle', 0) < (timestamp - r['timespan'] * 60) and int(timestamp/60) % r['timespan'] == 0:
            if r['type'] == 'history':
                make_history(r['sensorNames'])
            try:
                print(
                    f"{r['name'].capitalize()}: {int((timestamp-r['lastCycle']-10)/60)}:{int(timestamp-r['lastCycle']-10)%60} min since last run", flush=True)
            except:
                pass
            # -10 seconds are to account for eventual stack of miliseconds up to a full skip of one round
            r['lastCycle'] = timestamp - 10
    return


if __name__ == '__main__':
    while True:
        start = datetime.now().timestamp()
        for s in config['sensors']:
            if s.get('enabled', True):
                if s.get('timeout', 0) > datetime.now().timestamp():
                    continue
                if (data:= get_inverter_data(s['name'])) is not None:
                    update_sensor(s['deviceId'], s['name'], data['value'], data['unit'], s.get('unit', data['type']))
                # elif: TODO powermeter     
        check_routines()
        time.sleep(5 - (datetime.now().timestamp() - start))
    exit()
