from datetime import datetime
import json
import os
import threading
import time
from typing import Dict, List, Optional, Tuple, Union

from flask import Flask
from flask_restful import Api

import requests as r
from pymodbus.client.sync import ModbusTcpClient

from sml import SMLSerialParser
from sma.register import Register, registers as sma_registers
from utils.auth import JWTValidator
from utils.event import Event, EventSeverity, EventType
from utils.logging import format_seconds_to_mm_ss, get_module_logger
from utils.sensor import ModbusRegister, Sensor, SensorConfig

logger = get_module_logger()

REFRESH_TIME_SECONDS = 10

CUSTOMER_DOMAIN = os.environ.get('CUSTOMER_DOMAIN', "default")
CUSTOMER_SECRET = os.environ.get('CUSTOMER_SECRET', "")
AUTH_URL = os.environ.get('AUTH_URL', "")
address = os.environ.get('SMA_MODBUS_IP', "")
port = int(os.environ.get('SMA_MODBUS_PORT', 502))

jwt: JWTValidator = JWTValidator(AUTH_URL, CUSTOMER_DOMAIN, CUSTOMER_SECRET)

with open('sma/smaRegisters.json', encoding="utf-8") as config_file:
    register_config: List[ModbusRegister] = [
        ModbusRegister.from_object(r) for r in json.load(config_file)]

with open('config.json', encoding="utf-8") as config_file:
    config: SensorConfig = SensorConfig.from_object(json.load(config_file))

client = ModbusTcpClient(host=address, port=port, timeout=10)
client.connect()

sml_parser = SMLSerialParser()


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
    except r.exceptions.ConnectionError as e:
        Event("Error while update_sensor()",
              details=[str(e)],
              initiator='Power Component',
              event_severity=EventSeverity.IMPORTANT,
              event_type=EventType.ERROR).store()
    return False  # TODO Validation of success


def batch_update_sensor(sensors_list: List[Dict]):
    if len(sensors_list) == 0:
        return
    jwt.v()
    try:
        post = r.patch(f'http://{CUSTOMER_DOMAIN}/sensor/sensors?customer_id={jwt.token.customer_id}', json={
            'sensors': sensors_list
        }, headers={'x-access-token': jwt.token._token})
    except r.exceptions.ConnectionError as e:
        for update_sensor in sensors_list:
            try:
                sensor = config.get_sensor(update_sensor['id'])
                sensor.present_in_database = False
            except StopIteration:
                pass
        Event("Error while batch_update_sensor()",
              details=[str(e)],
              initiator='Power Component',
              event_severity=EventSeverity.IMPORTANT,
              event_type=EventType.ERROR).store()
    return False  # TODO Validation of success


def make_history(names: List):
    jwt.v()
    try:
        post = r.post(f'http://{CUSTOMER_DOMAIN}/sensor/sensors/names/history?customer_id={jwt.token.customer_id}', json={
            'names': names
        }, headers={'x-access-token': jwt.token._token})
    except r.exceptions.ConnectionError as e:
        Event("Error while make_history()",
              details=[str(e)],
              initiator='Power Component',
              event_severity=EventSeverity.IMPORTANT,
              event_type=EventType.ERROR).store()
    return False  # TODO Validation of success


def get_inverter_data(name: str) -> Optional[Dict]:
    """
    Gets the translation info for name -> register_id out of the register_config stored at sma/smaRegisters.json.
    Tries to read register from inverter.

    :param name: Name of the needed register.

    :return: None if failure. 0 or value if no error but succesful query.
    """
    try:
        config_register: ModbusRegister = next(
            r for r in register_config if r.name == name)
    except StopIteration:
        # Not in register config
        return
    register: Register = sma_registers[str(config_register.register)]
    try:
        response = client.read_holding_registers(
            register.id,
            register.length,
            unit=3
        )
    except:
        Event("Cannot connect to inverter",
              initiator='Power Component',
              event_severity=EventSeverity.CRITICAL,
              event_type=EventType.ERROR).store()
        return
    if not hasattr(response, 'registers'):
        Event("Malformed response from inverter",
              initiator='Power Component',
              event_severity=EventSeverity.IMPORTANT,
              event_type=EventType.ERROR).store()
        return
    register.set_registers(response.registers)
    if register.is_null() or register.get_value() == -2147483648:
        # Event("Failed Register",
        #       details=[
        #           f"Name: {register.name}",
        #           f"Value: {register.get_value()}",
        #       ],
        #       initiator='Power Component',
        #       event_severity=EventSeverity.DEBUG).store()
        return {'value': 0, 'unit': config_register.unit, 'type': config_register.type}
    value = config_register.transform_value(register.get_value())

    return {'value': value, 'unit': config_register.unit, 'type': config_register.type}


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
        if (data := sml_parser.get_energy_data()) is not None:
            for k, v in data.to_dict().items():
                sensors.append(
                    {'id': 'pw-'+k, 'value': v, 'name': k})
        else:
            Event("No power data from serial connection",
                  initiator='Power Component',
                  event_severity=EventSeverity.IMPORTANT,
                  event_type=EventType.ERROR).store()

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
        sensors.append(sensor.name)
    if sml_parser.energy_data is not None:
        sensors += ['bought', 'sold', 'total', 'l1', 'l2', 'l3',]
    return {'sensors': sensors}, 200


@app.route('/power', methods=['GET'])
def power() -> Tuple[Dict, int]:
    sensors = {}
    for sensor in config.sensors:
        if (data := get_inverter_data(sensor.device_id)) is None:
            continue
        sensors[sensor.name] = data['value']
    if sml_parser.energy_data is not None:
        sensors.update(sml_parser.energy_data.to_dict())
    return {'sensors': sensors}, 200


if __name__ == '__main__':
    threading.Thread(target=update_loop).start()
    app.run(host='0.0.0.0', port=80, debug=True, use_reloader=False)
