from datetime import datetime, timedelta
import json
import os
import time
from typing import Union

import requests as r

from utils.auth import JWTValidator, get_jwt

domain = os.environ.get('CUSTOMER_DOMAIN')
secret = os.environ.get('CUSTOMER_SECRET')
auth_utl = os.environ.get('AUTH_URL')
jwt = JWTValidator(auth_utl, domain, secret)


with open('config.json') as config:
    config = json.load(config)


def update_sensor(id: str, value: Union[int, float]) -> bool:
    jwt.v()
    sensor_config = next(s for s in config['sensors'] if s['deviceId'] == id)
    if sensor_config.get('offset') is not None:
        value = value + sensor_config['offset']
    unit = '°C'
    type = 'temperature'
    patch = r.patch(f'http://{domain}/sensor/sensors/{id}?customer_id={jwt.token.customer_id}', json={
        'value': value
    }, headers={'x-access-token': jwt.token._token})
    if patch.status_code == 404:
        post = r.post(f'http://{domain}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
            'id': id,
            'name': sensor_config['name'],
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


def get_temperature(id: str):
    sensor_config = next(s for s in config['sensors'] if s['deviceId'] == id)
    try:
        with open('/sys/bus/w1/devices/{}/w1_slave'.format(id)) as file:
            filecontent = file.read()
        stringvalue = filecontent.split("\n")[1].split(" ")[9]
        temp = float(stringvalue[2:]) / 1000
        if sensor_config.get('lowerBounds', -20) <= temp <= sensor_config.get('upperBounds', 50):
            return temp
    except FileNotFoundError as e:
        sensor_config['timeout'] = (
            datetime.now() + timedelta(minutes=5)).timestamp()
        sensor_config['disconnectedCycles'] = sensor_config.get(
            'disconnectedCycles', 0) + 1
        if sensor_config['disconnectedCycles'] % 6 == 0:
            # TODO E-Mail alert
            print(datetime.now(), "E-Mail", flush=True)
    except Exception as e:
        print(str(e), flush=True)
    return


def check_routines():
    now = datetime.now()
    timestamp = now.timestamp()
    for r in config['routines']:
        if r['type'] == 'cycle':
            if r.get('lastCycle', 0) < (timestamp - r['timespan'] * 60) and int(timestamp/60) % r['timespan'] == 0:
                make_history(r['sensorNames'])
                try:
                    print(f"{r['name'].capitalize()}: {int((timestamp-r['lastCycle']-10)/60)}:{int(timestamp-r['lastCycle']-10)%60} min since last run", flush=True)
                except:
                    pass
                r['lastCycle'] = timestamp - 10 # -10 seconds are to account for eventual stack of miliseconds up to a full skip of one round
        elif r['type'] == 'datetime':
            pass # TODO Datetime routines rely on a specific date time cimbination to be triggered like cronjobs
    return


if __name__ == '__main__':
    while True:
        start = datetime.now().timestamp()
        for s in config['sensors']:
            if s.get('enabled', True):
                if s.get('timeout', 0) > datetime.now().timestamp():
                    continue
                temperature = get_temperature(s['deviceId'])
                if temperature is not None:
                    update_sensor(s['deviceId'], temperature)
        check_routines()
        time.sleep(5 - (datetime.now().timestamp() - start))
    exit()
