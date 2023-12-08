from enum import Enum
from typing import Dict, List, Optional, TypeVar

Task = TypeVar('Task')


class Action(Enum):
    SWITCH = 'switch'
    ON = 'on'
    OFF = 'off'
    TIMER = 'timer'
    STATE = 'state'

    @staticmethod
    def from_str(action: str):
        if action in ('switch'):
            return Action.SWITCH
        elif action in ('on'):
            return Action.ON
        elif action in ('off'):
            return Action.OFF
        elif action in ('timer'):
            return Action.TIMER
        elif action in ('state'):
            return Action.STATE
        else:
            raise Exception("No matching action")


class Task():
    def __init__(self,
                 device_name: str,
                 action: Action,
                 action_args: Dict = {}) -> None:

        self.device_name: str = device_name
        self.action: Action = action
        self.action_args: Dict = action_args

    @classmethod
    def from_object(
            cls,
            object: Dict
    ) -> Task:
        if 'deviceName' not in object:
            raise Exception("No deviceName given")
        if 'action' not in object:
            raise Exception("No action given")
        task: Task = cls(device_name=object['deviceName'],
                         action=Action.from_str(object['action']))
        task.action_args = object.get('args', {})
        return task

    def verify_action_params(self) -> bool:
        if self.action_args == {}:
            return self.action in []
        if self.action in [Action.SWITCH, Action.OFF, Action.ON]:
            return all(k in self.action_args for k in ['user'])
        elif self.action == Action.STATE:
            return all(k in self.action_args for k in ['details'])
        elif self.action == Action.TIMER:
            return all(k in self.action_args for k in ['user', 'delaySeconds', 'state'])
        return False
