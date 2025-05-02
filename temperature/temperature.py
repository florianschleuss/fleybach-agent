from datetime import datetime, timedelta
import json
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
        patch = r.patch(f'http://{AUTH_URL}/sensor/sensors/{id}?customer_id={jwt.token.customer_id}', json={
            'value': value
        }, headers={'x-access-token': jwt.token._token})
        print("Patch", flush=True)
        print(patch.status_code, flush=True)
        if patch.status_code == 404:
            post = r.post(f'http://{AUTH_URL}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
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
        post = r.patch(f'http://{AUTH_URL}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
            'sensors': sensors_list
        }, headers={'x-access-token': jwt.token._token})
    except r.exceptions.ConnectionError:
        for update_sensor in sensors_list:
            if (sensor := config.get_sensor(update_sensor['id'])) is None:
                return False
            sensor.present_in_database = False
    return False  # TODO Validation of success


def make_history(names: List):
    jwt.v()
    try:
        post = r.post(f'http://{AUTH_URL}/sensor/sensors/names/history?customer_id={jwt.token.customer_id}', json={
            'names': names
        }, headers={'x-access-token': jwt.token._token})
    except r.exceptions.ConnectionError:
        pass
    return False  # TODO Validation of success


def update_temperature(id: str) -> bool:
    '''
    :return: True if update was successful
    '''
    if (sensor := config.get_sensor(id)) is None:
        return False
    try:
        with open('/sys/bus/w1/devices/{}/w1_slave'.format(id)) as file:
            filecontent = file.read()
        stringvalue = filecontent.split("\n")[1].split(" ")[9]
        temperature = float(stringvalue[2:]) / 1000
        if sensor.lower_bound <= temperature <= sensor.upper_bound:
            sensor.update_value(temperature)
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
              initiator='Power Component',
              event_severity=EventSeverity.IMPORTANT,
              event_type=EventType.ERROR).store()
    return False


def update_temperature_by_serial() -> List[Dict]:
    '''
    Updates all sensors that are send via serial
    '''
    batch_sensors = []
    with serial.Serial(
            port='/dev/ttyUSBTem',
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0) as ser:
        seq = []
        start_time = time.time()
        # 20 Seconds time to receive the serial-data
        while time.time() - start_time < 20:
            for c in ser.read():
                seq.append(chr(c))

                # Only evaluate if end-of-line is reached
                if chr(c) != '\n':
                    continue

                # convert from ANSII to string
                joined_seq = ''.join(str(v)for v in seq).strip()
                if len(joined_seq) < 2:
                    continue

                if joined_seq[0] == '{' and joined_seq[-1] == '}':
                    data_sensors = json.loads(
                        joined_seq)['sensors']
                    for data_sensor in data_sensors:
                        if (sensor := config.get_sensor(data_sensor['id'])) is None:
                            continue

                        temperature = data_sensor['value']
                        if temperature is None:
                            continue
                        if sensor.lower_bound <= temperature <= sensor.upper_bound:
                            sensor.update_value(temperature)
                            batch_sensors.append(
                                {'id': sensor.device_id, 'value': sensor.value})
                    return batch_sensors
                seq = []
                break
        return []


def check_routines():
    for routine in config.routines:
        if routine.type == 'cycle':
            if not routine.due():
                continue
            make_history(routine.sensor_names)
            Event(
                f"{routine.name.capitalize()}: {format_seconds_to_mm_ss(time.time()-routine.last_run-10)} since last run",
                initiator='Power Component',
                event_severity=EventSeverity.DEBUG).store()
            # -10 seconds are to account for eventual stack of miliseconds up to a full skip of one round
            routine.last_run = time.time()
        elif routine.type == 'datetime':
            # TODO Datetime routines rely on a specific date time combination to be triggered like cronjobs
            pass
    return


def update_loop() -> None:
    while True:
        serial_check_flag = False
        start = datetime.now().timestamp()
        sensors = []
        for sensor in config.sensors:
            if not sensor.enabled:
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
