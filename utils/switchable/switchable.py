from ast import Del
from enum import Enum
import time
from typing import List, Optional, TypeVar

from utils.delayTimer import DelayTimer

Switchable = TypeVar('Switchable')
Depender = TypeVar('Depender')


class DependencyType(Enum):
    AUTOMATIC = 0
    USER = 1


class Depender:
    def __init__(self,
                 name: str,
                 dependency_type: DependencyType,
                 user: Optional[str] = None):
        self.name: str = name
        self.dependency_type: DependencyType = dependency_type
        self.user: Optional[str] = user
        return

    def __eq__(self, other: Depender):
        conditions = [
            self.name == other.name,
            self.dependency_type == other.dependency_type,
            self.user == other.user
        ]
        return any(conditions)


class Switchable:
    def __init__(self,
                 name: str,
                 dependencies: List[Switchable] = [],
                 shutdown_time: int = 0,
                 max_active_time: int = 86400,  # One day
                 min_active_time: int = 0,
                 hysteresis: int = 0,
                 re_hysteresis: int = 0
                 ) -> None:
        # Displayed name of SW
        self.name: str = name

        # SW state
        self._state: bool = False

        # Depedencies of SW. No activation without dependencies being active.
        self._dependencies: List[Switchable] = dependencies

        self._dependers: List[Depender] = []

        # Human interactions are listed here
        self._actuators: List[Depender] = []

        # Time the SW has been on in sec
        self._active_time: int = 0

        # Maximum time per day of active in sec
        self._max_active_time: int = max_active_time

        # Minimum time per day of active in sec
        self._min_active_time: int = min_active_time

        # Timestamp of last switch in sec
        self._last_switch: int = 0

        # Automatic shutdown after x seconds
        self._shutdown_time: int = shutdown_time
        self._shutdown_timer: Optional[DelayTimer] = None

        # Min. active between on->off
        self._hysteresis: int = hysteresis

        # Min. deactive between off->on
        self._re_hysteresis: int = re_hysteresis
        return

    @property
    def state(self):
        return self._state

    def set_state(self, new_state: bool, user: str = 'default') -> bool:
        '''Returns the value that is set after validation
        '''
        if new_state:  # Switch on
            if self._last_switch > (time.time() - self._re_hysteresis):
                return False
            if self._max_active_time <= self.active_time:
                return False
            if len(self._dependencies) != 0:
                for d in self._dependencies:
                    if (dep := self.to_depender()) not in d._dependers:
                        d._dependers.append(dep)
                    d.refresh_state()
            self._actuators.append(
                Depender(name=user, dependency_type=DependencyType.USER))
            if self._shutdown_time != 0:
                self._shutdown_timer = DelayTimer(timeout=self._shutdown_time,
                                                  userHandler=self.set_state,
                                                  kwargs={'new_state': False,
                                                          'user': user})  # noqa

        else:  # Switch off
            if self._last_switch > (time.time() - self._hysteresis):
                return False
            self._actuators.remove(
                Depender(name=user, dependency_type=DependencyType.USER))
            if len(self._dependencies) != 0 and len(self._actuators) == 0:
                for d in self._dependencies:
                    if (dep := self.to_depender()) in d._dependers:
                        d._dependers.remove(dep)
                        d.refresh_state()

        self.refresh_state()
        return self._state

    @property
    def active_time(self) -> int:
        '''
        Returns the time the device is active.
        '''
        active_time: int = self._active_time
        if self._state:
            active_time += int(time.time()) - self._last_switch
        return active_time

    @property
    def rest_active_time(self) -> int:
        '''
        Returns rest time to fulfill min_active_time requriement in .
        Returns 0 if no need for activation.
        '''
        rest_time: int = self._max_active_time - self.active_time
        if self._min_active_time < self.active_time and rest_time < 0:
            return 0
        return self._max_active_time - self.active_time

    def reset(self):
        '''Reset the values for a daily reset routine
        '''
        self._active_time: int = 0
        if self._last_switch != 0:
            self._last_switch = int(time.time())
        # TODO: log
        return

    def to_depender(self,
                    dependency_type: DependencyType =
                    DependencyType.AUTOMATIC):
        '''Conversion to depender class
        '''
        return Depender(name=self.name, dependency_type=dependency_type)

    def _set_hardware_io(self, state: bool) -> bool:
        '''Placeholder for later hardware switching functionallity
        '''
        return False

    def refresh_state(self) -> None:
        '''
        Re-evaltuates state when e.g. dependencies change and invoke refresh
        '''
        new_state = len(self._actuators) > 0 or len(self._dependers) > 0

        if self._set_hardware_io(new_state):
            if not new_state:
                self._active_time += int(time.time()) - self._last_switch
            self._last_switch = int(time.time())
            self._state = new_state
        # TODO: log
        return
