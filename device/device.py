import datetime
import requests
import os
import time
from typing import Any, Dict, List, Optional
import yaml
import socketio

from utils.auth import JWTValidator
from utils.delayTimer import DelayTimer
from utils.event import Event, EventSeverity, EventType
from utils.logging import format_seconds_to_mm_ss, get_module_logger
from utils.mail import AlertEmail, EmailSender
from utils.reason import ReasonFlow
from utils.switchable.powerSwitchable import LocalDevice, PowerSwitchable, RemoteDevice, RemoteDeviceType
from utils.switchable.switchable import TemperatureSafety
from utils.task import Action, Task
from utils.transportModels import ReturnObject

logger = get_module_logger()
sio: socketio.Client = socketio.Client()

DEADLINE_CHECK_TIME = datetime.time(19, 00, 00)  # UTC
REFRESH_TIME_SECONDS = 10
CUSTOMER_DOMAIN = os.environ.get('CUSTOMER_DOMAIN', "default")
CUSTOMER_SECRET = os.environ.get('CUSTOMER_SECRET', "")
AUTH_URL = os.environ.get('AUTH_URL', "")

jwt = JWTValidator(AUTH_URL, CUSTOMER_DOMAIN, CUSTOMER_SECRET)

# Constants initialized at startup to store if components are present
local_temperature_component = False
local_power_component = False
startup_check_values = {}


def deep_update(mapping: Dict[str, Any], *updating_mappings: Dict[str, Any]) -> Dict[str, Any]:
    old_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if k in old_mapping and isinstance(old_mapping[k], dict) and isinstance(v, dict):
                old_mapping[k] = deep_update(old_mapping[k], v)
            if k in old_mapping and isinstance(old_mapping[k], list) and isinstance(v, list):
                if len(v) == 0:
                    old_mapping[k] = []
                if isinstance(v[0], dict):
                    old_mapping[k] = [deep_update(
                        old_mapping[k][ind], i) for ind, i in enumerate(v)]
                else:
                    old_mapping[k] = v
            else:
                old_mapping[k] = v
    return old_mapping


class DeviceController:
    def __init__(
        self,
        devices: Optional[Dict[str, PowerSwitchable]] = None,
        device_config_path: Optional[str] = os.environ.get(
            "DEVICE_CONFIG_PATH")
    ):
        # Path to the config file, defaults to device-config.yaml
        # 1st method param, 2nd env variable, 3rd default
        self._device_config_path: str = "device-config.yaml"
        if device_config_path is not None:
            self._device_config_path = device_config_path

        # Device list to pre-populate the device list. Key is device_name
        self._devices: Dict[str, PowerSwitchable]
        if devices is None:
            self._devices = self.update_devices_from_config()
        else:
            self._devices = devices

        # List of the last power_consumption values
        # to calc an average over all of them
        self._avrg_power_consumtion: Dict[int, float] = {}

        # The span in sec over which the power avrg is calculated
        self._avrg_power_timespan = 30

        # Last time the deadline_check has run
        self._deadline_check_last_run = 0

    def _devices_in_relevance_order(self,
                                    state: bool = False,
                                    reverse: bool = False,
                                    reason_flow: Optional[ReasonFlow] = None,
                                    ) -> List[PowerSwitchable]:
        """
        Returns a list of devices in a specific order based on their relevance.
        1st prio has importance value
        2nd prio has rest_active_time value

        :param state: Filter devices by their state (default is off).
        :param reverse: Set to True to reverse the sorting order.

        :return: A list of devices sorted by their rest active time,
                with optional filtering and sorting direction.
        """
        devices = [device for device in self._devices.values()
                   if device._state == state]
        devices = sorted(
            devices,
            key=lambda device: (device._importance,
                                device.rest_active_time_seconds),
            reverse=not reverse)
        if reason_flow is not None:
            if len(devices) == 0:
                reason_flow.add_reason(
                    f"No relevant devices in list").to_event(EventSeverity.DEBUG)
                return devices
            reason_flow.add_reason(
                f"Relevant devices in state '{state}' are {[d.name for d in devices]}")
        return devices

    def _active_time_deadline_check(self,
                                    reason_flow: Optional[ReasonFlow] = None) -> None:
        """
        Checks if all devices have fullfilled their min_active_time.
        If not activates them for the needed amount of time.        
        """

        # Creat info-event for runtime summary of day
        for d in self._devices.values():
            if d.rest_active_time_seconds > 0:
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"{d.name.replace('_', '-').title()} needs {format_seconds_to_mm_ss(d.rest_active_time_seconds)} to fullfil min. active time")
            else:
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"{d.name.replace('_', '-').title()} ran for {format_seconds_to_mm_ss(d.active_time_seconds)} today. Min. active time fullfiled")
        if reason_flow is not None:
            reason_flow.to_event(event_severity=EventSeverity.INFO)

        # Min. active time checking
        for d in self._devices.values():
            if d.rest_active_time_seconds == 0:
                break
            drf = reason_flow.split() if reason_flow is not None else None
            d.set_state(True,
                        user='DeadlineCheck',
                        timer_seconds=d.rest_active_time_seconds,
                        reason_flow=drf)
            # Log event
        return

    def _available_power(self, current_power_consumption: float):
        """
        Update the average power consumption list and calculate available power.

        :param current_power_consumption: The current power consumption to be added to the list.

        :return: The available power, which is the average power consumption over a specified time period.
        """
        for k, v in list(self._avrg_power_consumtion.items()):
            if v < time.time() - self._avrg_power_timespan:
                del self._avrg_power_consumtion[k]
        self._avrg_power_consumtion[int(
            time.time())] = current_power_consumption
        return sum(self._avrg_power_consumtion.values()) / len(self._avrg_power_consumtion.values()) * -1

    @property
    def device_list(self) -> List[str]:
        return list(self._devices.keys())

    def get_device_by_name(self, name: str) -> PowerSwitchable:
        """
        :return: Returns the device
        """
        if not self.has_device(name):
            raise Exception("Device not in DeviceController")
        return self._devices[name]

    def get_devices(self) -> List[PowerSwitchable]:
        """
        :return: Returns all devices
        """
        return list(self._devices.values())

    def safety_sensor_list(self) -> List[str]:
        sensors = []
        for d in self._devices.values():
            if d._temperature_safety is None:
                continue
            sensors += d._temperature_safety.needed_sensors()
        return list(dict.fromkeys(sensors))

    def has_device(self, name: str) -> bool:
        return name in self._devices

    def switch_device(self,
                      device_name: str,
                      user: str,
                      new_state: Optional[bool] = None,
                      timer_seconds: Optional[int] = None
                      ) -> bool:
        if not self.has_device(device_name):
            return False
        device: PowerSwitchable = self._devices[device_name]

        reason_flow: ReasonFlow = ReasonFlow(
            name=f"Manual switch at {datetime.datetime.now()} UTC",
            initiator=device.name.replace('_', '-').title(),
            initial_comment=f"{device.name.capitalize()} switched by '{user}'")
        to_value: bool = new_state if new_state is not None else not device.state
        set_value: bool = device.set_state(new_state=to_value,
                                           user=user,
                                           reason_flow=reason_flow,
                                           timer_seconds=timer_seconds)
        return to_value == set_value

    def update_devices_from_config(
            self,
            devices: Dict[str, PowerSwitchable] = {}
    ) -> Dict[str, PowerSwitchable]:
        """
        Updates the list of devices based on a configuration file.

        :param devices: A dictionary of existing devices.
                        Defaults to an empty dictionary.

        :return: A dictionary containing the updated list of devices.
        """
        new_devices: Dict[str, PowerSwitchable] = {}
        try:
            with open(self._device_config_path, 'r') as file:
                device_config: Dict = yaml.safe_load(file)
        except FileNotFoundError as e:
            return new_devices
        d: Dict

        # Local devices
        for d in device_config.get('local_devices', []):
            ld: LocalDevice = LocalDevice.from_object(
                d,
                dependencies=[new_devices[dependency_name]
                              for dependency_name in d.get(
                    'dependencies', [])],
                updating_device=devices.get(d['name'], None))  # type: ignore
            new_devices[ld.name] = ld

        # Remote devices
        for d in device_config.get('remote_devices', []):
            rd: RemoteDevice = RemoteDevice.from_object(
                d,
                dependencies=[new_devices[dependency_name]
                              for dependency_name in d.get(
                    'dependencies', [])],
                updating_device=devices.get(d['name'], None))  # type: ignore
            new_devices[rd.name] = rd
        return new_devices

    def dump_config(self):
        """
        Dump the current devices to the configuration file.

        :return: None
        """
        config_data = {
            'local_devices': [],
            'remote_devices': []
        }
        irrelevant_keys = [
            'active_time_seconds'
            'restart_timer'
            'shutdown_timer'
            'state',
            'power_all']
        default_local_device_data = LocalDevice(
            name='-1', gpio=50, power=-1).to_dict()
        default_remote_device_data = RemoteDevice(name='-1',
                                                  power=-1, device_type=RemoteDeviceType.DEFAULT, host="-1").to_dict()

        for device in self._devices.values():
            device_data = device.to_dict()
            if isinstance(device, LocalDevice):
                config_data['local_devices'].append(
                    {key: value for key, value in device_data.items() if value != default_local_device_data[key] and key not in irrelevant_keys})
            elif isinstance(device, RemoteDevice):
                config_data['remote_devices'].append(
                    {key: value for key, value in device_data.items() if value != default_remote_device_data[key] and key not in irrelevant_keys})

        with open(self._device_config_path, 'r') as file:
            device_config: Dict = yaml.safe_load(file)
        device_config = deep_update(device_config, config_data)
        with open(self._device_config_path, 'w', encoding='utf-8') as file:
            yaml.dump(device_config, file, sort_keys=False, allow_unicode=True)

    @staticmethod
    def is_within_x_hours_range(target_time: datetime.time, x_hours: int) -> bool:
        """
        Check if the current time is within a specified number of hours around the given time.

        :param target_time (datetime): The target time to check.
        :param x_hours (int): The number of hours for the range.

        :return: True if the target time is within the specified hours range from the current time, False otherwise.
        """
        # Get the current time
        current_time = datetime.datetime.now().time()

        # Calculate the custom time window
        custom_window_end_time = (datetime.datetime.combine(
            datetime.datetime.today(), target_time) + datetime.timedelta(hours=x_hours)).time()

        # Check if the target time is within the specified hours range
        return target_time <= current_time <= custom_window_end_time

    def tick(self,
             current_power_consumption: float) -> None:
        """
        Update the state of devices based on available power.

        :param current_power_consumption: The current power consumption.
        """
        available_power = self._available_power(current_power_consumption)

        # ReasonFlow to store all decisions made througout the process
        reason_flow: ReasonFlow = ReasonFlow(
            name=f"Power Tick",
            initiator='Device Component',
            initial_comment=f"Tick with {available_power} available power",
            auto_store_event_severity=EventSeverity.DEBUG)

        # Not enough power present
        if available_power <= 0:
            devices = self._devices_in_relevance_order(state=True,
                                                       reverse=True,
                                                       reason_flow=reason_flow)
            for device in devices:
                if device._power_off_tolerance > available_power:
                    if not device.set_state(False,
                                            user='Automation',
                                            reason_flow=reason_flow.add_reason(f"Try to set state to '{False}' for '{device.name}' with user 'Automation'")):
                        current_power_consumption -= device.power_all
        # To much power present
        else:
            devices = self._devices_in_relevance_order(
                state=False, reverse=False, reason_flow=reason_flow)

            for device in devices:
                if (
                    device.power_all < available_power
                    and
                    device.rest_active_time_seconds > 0
                ):
                    drf = reason_flow.add_reason(
                        f"Try to set state to '{True}' for '{device.name}' requiring {device.power_all} power with user 'Automation'")
                    if device.set_state(True,
                                        user='Automation',
                                        reason_flow=drf):
                        available_power -= device.power_all

        # Deadline check
        if DEADLINE_CHECK_TIME is not None:
            check_time = datetime.datetime.now().time()
            if self.is_within_x_hours_range(DEADLINE_CHECK_TIME, 1) and self._deadline_check_last_run < time.time()-12*60*60:
                self._active_time_deadline_check(
                    reason_flow=ReasonFlow('Deadline check',
                                           initiator='Device Component',))
                self._deadline_check_last_run = time.time()

    def temperature_tick(self, temperatures: Dict[str, float]) -> None:
        """
        Evaluate switching decisions based on temperature.

        :param temperatures: The current temperature of all associated sensors.
        """
        for device in self._devices.values():
            if device._temperature_safety is None:
                continue
            ts: TemperatureSafety = device._temperature_safety
            for tss in ts.temperature_safety_steps:
                if tss.sensor_name not in temperatures:
                    if tss.needs_alert():
                        AlertEmail(
                            alerting_component="Temperature Safety",
                            subject=f"Temperature sensor {tss.sensor_name} missing for temperature safety",
                            body=f"Sensor {tss.sensor_name} not in temperatures: {temperatures}\nTriggered after {format_seconds_to_mm_ss(tss.interval_seconds)} wait time."
                        ).send(es, to_print=True)
                        tss.alert_send()
                    continue
                if not tss.is_safe(temperatures[tss.sensor_name]):
                    rf: ReasonFlow = ReasonFlow(
                        name=f"Temperature safety",
                        initiator='Device Component',
                        initial_comment=f"Temperature safety triggered at {temperatures[tss.sensor_name]} for {format_seconds_to_mm_ss(tss.duration_seconds)}")
                    device.set_state(
                        new_state=True,
                        user="Temperature-Safety",
                        timer_seconds=tss.duration_seconds,
                        reason_flow=rf
                    )
                    tss.trigger()
        return


es: EmailSender = EmailSender.from_env()
dc: DeviceController = DeviceController()


def _check_temperature_component(rf: ReasonFlow) -> bool:
    global local_temperature_component
    try:
        get = requests.get(url="http://temperature/activate")
    except requests.exceptions.RequestException:
        rf.add_reason(
            f"Local temperature component is not reachable")
        return local_temperature_component
    sensors: List[str] = get.json()['sensors']
    if set(dc.safety_sensor_list()).issubset(set(sensors)):
        local_temperature_component = True
    rf.add_reason(
        f"Local temperature component {'does not have' if not local_temperature_component else 'has'} all sensors requried")
    return local_temperature_component


def _check_power_component(rf: ReasonFlow) -> bool:
    global local_power_component
    try:
        get = requests.get(url="http://power/activate")
    except requests.exceptions.RequestException:
        rf.add_reason(
            f"Local temperature component is not reachable")
        return local_power_component
    sensors: List[str] = get.json()['sensors']
    if set(['total']).issubset(set(sensors)):
        local_power_component = True
    rf.add_reason(
        f"Local power component is {'not ' if not local_power_component else ''}reachable")
    return local_power_component


def startup_check() -> None:
    rf: ReasonFlow = ReasonFlow(
        name="Startup checks", auto_store_seconds=None, initiator='Device Component')
    tc = _check_temperature_component(rf)
    pc = _check_power_component(rf)
    if not pc or not tc:
        DelayTimer(300, startup_check)
    if startup_check_values.get('tc', not local_temperature_component) != local_temperature_component or startup_check_values.get('pc', not local_power_component) != local_power_component:
        rf.to_event(EventSeverity.INFO)
    startup_check_values['tc'] = tc
    startup_check_values['pc'] = pc
    return


def get_power_consumption() -> float:
    """
    Get the current power consumption.
    If local component is present gets the data from there.
    Fallback is to collect the data from the DB in the backend.

    :raises: TimeoutError
    """
    global local_power_component
    if local_power_component:
        get = requests.get(url="http://power/power", timeout=10)

        if get.status_code == 200:
            sensors: Dict[str, float] = get.json()['sensors']
            if 'total' not in sensors:
                raise ConnectionError(
                    "Not all sensor data was delivered locally")
            return float(sensors['total'])
        else:
            local_power_component = False
            raise ConnectionError(
                f"Local request status_code was {get.status_code}")

    jwt.v()
    try:
        get = requests.get(
            f"https://api.florianschleuss.de/sensor/sensors/names?customer_id={jwt.token.customer_id}&names[]=total",
            headers={'x-access-token': jwt.token._token})
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Connection time out")
    if get.json() is None:
        raise ConnectionError("No data was returned")
    data: Dict = get.json()['data'][0]
    if data['lastModified'] + 30 < time.time():
        Event("Power value received from backend is not up to date",
              event_severity=EventSeverity.IMPORTANT,
              initiator='Device Component').store()
        pass
    return float(data['value'])


def get_temperatures() -> Dict[str, float]:
    global local_temperature_component
    if local_temperature_component:
        # TODO prioritize local component
        return {}

    jwt.v()
    try:
        get = requests.get(
            f"https://api.florianschleuss.de/sensor/sensors/type/temperature?customer_id={jwt.token.customer_id}",
            headers={'x-access-token': jwt.token._token})
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Connection time out")
    if get.status_code != 200:
        raise ConnectionError(
            f"API request decliend (status_code:{get.status_code})")
    if get.json() is None:
        raise ConnectionError("No data was returned")
    data: List[Dict] = get.json()['data']
    temps = {}
    for item in data:
        if item['lastModified'] + 30 < time.time():
            Event("Temperature value received from backend is not up to date",
                  event_severity=EventSeverity.IMPORTANT,
                  details=[f"Sensor name: '{item['name']}'"],
                  initiator='Device Component')
            continue
        temps[item['name']] = float(item['value'])

    return temps


@sio.event
def connect():
    """
    Registers endpoint as soon as the WS is connected
    """
    sio.emit('customer_domain', CUSTOMER_DOMAIN)
    Event(f"Connected as '{CUSTOMER_DOMAIN}'!", initiator='Device Component',
          event_severity=EventSeverity.DEBUG).store()


@sio.event
def disconnect():
    Event(f"'{CUSTOMER_DOMAIN.capitalize()}' Disconnected!",
          initiator='Device Component', event_severity=EventSeverity.DEBUG).store()


@sio.on('task')  # type: ignore
def handle_task_event(data: dict):
    """
    Takes the task events with the data and hadles all the parsing into the appropriat actions

    :param data: Data with device_name, action and needed params to execute action
    """
    task: Task = Task.from_object(data)
    if not task.verify_action_params():
        return ReturnObject(status_code=422, error_code='paramsNotFound', message="Not all needed parameters are present").to_dict()

    if task.action is Action.SWITCH:
        if dc.switch_device(
                device_name=task.action_args['deviceName'],
                user=task.action_args['user']):
            return ReturnObject(status_code=200).to_dict()
    elif task.action is Action.ON:
        if dc.switch_device(
                device_name=task.action_args['deviceName'],
                user=task.action_args['user'],
                new_state=True):
            return ReturnObject(status_code=200).to_dict()
    elif task.action is Action.OFF:
        if dc.switch_device(
                device_name=task.action_args['deviceName'],
                user=task.action_args['user'],
                new_state=False):
            return ReturnObject(status_code=200).to_dict()
    elif task.action is Action.TIMER:
        if dc.switch_device(
                device_name=task.action_args['deviceName'],
                user=task.action_args['user'],
                new_state=task.action_args['state'],
                timer_seconds=task.action_args['delaySeconds']):
            return ReturnObject(status_code=200).to_dict()
    elif task.action is Action.STATE:
        device = dc.get_device_by_name(task.action_args['deviceName'])
        details = task.action_args.get('details', False)
        return ReturnObject(status_code=200, data=device.to_dict(full=details)).to_dict()
    elif task.action is Action.STATEALL:
        devices = dc.get_devices()
        details = task.action_args.get('details', False)
        return ReturnObject(status_code=200, data=[device.to_dict(full=details) for device in devices]).to_dict()
    elif task.action is Action.UPDATE:
        allowed_updates = ['power',
                           'displayed_name',
                           'displayed_description',
                           'gpio',
                           'hysteresis_seconds',
                           're_hysteresis_seconds',
                           'min_active_time_seconds',
                           'shutdown_time_seconds',
                           'host']
        device = dc.get_device_by_name(task.action_args['deviceName'])
        updates = task.action_args['updates']
        for u in updates:
            if (not 'key' in u) or (not 'value' in u):
                continue
            if not hasattr(device, u['key']):
                continue
            if u['key'] not in allowed_updates:
                continue
            setattr(device, u['key'], u['value'])
        dc.dump_config()
        return ReturnObject(status_code=200).to_dict()

    return ReturnObject(status_code=422, error_code='failedAction', message="The action was not successful. Refer to logs").to_dict()


if __name__ == "__main__":
    startup_check()
    retries: int = 0
    while not sio.connected and retries <= 10:
        try:
            sio.connect('https://api.florianschleuss.de', transports=['websocket'],
                        socketio_path="socket/socket.io", wait=False)
        except socketio.client.exceptions.ConnectionError as e:
            Event(f"SIO connect error",
                  details=[str(e)],
                  initiator='Device Component',
                  event_severity=EventSeverity.CRITICAL,
                  event_type=EventType.ERROR).store()
        time.sleep(10)
        retries += 1
    while True:
        start: float = datetime.datetime.now().timestamp()

        power: float
        temperatures: Dict[str, float]
        try:
            power = get_power_consumption()
            dc.tick(power)
        except ConnectionError as e:
            Event(f"Error while get_power_consumption()",
                  details=[str(e)],
                  initiator='Device Component',
                  event_severity=EventSeverity.IMPORTANT,
                  event_type=EventType.ERROR).store()
        except TimeoutError:
            Event(f"Timeout while get_power_consumption()",
                  initiator='Device Component',
                  event_severity=EventSeverity.IMPORTANT).store()

        try:
            temperatures = get_temperatures()
            dc.temperature_tick(temperatures)
        except ConnectionError as e:
            Event(f"Error while get_temperatures()",
                  details=[str(e)],
                  initiator='Device Component',
                  event_severity=EventSeverity.IMPORTANT,
                  event_type=EventType.ERROR).store()

        if (delta := (datetime.datetime.now().timestamp() - start)) < REFRESH_TIME_SECONDS:
            time.sleep(REFRESH_TIME_SECONDS - delta)
