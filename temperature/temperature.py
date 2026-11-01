from datetime import datetime, timedelta
import json
import math
import os
import threading
import time
from typing import Dict, List, Optional, Union
from flask import Flask
from flask_restful import Api

import serial

import requests as r

from utils.auth import JWTValidator
from utils.event import Event, EventSeverity, EventType
from utils.logging import format_seconds_to_mm_ss, get_module_logger
from utils.mail import AlertEmail, EmailSender
from utils.sensor import SensorConfig

logger = get_module_logger()

REFRESH_TIME_SECONDS = 10

CUSTOMER_DOMAIN = os.environ.get('CUSTOMER_DOMAIN', "default")
CUSTOMER_SECRET = os.environ.get('CUSTOMER_SECRET', "")
AUTH_URL = os.environ.get('AUTH_URL', "")
jwt: JWTValidator = JWTValidator(AUTH_URL, CUSTOMER_DOMAIN, CUSTOMER_SECRET)
es: EmailSender = EmailSender.from_env()


with open('config.json', 'r') as config_file:
    config: SensorConfig = SensorConfig.from_object(json.load(config_file))

from utils.site_store import publish as publish_site_measurement
for configured_sensor in config.sensors:
    publish_site_measurement('temperature:'+configured_sensor.device_id,
        configured_sensor.name,'°C',None,0,'temperature')


# Start a new history segment as soon as fresh readings arrive after restart.
for routine in config.routines:
    if routine.type == 'cycle':
        routine.last_run -= routine.interval_seconds


def update_sensor(id: str, value: Union[int, float]) -> bool:
    '''
    :return: True if update was successful
    '''
    jwt.v()
    print(config.get_sensor(id), flush=True)
    if (sensor := config.get_sensor(id)) is None:
        return False
    value = value + sensor.offset
    try:
        patch = r.patch(f'https://{AUTH_URL}/sensor/sensors/{id}?customer_id={jwt.token.customer_id}', json={
            'value': value
        }, headers={'x-access-token': jwt.token._token})
        print("Patch", flush=True)
        print(patch.status_code, flush=True)
        if patch.status_code == 404:
            post = r.post(f'https://{AUTH_URL}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
                'id': sensor.device_id,
                'name': sensor.name,
                'value': value,
                'unit': sensor.unit,
                'type': sensor.type
            }, headers={'x-access-token': jwt.token._token})
            print("Post", flush=True)
            print(post.status_code, flush=True)
        sensor.present_in_database = True
    except r.exceptions.ConnectionError:
        pass
    return False  # TODO Validation of success


def batch_update_sensor(sensors_list: List[Dict]):
    if len(sensors_list) == 0:
        return
    jwt.v()
    try:
        post = r.patch(f'https://{AUTH_URL}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
            'sensors': sensors_list
        }, headers={'x-access-token': jwt.token._token}, timeout=(5, 15))
    except r.exceptions.ConnectionError:
        for update_sensor in sensors_list:
            if (sensor := config.get_sensor(update_sensor['id'])) is None:
                return False
            sensor.present_in_database = False
    return False  # TODO Validation of success


def make_history(names: List):
    jwt.v()
    try:
        response = r.post(f'https://{AUTH_URL}/sensor/sensors/names/history?customer_id={jwt.token.customer_id}', json={
            'names': names
        }, headers={'x-access-token': jwt.token._token}, timeout=(5, 15))
        response.raise_for_status()
        rows = response.json().get('data', [])
        fresh = {row['name'] for row in rows
                 if row.get('lastModified', 0) >= time.time() - 60}
        if not set(names).issubset(fresh):
            logger.warning('Temperature history skipped stale or missing sensors: %s',
                           ', '.join(sorted(set(names) - fresh)))
            return False
        return True
    except (r.exceptions.RequestException, ValueError, TypeError, KeyError):
        logger.warning('Temperature history request failed; will retry next cycle')
        return False


def update_temperature(id: str) -> bool:
    '''
    :return: True if update was successful
    '''
    if (sensor := config.get_sensor(id)) is None:
        return False
    # Serial sensors are read together; missing local 1-Wire files are expected.
    if sensor.serial_connected:
        return False
    try:
        with open('/sys/bus/w1/devices/{}/w1_slave'.format(id)) as file:
            filecontent = file.read()
        stringvalue = filecontent.split("\n")[1].split(" ")[9]
        temperature = float(stringvalue[2:]) / 1000
        if sensor.lower_bound <= temperature <= sensor.upper_bound:
            sensor.update_value(temperature)
            from utils.site_store import publish
            publish('temperature:'+sensor.device_id,sensor.name,'°C',sensor.value,
                    sensor.last_updated,'temperature')
            return True
    except FileNotFoundError as e:
        sensor.update_timeout = (
            datetime.now() + timedelta(minutes=5)).timestamp()
        sensor.disconnected_cycles += 1
        if sensor.disconnected_cycles % 6 == 0:
            AlertEmail(
                alerting_component="Temperature Component",
                subject=f"Sensor {sensor.name.capitalize()} disconnected for to long",
                body=f"{sensor.name.capitalize()} with {id} was disconnected for over 30 min"
            ).send(es, to_print=True)
    except Exception as e:
        Event(str(e),
              initiator='Temperature Component',
              event_severity=EventSeverity.IMPORTANT,
              event_type=EventType.ERROR).store()
    return False


def serial_sensor_updates(line: str):
    """Ignore a damaged serial frame without stopping the polling worker."""
    try:
        report = json.loads(line)
    except (ValueError, TypeError):
        logger.warning('Ignoring malformed temperature serial frame')
        return None
    if not isinstance(report, dict) or not isinstance(report.get('sensors'), list):
        logger.warning('Ignoring temperature frame without sensor list')
        return None
    updates = []
    for reading in report['sensors']:
        if not isinstance(reading, dict):
            continue
        sensor = config.get_sensor(reading.get('id'))
        value = reading.get('value')
        if sensor is None or not sensor.enabled:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        if sensor.lower_bound <= value <= sensor.upper_bound:
            sensor.update_value(value)
            from utils.site_store import publish
            publish('temperature:'+sensor.device_id,sensor.name,'°C',sensor.value,
                    sensor.last_updated,'temperature')
            updates.append({'id': sensor.device_id, 'value': sensor.value})
    return updates


def update_temperature_by_serial() -> List[Dict]:
    with serial.Serial(port='/dev/ttyUSBTem', baudrate=115200,
                       parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                       bytesize=serial.EIGHTBITS, timeout=.2) as ser:
        pending = bytearray()
        started = time.monotonic()
        while time.monotonic() - started < 20:
            pending.extend(ser.read(256))
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending = bytearray(rest)
                updates = serial_sensor_updates(line.decode('utf-8', errors='replace').strip())
                if updates is not None:
                    return updates
            if len(pending) > 32768:
                pending.clear()
                logger.warning('Discarding oversized temperature serial frame')
        return []


def check_routines():
    for routine in config.routines:
        if routine.type == 'cycle':
            if not routine.due():
                continue
            history_started = time.time()
            if not make_history(routine.sensor_names):
                continue
            Event(
                f"{routine.name.capitalize()}: {format_seconds_to_mm_ss(time.time()-routine.last_run-10)} since last run",
                initiator='Temperature Component',
                event_severity=EventSeverity.DEBUG).store()
            # -10 seconds are to account for eventual stack of miliseconds up to a full skip of one round
            routine.completed(history_started)
        elif routine.type == 'datetime':
            # TODO Datetime routines rely on a specific date time combination to be triggered like cronjobs
            pass
    return


def update_loop() -> None:
    while True:
        try:
            serial_check_flag = False
            start = datetime.now().timestamp()
            sensors = []
            for sensor in config.sensors:
                if not sensor.enabled:
                    continue
                if sensor.serial_connected:
                    serial_check_flag = True
                    continue
                if sensor.on_timeout():
                    continue
                if not update_temperature(sensor.device_id):
                    if sensor.serial_connected:
                        serial_check_flag = True
                    continue
                if sensor.present_in_database:
                    sensors.append(
                        {'id': sensor.device_id, 'value': sensor.value})
                else:
                    update_sensor(sensor.device_id, sensor.value)
            if serial_check_flag:
                sensors.extend(update_temperature_by_serial())
            batch_update_sensor(sensors_list=sensors)
            check_routines()
            if (delta := (datetime.now().timestamp() - start)) < REFRESH_TIME_SECONDS:
                time.sleep(REFRESH_TIME_SECONDS - delta)
        except Exception:
            logger.exception('Temperature polling failed; retrying next cycle')
            time.sleep(REFRESH_TIME_SECONDS)


app = Flask(__name__)
api = Api(app)


@app.route('/activate', methods=['GET'])
def activate():
    sensors = []
    for sensor in config.sensors:
        if update_temperature(sensor.device_id):
            continue
        sensors.append(sensor.name)
    return {'sensors': sensors}, 200


if __name__ == '__main__':
    threading.Thread(target=update_loop).start()
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)
