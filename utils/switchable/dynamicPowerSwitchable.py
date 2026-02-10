# utils/switchable/dynamicPowerSwitchable.py
from __future__ import annotations

from enum import Enum
import json
import time
from typing import Dict, Optional, List, Any

import requests

from utils.event import EventSeverity
from utils.reason import ReasonFlow
from utils.switchable.switchable import Switchable
from utils.switchable.powerSwitchable import PowerSwitchable


class HeatPumpMode(Enum):
    STANDBY = 0
    FULL = 1

    @classmethod
    def from_int(cls, value: int) -> "HeatPumpMode":
        return cls.FULL if value == 1 else cls.STANDBY

    def to_int(self) -> int:
        return 1 if self is HeatPumpMode.FULL else 0


class HardwareIoEndpointMode(Enum):
    NONE = "none"
    HOMEASSISTANT = "homeassistant"

    @classmethod
    def from_str(cls, value: str) -> "HardwareIoEndpointMode":
        if not value:
            return cls.NONE
        value = value.lower()
        if value in ("ha", "homeassistant", "home_assistant"):
            return cls.HOMEASSISTANT
        return cls.NONE


class DynamicPowerSwitchable(PowerSwitchable):
    """
    Logical heat pump controller (no direct GPIO/relay).
    It computes the heat pump return setpoint and HEAT/WAIT decision and can
    optionally send the setpoint to a hardware endpoint (currently Home Assistant).

    - Inherits PowerSwitchable so it fits into DeviceController.
    - Appears in config under `dynamic_devices`.
    - Extra fields:
        * controlled_device_name : name of real HP switch device (e.g. 'lg_heat_pump')
        * buffer_sensor_name     : sensor for buffer top temp
        * outdoor_sensor_name    : sensor for outdoor temp
        * hardware_io_endpoint_mode: where to send setpoints (NONE / HOMEASSISTANT)
    """

    def __init__(self,
                 controlled_device_name: str,
                 buffer_sensor_name: str,
                 outdoor_sensor_name: str,
                 heat_pump_mode: HeatPumpMode = HeatPumpMode.STANDBY,
                 outdoor_temp_cold_ref: float = -10.0,
                 outdoor_temp_warm_ref: float = 15.0,
                 design_supply_temp_max: float = 55.0,
                 design_supply_temp_min: float = 25.0,
                 pv_temp_boost_factor: float = 1.0,
                 param_update_delay: int = 60,
                 buffer_delta_supply: float = 5.0,
                 hardware_io_endpoint_mode: HardwareIoEndpointMode = HardwareIoEndpointMode.NONE,
                 ha_base_url: Optional[str] = None,
                 ha_setpoint_webhook: Optional[str] = None,
                 ha_token: Optional[str] = None,
                 *args,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # what this logic device actually controls (for ON/OFF)
        self.controlled_device_name: str = controlled_device_name
        self.buffer_sensor_name: str = buffer_sensor_name
        self.outdoor_sensor_name: str = outdoor_sensor_name

        # config params
        self.heat_pump_mode: HeatPumpMode = heat_pump_mode
        self.outdoor_temp_cold_ref: float = outdoor_temp_cold_ref
        self.outdoor_temp_warm_ref: float = outdoor_temp_warm_ref
        self.design_supply_temp_max: float = design_supply_temp_max
        self.design_supply_temp_min: float = design_supply_temp_min
        self.pv_temp_boost_factor: float = pv_temp_boost_factor
        self.param_update_delay: int = param_update_delay
        self.buffer_delta_supply: float = buffer_delta_supply

        # IO endpoint config
        self.hardware_io_endpoint_mode: HardwareIoEndpointMode = hardware_io_endpoint_mode
        self.ha_base_url: Optional[str] = ha_base_url
        self.ha_setpoint_webhook: Optional[str] = ha_setpoint_webhook
        self.ha_token: Optional[str] = ha_token

        # derived
        self.house_supply_setpoint: float = 0.0
        self.supply_gradient: float = 0.0
        self.pv_boost_temp: float = 0.0
        self.heat_pump_return_setpoint: float = 0.0
        self.heat_pump_heat_wait: bool = False
        self._io_triggered_from_update: bool = False

        # hysteresis for parameter sending
        self._last_param_update_ts: float = 0.0
        self._last_sent_values: Dict[str, float | bool | int] = {}

    # ---------- YAML factory ----------

    @classmethod
    def from_object(
        cls,
        obj: Dict[str, Any],
        dependencies: Optional[List[Switchable]] = None,
        updating_device: Optional["DynamicPowerSwitchable"] = None
    ) -> "DynamicPowerSwitchable":
        """
        Build or update a DynamicPowerSwitchable from config dict.
        """
        required = ["name", "controlled_device", "buffer_sensor", "outdoor_sensor"]
        for key in required:
            if key not in obj:
                raise Exception(f"No {key} given for DynamicPowerSwitchable")

        hardware_mode = HardwareIoEndpointMode.from_str(
            obj.get("hardware_io_endpoint_mode", "none")
        )

        if updating_device is None:
            device: DynamicPowerSwitchable = cls(
                name=obj["name"],
                power=obj.get("power", 0),  # logical device: power often 0
                controlled_device_name=obj["controlled_device"],
                buffer_sensor_name=obj["buffer_sensor"],
                outdoor_sensor_name=obj["outdoor_sensor"],
                heat_pump_mode=HeatPumpMode.from_int(obj.get("heat_pump_mode", obj.get("wp_on", 0))),
                outdoor_temp_cold_ref=obj.get("outdoor_temp_cold_ref", -10.0),
                outdoor_temp_warm_ref=obj.get("outdoor_temp_warm_ref", 15.0),
                design_supply_temp_max=obj.get("design_supply_temp_max", 55.0),
                design_supply_temp_min=obj.get("design_supply_temp_min", 25.0),
                pv_temp_boost_factor=obj.get("pv_temp_boost_factor", 1.0),
                param_update_delay=obj.get("param_update_delay", 60),
                buffer_delta_supply=obj.get("buffer_delta_supply", 5.0),
                hardware_io_endpoint_mode=hardware_mode,
                ha_base_url=obj.get("ha_base_url"),
                ha_setpoint_webhook=obj.get("ha_setpoint_webhook"),
                ha_token=obj.get("ha_token"),
            )
        else:
            device = updating_device
            device.controlled_device_name = obj["controlled_device"]
            device.buffer_sensor_name = obj["buffer_sensor"]
            device.outdoor_sensor_name = obj["outdoor_sensor"]
            device.heat_pump_mode = HeatPumpMode.from_int(
                obj.get("heat_pump_mode", obj.get("wp_on", device.wp_on))
            )
            device.outdoor_temp_cold_ref = obj.get(
                "outdoor_temp_cold_ref", device.outdoor_temp_cold_ref
            )
            device.outdoor_temp_warm_ref = obj.get(
                "outdoor_temp_warm_ref", device.outdoor_temp_warm_ref
            )
            device.design_supply_temp_max = obj.get(
                "design_supply_temp_max", device.design_supply_temp_max
            )
            device.design_supply_temp_min = obj.get(
                "design_supply_temp_min", device.design_supply_temp_min
            )
            device.pv_temp_boost_factor = obj.get(
                "pv_temp_boost_factor", device.pv_temp_boost_factor
            )
            device.param_update_delay = obj.get(
                "param_update_delay", device.param_update_delay
            )
            device.buffer_delta_supply = obj.get(
                "buffer_delta_supply", device.buffer_delta_supply
            )
            device.hardware_io_endpoint_mode = hardware_mode
            device.ha_base_url = obj.get("ha_base_url", device.ha_base_url)
            device.ha_setpoint_webhook = obj.get(
                "ha_setpoint_webhook", device.ha_setpoint_webhook
            )
            device.ha_token = obj.get("ha_token", device.ha_token)

        # generic display / switchable params
        if "displayed_name" in obj:
            device.displayed_name = obj["displayed_name"]
        if "displayed_description" in obj:
            device.displayed_description = obj["displayed_description"]
        if "disable_automatic_management" in obj:
            device.disable_automatic_management = obj["disable_automatic_management"]

        if "hysteresis_seconds" in obj:
            device.hysteresis_seconds = obj["hysteresis_seconds"]
        if "re_hysteresis_seconds" in obj:
            device.re_hysteresis_seconds = obj["re_hysteresis_seconds"]
        if "importance" in obj:
            device.importance = obj["importance"]

        if dependencies:
            device._dependencies = dependencies

        return device

    # ---------- helper props ----------

    @property
    def wp_on(self) -> int:
        return self.heat_pump_mode.to_int()

    @wp_on.setter
    def wp_on(self, v: int) -> None:
        self.heat_pump_mode = HeatPumpMode.from_int(v)

    # ---------- core control logic ----------

    def _compute_house_supply_setpoint(self, outdoor_temp: float) -> float:
        T_out = outdoor_temp
        T_cold = self.outdoor_temp_cold_ref
        T_warm = self.outdoor_temp_warm_ref
        VL_max = self.design_supply_temp_max
        VL_min = self.design_supply_temp_min

        if T_warm == T_cold:
            self.supply_gradient = 0.0
            return VL_max

        if T_out > T_warm:
            self.supply_gradient = 0.0
            return VL_min
        if T_out < T_cold:
            self.supply_gradient = 0.0
            return VL_max

        supply_gradient = (VL_max - VL_min) / (T_warm - T_cold)
        self.supply_gradient = supply_gradient
        return VL_min + (T_warm - T_out) * supply_gradient

    def _compute_pv_boost_temp(self, grid_power_balance: float) -> float:
        if grid_power_balance < 0.0:
            export_kw = grid_power_balance / -1000.0
            return self.pv_temp_boost_factor * export_kw
        return 0.0

    def _compute_heat_wait_full_mode(self,
                                     buffer_temp_top: float,
                                     house_supply_setpoint: float) -> bool:
        return buffer_temp_top + self.buffer_delta_supply < house_supply_setpoint

    def _decide_heat_wait(self,
                          buffer_temp_top: float,
                          house_supply_setpoint: float,
                          grid_power_balance: float) -> bool:
        pv_surplus = grid_power_balance < 0.0

        if self.heat_pump_mode is HeatPumpMode.STANDBY:
            # Standby: run only when PV surplus
            return pv_surplus

        # Full mode: run if buffer too cold OR PV surplus
        buffer_needs_heat = self._compute_heat_wait_full_mode(
            buffer_temp_top=buffer_temp_top,
            house_supply_setpoint=house_supply_setpoint
        )
        return buffer_needs_heat or pv_surplus

    # ---------- hardware IO: Home Assistant ----------

    def _send_setpoint_to_homeassistant(self,
                                        reason_flow: Optional[ReasonFlow] = None) -> None:
        """
        Send the current heat_pump_return_setpoint (RL_WPSoll) to Home Assistant,
        using a webhook that accepts JSON payload.

        Expects:
          - ha_base_url like "http://192.168.178.224:8123"
          - ha_setpoint_webhook like "SetHeatPumpReturnSetpoint"
        Payload example:
          { "rl_wp_soll": 42.5, "device": "lg_heat_pump_dynamic" }
        """
        if not self.ha_base_url or not self.ha_setpoint_webhook:
            return  # no HA endpoint configured

        url = f"{self.ha_base_url.rstrip('/')}/api/webhook/{self.ha_setpoint_webhook}"
        payload = {
            "rl_wp_soll": round(self.heat_pump_return_setpoint, 2),
            "mode": self.heat_pump_heat_wait,
        }
        headers = {"Content-Type": "application/json"}
        if self.ha_token:
            headers["Authorization"] = f"Bearer {self.ha_token}"

        try:
            r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=5)
            if r.status_code != 200 and reason_flow is not None:
                reason_flow.add_reason(
                    f"Unsuccessful RL_WPSoll update to HA "
                    f"({r.status_code}): {r.text}"
                )
        except requests.exceptions.RequestException as e:
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Error sending RL_WPSoll to HA: {type(e).__name__} – {e}"
                )

    # ---------- main control entrypoint ----------

    def update_control(self,
                       buffer_temp_top: float,
                       outdoor_temp: float,
                       grid_power_balance: float,
                       *,
                       now_ts: Optional[float] = None,
                       user: str = "Automation",
                       reason_flow: Optional[ReasonFlow] = None) -> bool:
        if now_ts is None:
            now_ts = time.time()

        # 1) heating curve
        self.house_supply_setpoint = self._compute_house_supply_setpoint(outdoor_temp)
        # 2) PV boost
        self.pv_boost_temp = self._compute_pv_boost_temp(grid_power_balance)
        # 3) RL_WPSoll
        self.heat_pump_return_setpoint = self.house_supply_setpoint + self.pv_boost_temp
        # 4) HEAT/WAIT
        heat = self._decide_heat_wait(
            buffer_temp_top=buffer_temp_top,
            house_supply_setpoint=self.house_supply_setpoint,
            grid_power_balance=grid_power_balance
        )
        self.heat_pump_heat_wait = heat

        values_now: Dict[str, float | bool | int] = {
            "heat_pump_mode": self.wp_on,
            "house_supply_setpoint": round(self.house_supply_setpoint, 2),
            "pv_boost_temp": round(self.pv_boost_temp, 2),
            "heat_pump_return_setpoint": round(self.heat_pump_return_setpoint, 2),
            "heat_pump_heat_wait": heat,
        }

        has_changed = False
        if not self._last_sent_values:
            has_changed = True
        else:
            for key, value in values_now.items():
                if key not in self._last_sent_values:
                    has_changed = True
                    break
                old = self._last_sent_values[key]
                if isinstance(value, bool) or isinstance(old, bool):
                    if value != old:
                        has_changed = True
                        break
                else:
                    if abs(float(value) - float(old)) > 0.1:
                        has_changed = True
                        break

        enough_time_passed = (now_ts - self._last_param_update_ts) >= self.param_update_delay
        should_send = has_changed and enough_time_passed

        if reason_flow is None:
            reason_flow = ReasonFlow(
                initiator=user,
                name=f"DynamicPowerSwitchable control update for {self.name}"
            )

        reason_flow.add_reason(
            f"Computed: VLHausSoll={self.house_supply_setpoint:.2f}°C, "
            f"PVBoost={self.pv_boost_temp:.2f}°C, "
            f"RL_WPSoll={self.heat_pump_return_setpoint:.2f}°C, "
            f"WPHeatWait={'HEAT' if heat else 'WAIT'}, "
            f"WP_on={self.wp_on}"
        )

        # sync Switchable state to HEAT/WAIT (logical only)
        self.set_state(new_state=heat, user=user, reason_flow=reason_flow)

        if should_send:
            self._last_param_update_ts = now_ts
            self._last_sent_values = values_now
            reason_flow.add_reason("Parameters should be sent (changed + hysteresis passed).")

            # mark that we want to perform real IO now
            self._io_triggered_from_update = True
            # delegate to hardware-specific IO (HA, etc.)
            self._set_hardware_io(self.state, reason_flow=reason_flow)

            reason_flow.to_event(EventSeverity.DEBUG)
        else:
            reason_flow.add_reason("No parameter send (no change or hysteresis not passed).")
            reason_flow.to_event(EventSeverity.DEBUG)

        return should_send

    def _set_hardware_io(self,
                         state: bool,
                         reason_flow: Optional[ReasonFlow] = None) -> bool:
        """
        For DynamicPowerSwitchable:
        - Called by Switchable.refresh_state() on real state changes.
        - Also called explicitly from update_control() when param hysteresis allows.
        Actual hardware IO (HTTP to HA) is centralized here.

        We only send to HA when _io_triggered_from_update is True, so
        simple HEAT/WAIT state changes (without new parameters) don't spam HA.
        """
        if reason_flow is not None:
            reason_flow.add_reason(
                f"DynamicPowerSwitchable: logical state -> {'HEAT' if state else 'WAIT'}"
            )

        # If this call came from refresh_state (normal state change), do not perform
        # parameter IO to HA. Only IO triggered explicitly from update_control.
        if not self._io_triggered_from_update:
            return True

        # reset flag immediately to avoid double-use
        self._io_triggered_from_update = False

        # Decide IO backend
        if self.hardware_io_endpoint_mode is HardwareIoEndpointMode.HOMEASSISTANT:
            self._send_setpoint_to_homeassistant(reason_flow=reason_flow)

        # For NONE or unknown modes, we simply do nothing special
        return True

    def to_dict(self, full: bool = False) -> Dict:
        device_dict = super().to_dict(full=full)
        device_dict.update({
            "device_type": "DynamicPowerSwitchable",
            "heat_pump_mode": self.wp_on,
            "controlled_device": self.controlled_device_name,
            "buffer_sensor": self.buffer_sensor_name,
            "outdoor_sensor": self.outdoor_sensor_name,
            "outdoor_temp_cold_ref": self.outdoor_temp_cold_ref,
            "outdoor_temp_warm_ref": self.outdoor_temp_warm_ref,
            "design_supply_temp_max": self.design_supply_temp_max,
            "design_supply_temp_min": self.design_supply_temp_min,
            "pv_temp_boost_factor": self.pv_temp_boost_factor,
            "param_update_delay": self.param_update_delay,
            "buffer_delta_supply": self.buffer_delta_supply,
            "house_supply_setpoint": self.house_supply_setpoint,
            "supply_gradient": self.supply_gradient,
            "pv_boost_temp": self.pv_boost_temp,
            "heat_pump_return_setpoint": self.heat_pump_return_setpoint,
            "heat_pump_heat_wait": self.heat_pump_heat_wait,
            "last_param_update_ts": self._last_param_update_ts,
            "hardware_io_endpoint_mode": self.hardware_io_endpoint_mode.value,
            "ha_base_url": self.ha_base_url,
            "ha_setpoint_webhook": self.ha_setpoint_webhook,
            # never expose token in UI in real life; here just for completeness
        })
        return device_dict
