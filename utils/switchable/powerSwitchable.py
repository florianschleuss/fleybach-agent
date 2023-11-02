from enum import Enum
from typing import Dict, List, Optional, TypeVar

import requests
from requests.exceptions import ConnectionError
from utils.event import EventCategory
from utils.reason import ReasonFlow
from utils.switchable.switchable import Switchable

import RPi.GPIO as GPIO

PowerSwitchable = TypeVar('PowerSwitchable')
LocalDevice = TypeVar('LocalDevice')
RemoteDevice = TypeVar('RemoteDevice')
RemoteDeviceType = TypeVar('RemoteDeviceType')
GPIO.setmode(GPIO.BCM)  # type: ignore


class PowerSwitchable(Switchable):
    def __init__(self,
                 name: str,
                 power: int,
                 power_off_tolerance: int = 0,
                 dependencies: List[Switchable] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0,
                 importance: int = 0
                 ) -> None:
        super().__init__(name=name,
                         dependencies=dependencies,
                         shutdown_time=shutdown_time,
                         max_active_time=max_active_time,
                         min_active_time=min_active_time,
                         hysteresis=hysteresis,
                         re_hysteresis=re_hysteresis,
                         importance=importance)

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


class LocalDevice(PowerSwitchable):
    def __init__(self,
                 name: str,
                 power: int,
                 gpio: int,
                 power_off_tolerance: int = 0,
                 dependencies: List[Switchable] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0,
                 importance: int = 0) -> None:
        super().__init__(name,
                         power,
                         power_off_tolerance,
                         dependencies,
                         shutdown_time,
                         max_active_time,
                         min_active_time,
                         hysteresis,
                         re_hysteresis,
                         importance)

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
        if 'power_off_tolerance' in object:
            device._power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time' in object:
            device._shutdown_time = object['shutdown_time']
        if 'max_active_time' in object:
            device._max_active_time = object['max_active_time']
        if 'min_active_time' in object:
            device._min_active_time = object['min_active_time']
        if 'hysteresis' in object:
            device._hysteresis = object['hysteresis']
        if 're_hysteresis' in object:
            device._re_hysteresis = object['re_hysteresis']
        if dependencies:
            device._dependencies = dependencies
        return device

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
    SONOFF = 0
    TASMOTA = 1

    @classmethod
    def from_str(cls, str: str) -> RemoteDeviceType:
        if str.lower() == 'sonoff':
            return cls.SONOFF
        elif str.lower() == 'tasmota':
            return cls.TASMOTA
        raise Exception("No matching device type given")


class RemoteDevice(PowerSwitchable):
    def __init__(self,
                 name: str,
                 power: int,
                 host: str,
                 device_type: RemoteDeviceType,
                 power_off_tolerance: int = 0,
                 dependencies: List[Switchable] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0,
                 importance: int = 0) -> None:
        super().__init__(name,
                         power,
                         power_off_tolerance,
                         dependencies,
                         shutdown_time,
                         max_active_time,
                         min_active_time,
                         hysteresis,
                         re_hysteresis,
                         importance)

        self._host: str = host

        self._devcive_type: RemoteDeviceType = device_type

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
        if 'power_off_tolerance' in object:
            device._power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time' in object:
            device._shutdown_time = object['shutdown_time']
        if 'max_active_time' in object:
            device._max_active_time = object['max_active_time']
        if 'min_active_time' in object:
            device._min_active_time = object['min_active_time']
        if 'hysteresis' in object:
            device._hysteresis = object['hysteresis']
        if 're_hysteresis' in object:
            device._re_hysteresis = object['re_hysteresis']
        if dependencies:
            device._dependencies = dependencies
        return device

    # @Override
    def _set_hardware_io(self,
                         state: bool,
                         reason_flow: Optional[ReasonFlow] = None) -> bool:
        url_params: str = ""
        if self._devcive_type == RemoteDeviceType.SONOFF:
            if state:
                url_params = "control?cmd=GPIO,12,1"
            else:
                url_params = "control?cmd=GPIO,12,0"
        elif self._devcive_type == RemoteDeviceType.TASMOTA:
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
                reason_flow.add_reason(f"Connection error for {self.name} to host {self._host} trying to switch to {state}\n{e}")  # noqa
                reason_flow.to_event(EventCategory.IMPORTANT)
            return False
        if reason_flow is not None:
            reason_flow.add_reason(f"Unsuccessful switching for {self.name} to host {self._host} trying to switch to {state}")  # noqa
            reason_flow.to_event(EventCategory.IMPORTANT)
        return False
