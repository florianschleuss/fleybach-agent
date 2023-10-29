from enum import Enum
from typing import List, TypeVar, Union

import requests
from requests.exceptions import ConnectionError
from utils.switchable.switchable import Switchable

import RPi.GPIO as GPIO

PowerSwitchable = TypeVar('PowerSwitchable')
GPIO.setmode(GPIO.BCM)  # type: ignore


class PowerSwitchable(Switchable):
    def __init__(self,
                 name: str,
                 power: int,
                 power_off_tolerance: int = 0,
                 dependencies: List[Union[Switchable, PowerSwitchable]] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0
                 ) -> None:
        super().__init__(name=name,
                         dependencies=dependencies,
                         shutdown_time=shutdown_time,
                         max_active_time=max_active_time,
                         min_active_time=min_active_time,
                         hysteresis=hysteresis,
                         re_hysteresis=re_hysteresis)

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
                 dependencies: List[Union[Switchable, PowerSwitchable]] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0) -> None:
        super().__init__(name,
                         power,
                         power_off_tolerance,
                         dependencies,
                         shutdown_time,
                         max_active_time,
                         min_active_time,
                         hysteresis,
                         re_hysteresis)

        # GPIO pin to which the device is connected
        self._gpio: int = gpio
        GPIO.setup(self._gpio, GPIO.OUT)  # type: ignore
        GPIO.output(gpio, GPIO.HIGH)  # type: ignore

    # @Override
    def _set_hardware_io(self, state: bool) -> bool:
        # TODO: verify success
        if state:
            GPIO.output(self._gpio, GPIO.LOW)  # type: ignore
        else:
            GPIO.output(self._gpio, GPIO.HIGH)  # type: ignore
        return True


class RemoteDeviceType(Enum):
    SONOFF = 0
    TASMOTA = 1


class RemoteDevice(PowerSwitchable):
    def __init__(self,
                 name: str,
                 power: int,
                 host: str,
                 device_type: RemoteDeviceType,
                 power_off_tolerance: int = 0,
                 dependencies: List[Union[Switchable, PowerSwitchable]] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0) -> None:
        super().__init__(name,
                         power,
                         power_off_tolerance,
                         dependencies,
                         shutdown_time,
                         max_active_time,
                         min_active_time,
                         hysteresis,
                         re_hysteresis)

        self._host: str = host

        self._devcive_type: RemoteDeviceType = device_type

    # @Override
    def _set_hardware_io(self, state: bool) -> bool:
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
            return False
        return False
