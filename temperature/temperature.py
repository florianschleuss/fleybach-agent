from datetime import datetime, timedelta
import json
import os
import threading
import time
from typing import Dict, List, Optional, Union
from flask import Flask
from flask_restful import Api

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
    jwt.v()
    sensor = config.get_sensor(id)
    value = value + sensor.offset
    try:
        patch = r.patch(f'http://{CUSTOMER_DOMAIN}/sensor/sensors/{id}?customer_id={jwt.token.customer_id}', json={
            'value': value
        }, headers={'x-access-token': jwt.token._token})
        if patch.status_code == 404:
            post = r.post(f'http://{CUSTOMER_DOMAIN}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
                'id': sensor.device_id,
                'name': sensor.name,
                'value': value,
                'unit': sensor.unit,
                'type': sensor.type
            }, headers={'x-access-token': jwt.token._token})
        sensor.present_in_database = True
    except r.exceptions.ConnectionError:
        pass
    return False  # TODO Validation of success


def batch_update_sensor(sensors_list: List[Dict]):
    if len(sensors_list) == 0:
        return
    jwt.v()
    try:
        post = r.patch(f'http://{CUSTOMER_DOMAIN}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
            'sensors': sensors_list
        }, headers={'x-access-token': jwt.token._token})
    except r.exceptions.ConnectionError:
        for update_sensor in sensors_list:
            sensor = config.get_sensor(update_sensor['id'])
            sensor.present_in_database = False
    return False  # TODO Validation of success


def make_history(names: List):
    jwt.v()
    try:
        post = r.post(f'http://{CUSTOMER_DOMAIN}/sensor/sensors/names/history?customer_id={jwt.token.customer_id}', json={
            'names': names
        }, headers={'x-access-token': jwt.token._token})
    except r.exceptions.ConnectionError:
        pass
    return False  # TODO Validation of success


def get_temperature(id: str) -> Optional[float]:
    sensor = config.get_sensor(id)
    try:
        with open('/sys/bus/w1/devices/{}/w1_slave'.format(id)) as file:
            filecontent = file.read()
        stringvalue = filecontent.split("\n")[1].split(" ")[9]
        temperature = float(stringvalue[2:]) / 1000
        if sensor.lower_bound <= temperature <= sensor.upper_bound:
            return temperature
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
    return


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
        start = datetime.now().timestamp()
        sensors = []
        for sensor in config.sensors:
            if not sensor.enabled:
                continue
            if sensor.on_timeout():
                continue
            if (temperature := get_temperature(sensor.device_id)) is None:
                continue
            if sensor.present_in_database:
                sensors.append(
                    {'id': sensor.device_id, 'value': temperature})
            else:
                update_sensor(sensor.device_id, temperature)
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
        if get_temperature(sensor.device_id) is None:
            continue
        sensors.append(sensor.name)
    return {'sensors': sensors}, 200


if __name__ == '__main__':
    threading.Thread(target=update_loop).start()
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)
