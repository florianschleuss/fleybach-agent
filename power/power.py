from utils.faults import FaultReporter
faults = FaultReporter("Power Component")
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

from utils.cloud_worker import CloudWorker
from utils.sensor_upload import SensorUploader
from utils.faults import FaultReporter
upload_faults = FaultReporter("Power Component")
def cloud_status(failed):
    upload_faults.observe('CLOUD_UPLOAD', 'sensors', failed,
        'Cloud upload unavailable; local acquisition continues' if failed else 'Cloud upload restored')
cloud_upload = CloudWorker('power-upload', capacity=1, observer=cloud_status)


REFRESH_TIME_SECONDS = 10

CUSTOMER_DOMAIN = os.environ.get('CUSTOMER_DOMAIN', "default")
CUSTOMER_SECRET = os.environ.get('CUSTOMER_SECRET', "")
AUTH_URL = os.environ.get('AUTH_URL', "")
address = os.environ.get('SMA_MODBUS_IP', "")
port = int(os.environ.get('SMA_MODBUS_PORT', 502))

jwt: JWTValidator = JWTValidator(AUTH_URL, CUSTOMER_DOMAIN, CUSTOMER_SECRET)
uploader = SensorUploader(jwt, AUTH_URL)

with open('sma/smaRegisters.json', encoding="utf-8") as config_file:
    register_config: List[ModbusRegister] = [
        ModbusRegister.from_object(r) for r in json.load(config_file)]

with open('config.json', encoding="utf-8") as config_file:
    config: SensorConfig = SensorConfig.from_object(json.load(config_file))

from utils.site_store import publish as publish_site_measurement
for configured_sensor in config.sensors:
    register = next((r for r in register_config if r.name == configured_sensor.name), None)
    publish_site_measurement('power:'+configured_sensor.name,configured_sensor.name,
        register.unit if register else (configured_sensor.unit or ''),None,0,'power')
for name in ('total','l1','l2','l3','bought','sold'):
    publish_site_measurement('power:'+name,name,'kWh' if name in ('bought','sold') else 'W',None,0,'power')


client = ModbusTcpClient(host=address, port=port, timeout=10)
client.connect()

sml_parser = SMLSerialParser()


def make_history(names: List):
    jwt.v()
    try:
        post = r.post(f'https://{AUTH_URL}/sensor/sensors/names/history?customer_id={jwt.token.customer_id}', json={
            'names': names
        }, headers={'x-access-token': jwt.token._token}, timeout=(5, 15))
        post.raise_for_status()
        rows = post.json().get('data', [])
        fresh = {row['name'] for row in rows if row.get('lastModified', 0) >= time.time()-60}
        return set(names).issubset(fresh)
    except (r.exceptions.RequestException, ValueError, TypeError, KeyError) as exc:
        logger.warning('Power history request failed (%s); retrying next cycle', type(exc).__name__)
        return False


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
    except Exception as exc:
        faults.observe("INVERTER_CONNECTION", "inverter", True,
                       "Cannot connect to inverter", [type(exc).__name__], critical=True)
        return
    if not hasattr(response, 'registers'):
        faults.observe("INVERTER_RESPONSE", name, True,
                       "Inverter returned no register data", [f"Register: {name}"])
        return
    faults.observe("INVERTER_CONNECTION", "inverter", False, "Inverter connection restored")
    faults.observe("INVERTER_RESPONSE", name, False, "Inverter register data available again")
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

    from utils.site_store import publish
    publish('power:'+config_register.name,config_register.name,config_register.unit,
            value,time.time(),'power')
    return {'value': value, 'unit': config_register.unit, 'type': config_register.type}


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
                initiator='Power Component',
                event_severity=EventSeverity.DEBUG).store()
            # -10 seconds are to account for eventual stack of miliseconds up to a full skip of one round
            routine.completed(history_started)
    return


def upload_snapshot(readings):
    if uploader.upload(readings):
        check_routines()
        return True
    return False


def update_loop() -> None:
    global sml_parser
    while True:
        start = time.monotonic()
        try:
            readings = []
            for sensor in config.sensors:
                if not sensor.enabled or sensor.on_timeout():
                    continue
                data = get_inverter_data(sensor.name)
                if data is not None:
                    readings.append(dict(id=sensor.device_id, name=sensor.name,
                        value=data['value'], unit=data['unit'],
                        type=sensor.type or data['type'], sampledAt=time.time()))
            data = sml_parser.get_energy_data()
            if data is not None:
                for name, value in data.to_dict().items():
                    readings.append(dict(id='pw-'+name, name=name, value=value,
                        unit='kWh' if name in ('bought','sold') else 'W',
                        type='power', sampledAt=data.sampled_at))
            else:
                Event('No power data from serial connection', initiator='Power Component',
                    event_severity=EventSeverity.IMPORTANT, event_type=EventType.ERROR).store()
            # Capture by value: the cloud worker never reads mutable hardware/config state.
            cloud_upload.submit('snapshot', lambda rows=readings: upload_snapshot(rows))
        except Exception:
            logger.exception('Power acquisition failed; retrying next cycle')
        time.sleep(max(.1, REFRESH_TIME_SECONDS-(time.monotonic()-start)))


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
