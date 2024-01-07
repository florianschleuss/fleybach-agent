from enum import Enum
from typing import Dict, List, Optional, TypeVar

import requests
from requests.exceptions import ConnectionError
from utils.event import EventSeverity
from utils.reason import ReasonFlow
from utils.switchable.switchable import Switchable, TemperatureSafety

import RPi.GPIO as GPIO
GPIO.setwarnings(False)  # type: ignore

PowerSwitchable = TypeVar('PowerSwitchable')  # type: ignore
LocalDevice = TypeVar('LocalDevice')  # type: ignore
RemoteDevice = TypeVar('RemoteDevice')  # type: ignore
RemoteDeviceType = TypeVar('RemoteDeviceType')  # type: ignore
GPIO.setmode(GPIO.BCM)  # type: ignore


class PowerSwitchable(Switchable):
    def __init__(self,
                 power: int,
                 power_off_tolerance: int = 0,
                 *args,
                 **kwarags
                 ) -> None:
        super().__init__(*args, **kwarags)

        # Power consumption of this particular SW
        self.power: int = power

        # Power that may be bought before the device is allowed
        # to be turned off automatically
        self._power_off_tolerance: int = power_off_tolerance
        return

    @property
    def power_all(self):
        power_all: int = self.power
        for d in self._dependencies:
            if not d.state and isinstance(d, PowerSwitchable):
                power_all += d.power_all
        return power_all

    def to_dict(self, full=False) -> Dict:
        device_dict = super().to_dict(full=full)
        device_dict['power'] = self.power
        device_dict['power_all'] = self.power_all
        device_dict['power_off_tolerance'] = self._power_off_tolerance
        return device_dict


class LocalDevice(PowerSwitchable):
    def __init__(self,
                 gpio: int,
                 *args,
                 **kwarags) -> None:
        super().__init__(*args, **kwarags)

        # GPIO pin to which the device is connected
        self._gpio: int = gpio
        GPIO.setup(self._gpio, GPIO.OUT)  # type: ignore
        GPIO.output(gpio, GPIO.HIGH)  # type: ignore

    @classmethod
    def from_object(
            cls,
            object: Dict,
            dependencies: Optional[List[Switchable]] = None,
            updating_device: Optional[LocalDevice] = None
    ) -> LocalDevice:
        if 'name' not in object:
            raise Exception("No name given")
        if 'power' not in object:
            raise Exception("No power given")
        if 'gpio' not in object:
            raise Exception("No gpio given")
        if updating_device is None:
            device: LocalDevice = cls(name=object['name'],
                                      power=object['power'],
                                      gpio=object['gpio'])
        else:
            device: LocalDevice = updating_device
        if 'displayed_name' in object:
            device.displayed_name = object['displayed_name']
        if 'displayed_description' in object:
            device.displayed_description = object['displayed_description']
        if 'power_off_tolerance' in object:
            device._power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time_seconds' in object:
            device._shutdown_time_seconds = object['shutdown_time_seconds']
        if 'max_active_time_seconds' in object:
            device._max_active_time_seconds = object['max_active_time_seconds']
        if 'min_active_time_seconds' in object:
            device._min_active_time_seconds = object['min_active_time_seconds']
        if 'hysteresis_seconds' in object:
            device._hysteresis_seconds = object['hysteresis_seconds']
        if 're_hysteresis_seconds' in object:
            device._re_hysteresis_seconds = object['re_hysteresis_seconds']
        if 'importance' in object:
            device._importance = object['importance']
        if 'temperature_safety' in object:
            device._temperature_safety = TemperatureSafety.from_list(
                object['temperature_safety'])
            pass
        if dependencies:
            device._dependencies = dependencies
        return device

    # @Override

    def to_dict(self, full=False) -> Dict:
        device_dict = super().to_dict(full=full)
        device_dict['gpio'] = self._gpio
        return device_dict

    # @Override

    def _set_hardware_io(self,
                         state: bool,
                         reason_flow: Optional[ReasonFlow] = None) -> bool:
        # TODO: verify success
        if state:
            GPIO.output(self._gpio, GPIO.LOW)  # type: ignore
        else:
            GPIO.output(self._gpio, GPIO.HIGH)  # type: ignore
        return True


class RemoteDeviceType(Enum):
    DEFAULT = 'default'
    SONOFF = 'sonoff'
    TASMOTA = 'tasmota'

    @classmethod
    def from_str(cls, str: str) -> RemoteDeviceType:
        if 'sonoff' in str.lower():
            return cls.SONOFF
        elif 'tasmota' in str.lower():
            return cls.TASMOTA
        raise Exception("No matching device type given")


class RemoteDevice(PowerSwitchable):
    def __init__(self,
                 host: str,
                 device_type: RemoteDeviceType,
                 *args,
                 **kwarags
                 ) -> None:
        super().__init__(*args, **kwarags)

        self._host: str = host

        self._device_type: RemoteDeviceType = device_type

    @classmethod
    def from_object(
        cls,
        object: Dict,
        dependencies: Optional[List[Switchable]] = None,
        updating_device: Optional[RemoteDevice] = None
    ) -> RemoteDevice:
        if 'name' not in object:
            raise Exception("No name given")
        if 'power' not in object:
            raise Exception("No power given")
        if 'host' not in object:
            raise Exception("No host given")
        if 'device_type' not in object:
            raise Exception("No device_type given")
        if updating_device is None:
            device: RemoteDevice = cls(
                name=object['name'],
                power=object['power'],
                host=object['host'],
                device_type=RemoteDeviceType.from_str(object['device_type']))
        else:
            device: RemoteDevice = updating_device
        device: RemoteDevice = cls(
            name=object['name'],
            power=object['power'],
            host=object['host'],
            device_type=RemoteDeviceType.from_str(object['device_type']))
        if 'displayed_name' in object:
            device.displayed_name = object['displayed_name']
        if 'displayed_description' in object:
            device.displayed_description = object['displayed_description']
        if 'power_off_tolerance' in object:
            device._power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time_seconds' in object:
            device._shutdown_time_seconds = object['shutdown_time_seconds']
        if 'max_active_time_seconds' in object:
            device._max_active_time_seconds = object['max_active_time_seconds']
        if 'min_active_time_seconds' in object:
            device._min_active_time_seconds = object['min_active_time_seconds']
        if 'hysteresis_seconds' in object:
            device._hysteresis_seconds = object['hysteresis_seconds']
        if 're_hysteresis_seconds' in object:
            device._re_hysteresis_seconds = object['re_hysteresis_seconds']
        if 'importance' in object:
            device._importance = object['importance']
        if 'temperature_safety' in object:
            device._temperature_safety = TemperatureSafety.from_list(
                object['temperature_safety'])
            pass
        if dependencies:
            device._dependencies = dependencies
        return device

        # @Override

    def to_dict(self, full=False) -> Dict:
        device_dict = super().to_dict(full=full)
        device_dict['host'] = self._host
        device_dict['device_type'] = str(self._device_type)
        return device_dict

    # @Override
    def _set_hardware_io(self,
                         state: bool,
                         reason_flow: Optional[ReasonFlow] = None) -> bool:
        url_params: str = ""
        if self._device_type == RemoteDeviceType.SONOFF:
            if state:
                url_params = "control?cmd=GPIO,12,1"
            else:
                url_params = "control?cmd=GPIO,12,0"
        elif self._device_type == RemoteDeviceType.TASMOTA:
            if state:
                url_params = "cm?cmnd=Power%20on"
            else:
                url_params = "cm?cmnd=Power%20off"

        try:
            r: requests.Response = requests.get(
                f"http://{self._host}/{url_params}")
            if r.status_code == 200:
                return True
        except ConnectionError as e:
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Connection error for {self.name} to host {self._host} trying to switch to '{state}'\n{e}")
                reason_flow.to_event(EventSeverity.IMPORTANT)
            return False
        if reason_flow is not None:
            reason_flow.add_reason(
                f"Unsuccessful switching for {self.name} to host {self._host} trying to switch to '{state}'")
            reason_flow.to_event(EventSeverity.IMPORTANT)
        return False
