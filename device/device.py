from datetime import datetime
import os
from typing import Dict, List, Optional
import yaml

from utils.reason import ReasonFlow
from utils.switchable.powerSwitchable import LocalDevice, PowerSwitchable, RemoteDevice  # noqa


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

        # Device list to pre-populate the device list
        self._devices: Dict[str, PowerSwitchable]
        if devices is None:
            self._devices = self.update_devices_from_config()
        else:
            self._devices = devices

        # List of the last power_consumption values
        # to calc an average over all of them
        self._avrg_power_consumtion: List[float] = []

    def _devices_in_relevance_order(self,
                                    state: bool = False,
                                    reverse: bool = False,
                                    reason_flow: Optional[ReasonFlow] = None,
                                    ) -> List[PowerSwitchable]:
        """
        Returns a list of devices in a specific order based on their relevance.

        :param state: Filter devices by their state (default is off).
        :param reverse: Set to True to reverse the sorting order.

        :return: A list of devices sorted by their rest active time,
                with optional filtering and sorting direction.
        """
        devices = [device for device in self._devices.values()
                   if device._state == state]
        devices = sorted(
            devices,
            key=lambda device: (device._importance, device.rest_active_time),
            reverse=not reverse)
        if reason_flow is not None:
            reason_flow.add_reason(
                f"Relevant devices in state '{state}' are {[d.name for d in devices]} (reverse: {reverse})")  # noqa
        return devices

    def _deadline_check(self) -> None:
        # log('Deadline check run', ['info', 'deadline-check'])

        # for name, device in self.devices.items():
        #     if device.get_rest_time() > 0:
        #         device.manual_switch(True, 'DeadlineCheck')
        #         DelayTimer(device.get_rest_time(), device.manual_switch, [
        #                    False, 'DeadlineCheck'])
        #         rest_time_str: str = "{}:{}".format(
        #             int(device.get_rest_time() / 60),
        #             device.get_rest_time() % 60)
        #         log('{} needed {} more time to fullfill worktime for today'
        #             .format(device.get_name().replace("_", "-")
        #                     .capitalize(), rest_time_str),
        #             ['info', 'deadline-check'])

        # # Log day-summary
        # for name, device in self.devices.items():
        #     worked_time: int = device.get_worked_time()
        #     worked_str: str = "{}:{}:{}".format(
        #         int(worked_time / 3600), int(worked_time % 3600 / 60),
        #         worked_time % 3600 % 60)
        #     log('{} run for {} today'.format(device.get_name()
        #                                      .replace("_", "-")
        #                                      .capitalize(), worked_str),
        #         ['info', 'deadline-check'])
        return

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

    def tick(self,
             current_power_consumption: float) -> None:
        """
        Update the state of devices based on available power.

        :param current_power_consumption: The current power consumption.
        """
        # Calculate available power based on average power consumption
        while len(self._avrg_power_consumtion) >= 20:
            self._avrg_power_consumtion.pop(0)
        self._avrg_power_consumtion.append(current_power_consumption)

        available_power = sum(self._avrg_power_consumtion) / \
            len(self._avrg_power_consumtion) * -1

        # ReasonFlow to store all decisions made througout the process
        reason_flow: ReasonFlow = ReasonFlow(
            name=f"Tick at {datetime.now()}",
            initial_comment=f"Tick with {available_power} available power")

        # Not enough power present
        if available_power <= 0:
            devices = self._devices_in_relevance_order(state=True,
                                                       reverse=True,
                                                       reason_flow=reason_flow)
            for device in devices:
                if device._power_off_tolerance > available_power:
                    if device.set_state(False,
                                        user='Automation',
                                        reason_flow=reason_flow.split(f"Try to set state to '{False}' for '{device.name}' with user 'Automation'")):  # noqa
                        current_power_consumption -= device.power_all
        # To much power present
        else:
            devices = self._devices_in_relevance_order(
                state=False, reverse=False, reason_flow=reason_flow)

            for device in devices:
                if (
                    device.power_all < available_power
                    and
                    device.rest_active_time > 0
                ):
                    drf = reason_flow.split(f"Try to set state to '{True}' for '{device.name}' requiring {device.power_all} power with user 'Automation'")  # noqa
                    if device.set_state(True,
                                        user='Automation',
                                        reason_flow=drf):
                        available_power -= device.power_all

        # TODO deadline check
        # if datetime.now().hour == 17 and not self.deadline_check:
        #     self.deadline_check = True
        #     self._deadline_check()
