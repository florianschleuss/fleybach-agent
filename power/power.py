from datetime import datetime, timedelta
import json
import logging
import os
import threading
import time
from typing import Dict, List, Tuple, Union

from flask import Flask
from flask_restful import Api

import requests as r
from pymodbus.client.sync import ModbusTcpClient  # type: ignore

from utils.auth import JWTValidator
from sma.register import Register, registers as sma_registers
from utils.logging import format_seconds_to_mm_ss, get_module_logger
from utils.sensor import SensorConfig

logger = get_module_logger()

REFRESH_TIME_SECONDS = 10

CUSTOMER_DOMAIN = os.environ.get('CUSTOMER_DOMAIN', "default")
CUSTOMER_SECRET = os.environ.get('CUSTOMER_SECRET', "")
AUTH_URL = os.environ.get('AUTH_URL', "")
address = os.environ.get('SMA_MODBUS_IP')
port = os.environ.get('SMA_MODBUS_PORT', 502)

jwt: JWTValidator = JWTValidator(AUTH_URL, CUSTOMER_DOMAIN, CUSTOMER_SECRET)

with open('sma/smaRegisters.json') as config_file:
    register_config = json.load(config_file)

with open('config.json') as config_file:
    config: SensorConfig = SensorConfig.from_object(json.load(config_file))

client = ModbusTcpClient(host=address, port=port, timeout=10)
client.connect()


def update_sensor(id: str, name: str, value: Union[int, float], unit: str, type: str) -> bool:
    jwt.v()
    sensor = config.get_sensor(id)
    value = value + sensor.offset
    try:
        patch = r.patch(f'http://{CUSTOMER_DOMAIN}/sensor/sensors/{id}?customer_id={jwt.token.customer_id}', json={
            'value': value
        }, headers={'x-access-token': jwt.token._token})
        if patch.status_code == 404:
            post = r.post(f'http://{CUSTOMER_DOMAIN}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
                'id': id,
                'name': name,
                'value': value,
                'unit': unit,
                'type': type
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


def get_inverter_data(name: str):
    try:
        config_register = next(s for s in register_config if s['name'] == name)
    except StopIteration:
        return None
    register: Register = sma_registers[config_register['register']]
    try:
        response = client.read_holding_registers(
            register.id,
            register.length,
            unit=2
        )
    except:
        logger.critical("Cannot connect to inverter")
        return
    register.set_registers(response.registers)
    # print(register.get_value(), flush=True)
    if register.is_null() or register.get_value() == -2147483648:
        return None
    value = register.get_value()
    if (_f := config_register.get('calculationFactor')) is not None and (_o := config_register.get('calculationOperand')) is not None:
        if _o == '/':
            value = value/_f
    return {'value': value, 'unit': config_register['unit'], 'type': config_register['type']}


def check_routines():
    for routine in config.routines:
        if routine.type == 'cycle':
            if not routine.due():
                continue
            make_history(routine.sensor_names)
            logger.info(
                f"{routine.name.capitalize()}: {format_seconds_to_mm_ss(time.time()-routine.last_run-10)} since last run")
            # -10 seconds are to account for eventual stack of miliseconds up to a full skip of one round
            routine.last_run = time.time()
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
            if (data := get_inverter_data(sensor.name)) is None:
                continue
            if sensor.present_in_database:
                sensors.append(
                    {'id': sensor.device_id, 'value': data['value'], 'name': sensor.name})
            else:
                update_sensor(id=sensor.device_id,
                              name=sensor.name,
                              value=data['value'],
                              unit=data['unit'],
                              type=sensor.type if sensor.type is not None else data['type'])

        # TODO: powermeter

        batch_update_sensor(sensors_list=sensors)
        check_routines()
        if (delta := (datetime.now().timestamp() - start)) < REFRESH_TIME_SECONDS:
            time.sleep(REFRESH_TIME_SECONDS - delta)


app = Flask(__name__)
api = Api(app)


@app.route('/activate', methods=['GET'])
def activate() -> Tuple[Dict, int]:
    sensors = []
    for sensor in config.sensors:
        if get_inverter_data(sensor.device_id) is None:
            continue
        # TODO if get_powermeter()
        sensors.append(sensor.name)
    return {'sensors': sensors}, 200


if __name__ == '__main__':
    threading.Thread(target=update_loop).start()
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)
