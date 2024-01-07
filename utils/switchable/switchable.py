from datetime import datetime, timedelta
from enum import Enum
import time
from typing import Dict, List, Optional, TypeVar

from utils.delayTimer import DelayTimer
from utils.event import Event, EventSeverity
from utils.reason import ReasonFlow

Switchable = TypeVar('Switchable')  # type: ignore
Depender = TypeVar('Depender')  # type: ignore


class DependencyType(Enum):
    AUTOMATIC = 'automatic'
    USER = 'user'


class Depender:
    def __init__(self,
                 name: str,
                 user: Optional[str] = None):
        self.name: str = name
        if self.name == "Automation":
            self.dependency_type: DependencyType = DependencyType.AUTOMATIC
        else:
            self.dependency_type: DependencyType = DependencyType.USER
        self.user: Optional[str] = user
        return

    def __eq__(self, other: Depender):
        conditions = [
            self.name == other.name,
            self.dependency_type == other.dependency_type
        ]
        return all(conditions)

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'user': self.user,
            'dependency_type': str(self.dependency_type)
        }


class TemperatureSafetyStepType(Enum):
    LOW = 'low'
    HIGH = 'high'


class TemperatureSafetyStep():
    def __init__(self,
                 type: TemperatureSafetyStepType,
                 value: float,
                 interval_seconds: int,
                 sensor_name: str):
        self.type: TemperatureSafetyStepType = type
        self.value: float = value
        self.interval_seconds: int = interval_seconds
        self.duration_seconds: int = 60
        self.sensor_name: str = sensor_name
        self.last_trigger: float = 0
        self._not_seen_since: Optional[float] = None
        self._alert_enabled: bool = True

    @classmethod
    def from_object(
            cls,
            object: Dict
    ):
        if 'type' not in object:
            raise Exception("No type given")
        if 'value_degrees_c' not in object:
            raise Exception("No value given")
        if 'interval_seconds' not in object:
            raise Exception("No interval given")
        if 'sensor_name' not in object:
            raise Exception("No sensor name given")
        tss = TemperatureSafetyStep(
            value=object['value_degrees_c'],
            interval_seconds=object['interval_seconds'],
            sensor_name=object['sensor_name'],
            type=TemperatureSafetyStepType(object['type'])
        )
        if 'duration_seconds' in object:
            tss.duration_seconds = object['duration_seconds']
        if 'alert_enabled' in object:
            tss._alert_enabled = object['alert_enabled']
        return tss

    def to_dict(self) -> Dict:
        return {
            'type': str(self.type),
            'value': self.value,
            'interval_seconds': self.interval_seconds,
            'duration_seconds': self.duration_seconds,
            'sensor_name': self.sensor_name,
            'last_trigger': self.last_trigger,
            'not_seen_since': self._not_seen_since,
            'alert_enabled': self._alert_enabled,
        }

    def is_safe(self,
                temperature: float
                ) -> bool:
        self._not_seen_since = None
        if self.last_trigger + self.interval_seconds > time.time():
            return True
        if self.type == TemperatureSafetyStepType.LOW:
            return self.value < temperature
        elif self.type == TemperatureSafetyStepType.HIGH:
            return self.value > temperature
        return False

    def needs_alert(self) -> bool:
        if not self._alert_enabled:
            return False
        if self._not_seen_since is None:
            self._not_seen_since = time.time()
            return False
        return self._not_seen_since + self.interval_seconds < time.time()

    def alert_send(self):
        self._not_seen_since = time.time()

    def trigger(self):
        """
        Logs a trigger to be aware of the last activation.
        Information used for is_safe evaluation.
        """
        self.last_trigger = time.time()


class TemperatureSafety:
    def __init__(self):
        self.temperature_safety_steps: List[TemperatureSafetyStep] = []
        return

    @classmethod
    def from_list(
            cls,
            list: List[Dict]
    ):
        if len(list) == 0:
            return
        ts: TemperatureSafety = TemperatureSafety()
        for tss in list:
            ts.temperature_safety_steps.append(
                TemperatureSafetyStep.from_object(tss))
        return ts

    def to_dict(self) -> Dict:
        return {'temperature_safety_steps': [tss.to_dict() for tss in self.temperature_safety_steps]}

    def by_step_type(self,
                     type: TemperatureSafetyStepType) -> List[TemperatureSafetyStep]:
        return [tss for tss in self.temperature_safety_steps if tss.type == type]

    def needed_sensors(self) -> List[str]:
        return list(dict.fromkeys([ts.sensor_name for ts in self.temperature_safety_steps]))


class Switchable:
    def __init__(self,
                 name: str,
                 displayed_name: str = '',
                 displayed_description: str = '',
                 dependencies: List[Switchable] = [],
                 shutdown_time_seconds: int = 0,
                 max_active_time_seconds: int = 86400,  # One day
                 min_active_time_seconds: int = 0,
                 hysteresis_seconds: int = 0,
                 re_hysteresis_seconds: int = 0,
                 importance: int = 0,
                 temperature_safety: Optional[TemperatureSafety] = None
                 ) -> None:
        # Internal name of SW
        self.name: str = name

        # Displayed data
        self.displayed_name: str = displayed_name
        self.displayed_description: str = displayed_description

        # SW state
        self._state: bool = False

        # Depedencies of SW. No activation without dependencies being active.
        self._dependencies: List[Switchable] = dependencies

        self._dependers: List[Depender] = []

        # Human interactions are listed here
        self._actuators: List[Depender] = []

        # Time the SW has been on in sec
        self._active_time_seconds: int = 0

        # Maximum time per day of active in sec
        self.max_active_time_seconds: int = max_active_time_seconds

        # Minimum time per day of active in sec
        self.min_active_time_seconds: int = min_active_time_seconds

        # Timestamp of last switch in sec
        self._last_switch: int = 0

        # Automatic shutdown after x seconds
        self.shutdown_time_seconds: int = shutdown_time_seconds
        self._shutdown_timer: Optional[DelayTimer] = None
        # Internal variable to keep track of a possible restart_timer
        self._restart_timer: Optional[DelayTimer] = None

        # Min. active between on->off in sec
        self.hysteresis_seconds: int = hysteresis_seconds

        # Min. deactive between off->on in sec
        self.re_hysteresis_seconds: int = re_hysteresis_seconds

        # Value to describe if the SW is more or less important than others
        self.importance: int = importance

        # Temperature information on which it is safe to operate
        self._temperature_safety: Optional[TemperatureSafety] = temperature_safety
        return

    @property
    def state(self):
        return self._state

    def re_hysteresis_timeout(self) -> bool:
        """
        If re_hysteresis from self or any dependcies is blocking switch on
        """
        if self._last_switch > (time.time() - self.re_hysteresis_seconds):
            return True
        return any([d.re_hysteresis_timeout() for d in self._dependencies])

    def hysteresis_timeout(self) -> bool:
        """
        If hysteresis from self or any dependcies is blocking switch off
        """
        if self._last_switch > (time.time() - self.hysteresis_seconds):
            return True
        return any([d.hysteresis_timeout() for d in self._dependencies])

    def max_active_time_pause(self) -> bool:
        """
        If max_active_time from self or any dependcies is blocking switch on
        """
        if self.max_active_time_seconds <= self.active_time_seconds:
            return True
        return any([d.max_active_time_pause() for d in self._dependencies])

    def remove_user_actuators(self):
        self._actuators = [
            a for a in self._actuators if a.dependency_type != DependencyType.USER]
        return

    def _switch_on(self,
                   user: str,
                   timer_seconds: Optional[int] = None,
                   reason_flow: Optional[ReasonFlow] = None) -> bool:
        """
        :param user: User who initiated the action
        :param timer: Optional timer to shutdown the device after x seconds

        :return: Success of operation
        """
        if (dep := Depender(name=user, user=user)) not in self._actuators:
            self._actuators.append(dep)
        if reason_flow is not None:
            reason_flow.add_reason(
                f"Added '{user}' to actuators. Total: {len(self._actuators)}")
        self.refresh_state(reason_flow=reason_flow)

        if self._restart_timer is not None:
            self._restart_timer.stop()
            self._restart_timer = None
        if self.shutdown_time_seconds != 0 or timer_seconds is not None:
            dtrf = None
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Automatic shutdown at {(datetime.now() + timedelta(seconds=self.shutdown_time_seconds if timer_seconds is None else timer_seconds)).strftime('%d.%m.%Y %H:%M:%S')} UTC")
                dtrf = reason_flow.split(
                    pause_auto_store=self.shutdown_time_seconds if timer_seconds is None else timer_seconds)
            self._shutdown_timer = DelayTimer(timeout=self.shutdown_time_seconds if timer_seconds is None else timer_seconds,
                                              userHandler=self.set_state,
                                              kwargs={'new_state': False,
                                                      'user': user,
                                                      'reason_flow': dtrf})
        return True

    def _switch_off(self,
                    user: str,
                    timer_seconds: Optional[int] = None,
                    reason_flow: Optional[ReasonFlow] = None) -> bool:
        """
        Handles the addition or removal of user/automations into the device.
        Calls _evaluate_state_change to calculate the new state.

        :param user: User who initiated the action
        :param timer: Optional timer to shutdown the device after x seconds

        :return: Success of operation
        """
        if Depender(name=user, user=user).dependency_type is DependencyType.USER:
            self.remove_user_actuators()
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Removed all users from actuators. Total: {len(self._actuators)}")
        elif (dep := Depender(name=user, user=user)) in self._actuators:
            self._actuators.remove(dep)
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Removed '{user}' from actuators. Total: {len(self._actuators)}")

        self.refresh_state(reason_flow=reason_flow)

        # Only if successful switch
        if self._state is not False:
            return self._state

        if self._shutdown_timer is not None and timer_seconds is None:
            self._shutdown_timer.stop()
            self._shutdown_timer = None
        if timer_seconds is not None:
            dtrf = None
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"Automatic restart at {(datetime.now() + timedelta(seconds=timer_seconds)).strftime('%d.%m.%Y %H:%M:%S')} UTC")
                dtrf = reason_flow.split(pause_auto_store=timer_seconds)
            self._restart_timer = DelayTimer(timeout=timer_seconds,
                                             userHandler=self.set_state,
                                             kwargs={'new_state': True,
                                                     'user': user,
                                                     'reason_flow': dtrf})
        # if reason_flow is not None:
        #     reason_flow.to_event(event_severity=EventCategory.NEUTRAL)
        return self._state

    def set_state(self,
                  new_state: bool,
                  user: str,
                  timer_seconds: Optional[int] = None,
                  reason_flow: Optional[ReasonFlow] = None) -> bool:
        '''
        Handles state changing with actuator awareness.

        :param user: The user/actuator that initiated the operation
        :param timer_seconds: Optional timer to revert the operation done after x sec

        :return: Value that is set after validation
        '''

        success: bool
        if new_state:
            success = self._switch_on(user=user, timer_seconds=timer_seconds,
                                      reason_flow=reason_flow)
        else:
            success = self._switch_off(user=user, timer_seconds=timer_seconds,
                                       reason_flow=reason_flow)
        return self._state

    @property
    def active_time_seconds(self) -> int:
        '''
        Calculates the time the device is active.

        :return: Time the device is active.
        '''
        active_time_seconds: int = self._active_time_seconds
        if self._state:
            active_time_seconds += int(time.time()) - self._last_switch
        return active_time_seconds

    @property
    def rest_active_time_seconds(self) -> int:
        '''
        Returns rest time to fulfill min_active_time requriement.
        Returns 0 if no need for activation.

        :return: The rest time the device needs to be active
        '''
        rest_time: int = self.max_active_time_seconds - self.active_time_seconds
        if self.min_active_time_seconds < self.active_time_seconds and rest_time < 0:
            return 0
        return self.min_active_time_seconds - self.active_time_seconds

    def to_dict(self, full=False) -> Dict:
        device_dict = {'name': self.name,
                       'state': self.state,
                       'max_active_time_seconds': self.max_active_time_seconds,
                       'min_active_time_seconds': self.min_active_time_seconds,
                       'hysteresis_seconds': self.hysteresis_seconds,
                       're_hysteresis_seconds': self.re_hysteresis_seconds,
                       'shutdown_time_seconds': self.shutdown_time_seconds,
                       'importance': self.importance,
                       'active_time_seconds': self.active_time_seconds,
                       'displayed_description': self.displayed_description,
                       'displayed_name': self.displayed_name}
        device_dict['shutdown_timer'] = self._shutdown_timer.rest_time(
        ) if self._shutdown_timer is not None else None
        device_dict['restart_timer'] = self._restart_timer.rest_time(
        ) if self._restart_timer is not None else None

        if full:
            device_dict['dependencies'] = [
                d.to_dict(full=full) for d in self._dependencies]
            if self._temperature_safety is not None:
                device_dict['temperature_safety'] = self._temperature_safety.to_dict()
            device_dict['actuators'] = [a.to_dict() for a in self._actuators]
            device_dict['dependers'] = [d.to_dict() for d in self._dependers]
        return device_dict

    def reset(self):
        '''
        Reset the values for a daily reset routine.
        '''
        self._active_time_seconds: int = 0
        if self._last_switch != 0:
            self._last_switch = int(time.time())
        Event(
            comment=f"Reset routine run for {self.name}",
            event_severity=EventSeverity.INFO,
            initiator=self.name.replace('_', '-').title()
        ).store()
        return

    def to_depender(self, user: Optional[str] = None) -> Depender:
        '''
        Conversion to depender class

        :return: A Depender object
        '''
        return Depender(name=self.name, user=user)

    def _set_hardware_io(self,
                         state: bool,
                         reason_flow: Optional[ReasonFlow] = None) -> bool:
        '''
        Placeholder for later hardware switching functionallity

        :param state: State to which it should be set

        :return: Success or failure
        '''
        return False

    def refresh_state(self,
                      reason_flow: Optional[ReasonFlow] = None) -> None:
        '''
        Re-evaltuates state when e.g. dependencies change and invoke refresh
        It does not need to include who or what switched. It evaluates the state in a 'stateless' fashion.
        '''
        new_state = len(self._actuators) > 0 or len(self._dependers) > 0

        if self._state == new_state:
            return

        # Switch on
        if new_state:
            if self.re_hysteresis_timeout():
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"Re-Hysteresis blocked attempt.")
                    reason_flow.to_event(EventSeverity.DEBUG)
                return

            if self.max_active_time_pause():
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"Max active time blocked attempt.")
                    reason_flow.to_event(EventSeverity.DEBUG)
                return
            if reason_flow is not None:
                reason_flow.update_auto_store_severity(EventSeverity.NEUTRAL)
            if len(self._dependencies) != 0:
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"Going through {len(self._dependencies)} dependencies")
                for d in self._dependencies:
                    if (dep := self.to_depender()) not in d._dependers:
                        d._dependers.append(dep)
                        if reason_flow is not None:
                            reason_flow.add_reason(
                                f"Added self ({self.name}) to '{d.name}' as depender")
                            rf = reason_flow.split()
                        else:
                            rf = None
                        d.refresh_state(reason_flow=rf)
        # Switch off
        else:
            if self.hysteresis_timeout():
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"Hysteresis blocked attempt.")
                    reason_flow.to_event(EventSeverity.DEBUG)
                return
            if reason_flow is not None:
                reason_flow.update_auto_store_severity(EventSeverity.NEUTRAL)
            if len(self._dependencies) != 0:
                if reason_flow is not None:
                    reason_flow.add_reason(
                        f"Going through {len(self._dependencies)} dependencies")
                for d in self._dependencies:
                    dep: Depender = self.to_depender()
                    rf = None
                    try:
                        d._dependers.remove(dep)
                        if reason_flow is not None:
                            reason_flow.add_reason(
                                f"Removed self ({self.name}) from {d.name} as depender")
                            rf = reason_flow.split()
                    except ValueError:
                        if reason_flow is not None:
                            reason_flow.add_reason(
                                f"Self ({self.name}) not present at {d.name} as depender")
                            rf = reason_flow.split()
                    finally:
                        d.refresh_state(reason_flow=rf)

        if self._set_hardware_io(new_state, reason_flow=reason_flow):
            if not new_state and self._last_switch != 0:
                # Needed for switch off after initialization
                self._active_time_seconds += int(time.time()) - \
                    self._last_switch
            self._last_switch = int(time.time())
            if reason_flow is not None:
                reason_flow.add_reason(
                    f"{self.name.capitalize()} switched to '{new_state}'")
                reason_flow.update_name()
            else:
                Event(comment=f"{self.name.capitalize()} switched to '{new_state}'",
                      event_severity=EventSeverity.NEUTRAL,
                      initiator=self.name.replace('_', '-').title()).store()
            self._state = new_state

        return
