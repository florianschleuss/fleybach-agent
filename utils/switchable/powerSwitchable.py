"""Power Switchable"""
from __future__ import annotations
from enum import Enum
import json
from typing import Dict, List, Optional

import requests
from utils.event import EventSeverity
from utils.reason import ReasonFlow
from utils.switchable.switchable import Switchable, TemperatureSafety

import RPi.GPIO as GPIO



# PowerSwitchable = TypeVar('PowerSwitchable')  # type: ignore
# LocalDevice = TypeVar('LocalDevice')  # type: ignore
# RemoteDevice = TypeVar('RemoteDevice')  # type: ignore
# RemoteDeviceType = TypeVar('RemoteDeviceType')  # type: ignore
# HomeAssistantDevice = TypeVar('HomeAssistantDevice')  # type: ignore
# HomeAssistantDeviceType = TypeVar('HomeAssistantDeviceType')  # type: ignore
def init_gpio() -> None:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)


class PowerSwitchable(Switchable):
    def __init__(self,
                 power: int,
                 power_off_tolerance: int = 0,
                 *args,
                 **kwargs
                 ) -> None:
        super().__init__(*args, **kwargs)

        # Power consumption of this particular SW
        self.power: int = power

        # Maximum power deficit (W) tolerated before this
        # device may be turned off automatically
        self.power_off_tolerance: int = power_off_tolerance
        return

    @property
    def power_all(self):
        """
        Sums power consumption of self and all disabled dependencies
        """
        power_all: int = self.power
        for d in self._dependencies:
            if not d.state and isinstance(d, PowerSwitchable):
                power_all += d.power_all
        return power_all

    def to_dict(self, full=False) -> Dict:
        device_dict = super().to_dict(full=full)  # type: ignore[attr-defined]
        device_dict['power'] = self.power
        device_dict['power_all'] = self.power_all
        device_dict['power_off_tolerance'] = self.power_off_tolerance
        return device_dict


class LocalDevice(PowerSwitchable):
    def __init__(self,
                 gpio: int,
                 *args,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        init_gpio()
        # GPIO pin to which the device is connected
        self._gpio: int = gpio
        GPIO.setup(self._gpio, GPIO.OUT)
        GPIO.output(self._gpio, GPIO.HIGH)

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
            device.power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time_seconds' in object:
            device.shutdown_time_seconds = object['shutdown_time_seconds']
        if 'max_active_time_seconds' in object:
            device.max_active_time_seconds = object['max_active_time_seconds']
        if 'min_active_time_seconds' in object:
            device.min_active_time_seconds = object['min_active_time_seconds']
        if 'disable_automatic_management' in object:
            device.disable_automatic_management = object['disable_automatic_management']
        if 'hysteresis_seconds' in object:
            device.hysteresis_seconds = object['hysteresis_seconds']
        if 're_hysteresis_seconds' in object:
            device.re_hysteresis_seconds = object['re_hysteresis_seconds']
        if 'importance' in object:
            device.importance = object['importance']
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
    def from_str(cls, strng: str) -> RemoteDeviceType:
        if 'sonoff' in strng.lower():
            return cls.SONOFF
        elif 'tasmota' in strng.lower():
            return cls.TASMOTA
        return cls.DEFAULT


class RemoteDevice(PowerSwitchable):
    def __init__(self,
                 host: str,
                 device_type: RemoteDeviceType,
                 *args,
                 **kwargs
                 ) -> None:
        super().__init__(*args, **kwargs)

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
        # device: RemoteDevice = cls(
        #     name=object['name'],
        #     power=object['power'],
        #     host=object['host'],
        #     device_type=RemoteDeviceType.from_str(object['device_type']))
        if 'displayed_name' in object:
            device.displayed_name = object['displayed_name']
        if 'displayed_description' in object:
            device.displayed_description = object['displayed_description']
        if 'power_off_tolerance' in object:
            device.power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time_seconds' in object:
            device.shutdown_time_seconds = object['shutdown_time_seconds']
        if 'disable_automatic_management' in object:
            device.disable_automatic_management = object['disable_automatic_management']
        if 'max_active_time_seconds' in object:
            device.max_active_time_seconds = object['max_active_time_seconds']
        if 'min_active_time_seconds' in object:
            device.min_active_time_seconds = object['min_active_time_seconds']
        if 'hysteresis_seconds' in object:
            device.hysteresis_seconds = object['hysteresis_seconds']
        if 're_hysteresis_seconds' in object:
            device.re_hysteresis_seconds = object['re_hysteresis_seconds']
        if 'importance' in object:
            device.importance = object['importance']
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
                url_params = "cm?cmnd=Power%20On"
            else:
                url_params = "cm?cmnd=Power%20Off"

        try:
            r: requests.Response = requests.get(
                f"http://{self._host}/{url_params}", timeout=5)
            if r.ok:
                return True
        except requests.exceptions.ConnectionError as e:
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

# TODO: Real Power Consumption from LG Systems


class HomeAssistantDeviceType(Enum):
    DEFAULT = 'default'
    LGWATERHEATER = 'lgwaterheater'
    LGHEATPUMP = 'lgheatpump'

    @classmethod
    def from_str(cls, str: str) -> HomeAssistantDeviceType:
        if 'lgwaterheater' in str.lower():
            return cls.LGWATERHEATER
        elif 'lgheatpump' in str.lower():
            return cls.LGHEATPUMP

        raise Exception("No matching device type given")


class HomeAssistantDevice(PowerSwitchable):
    def __init__(self,
                 entity_id: str,
                 device_type: HomeAssistantDeviceType,
                 *args,
                 **kwargs
                 ) -> None:
        super().__init__(*args, **kwargs)

        self._entity_id: str = entity_id

        self._device_type: HomeAssistantDeviceType = device_type

    @classmethod
    def from_object(
        cls,
        object: Dict,
        dependencies: Optional[List[Switchable]] = None,
        updating_device: Optional[HomeAssistantDevice] = None
    ) -> HomeAssistantDevice:
        if 'name' not in object:
            raise Exception("No name given")
        if 'power' not in object:
            raise Exception("No power given")
        if 'entity_id' not in object:
            raise Exception("No entity_id given")
        if 'device_type' not in object:
            raise Exception("No device_type given")
        if updating_device is None:
            device: HomeAssistantDevice = cls(
                name=object['name'],
                power=object['power'],
                entity_id=object['entity_id'],
                device_type=HomeAssistantDeviceType.from_str(object['device_type']))
        else:
            device: HomeAssistantDevice = updating_device
        # device: HomeAssistantDevice = cls(
        #     name=object['name'],
        #     power=object['power'],
        #     entity_id=object['entity_id'],
        #     device_type=HomeAssistantDeviceType.from_str(object['device_type']))
        if 'displayed_name' in object:
            device.displayed_name = object['displayed_name']
        if 'displayed_description' in object:
            device.displayed_description = object['displayed_description']
        if 'power_off_tolerance' in object:
            device.power_off_tolerance = object['power_off_tolerance']
        if 'shutdown_time_seconds' in object:
            device.shutdown_time_seconds = object['shutdown_time_seconds']
        if 'disable_automatic_management' in object:
            device.disable_automatic_management = object['disable_automatic_management']
        if 'max_active_time_seconds' in object:
            device.max_active_time_seconds = object['max_active_time_seconds']
        if 'min_active_time_seconds' in object:
            device.min_active_time_seconds = object['min_active_time_seconds']
        if 'hysteresis_seconds' in object:
            device.hysteresis_seconds = object['hysteresis_seconds']
        if 're_hysteresis_seconds' in object:
            device.re_hysteresis_seconds = object['re_hysteresis_seconds']
        if 'importance' in object:
            device.importance = object['importance']
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
        device_dict['entity_id'] = self._entity_id
        device_dict['device_type'] = str(self._device_type)
        return device_dict

    # @Override
    def _set_hardware_io(self,
                         state: bool,
                         reason_flow: Optional[ReasonFlow] = None) -> bool:
        webhook_name: str = ""
        payload: dict = {}
        if self._device_type == HomeAssistantDeviceType.LGWATERHEATER:
            webhook_name = "SetWaterHeaterTemperature"
            if state:
                payload = {'value': 55}
            else:
                payload = {'value': 45}
        elif self._device_type == HomeAssistantDeviceType.LGHEATPUMP:
            webhook_name = "SetHeatPumpRelativeTemperature"
            if state:
                payload = {'value': 10}
            else:
                payload = {'value': -10}
            pass

        try:
            headers: dict = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmMzAzNjcyZThkY2I0MWE3Yjc0YTczYmMxZGMwN2QyMiIsImlhdCI6MTcyODMyOTM4MywiZXhwIjoyMDQzNjg5MzgzfQ.y94glnLujipP7M278OObikHYn4hnD7W4VcdXJd4zPco'  # TODO: Remove key before commit
            }
            r: requests.Response = requests.post(
                f"http://192.168.178.224:8123/api/webhook/{webhook_name}",
                headers=headers, data=json.dumps(payload), timeout=5
            )
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError as e:
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Connection error for {self.name} to Homeassistant for '{self._entity_id}' trying to switch to '{state}'\n{e}")
                reason_flow.to_event(EventSeverity.IMPORTANT)
            return False
        if reason_flow is not None:
            reason_flow.add_reason(
                f"Unsuccessful switching for {self.name} to host Homeassistant for '{self._entity_id}' trying to switch to '{state}'")
            reason_flow.to_event(EventSeverity.IMPORTANT)
        return False
