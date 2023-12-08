from enum import Enum
from typing import Dict, List, Optional, TypeVar

Task = TypeVar('Task')


class Action(Enum):
    SWITCH = 'switch'
    ON = 'on'
    OFF = 'off'
    TIMER = 'timer'

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
        else:
            raise Exception("No matching action")


class Task():
    def __init__(self,
                 device_id: str,
                 action: Action,
                 action_args: Optional[Dict] = None) -> None:

        self.device_id: str = device_id
        self.action: Action = action
        self.action_args: Optional[Dict] = action_args

    @classmethod
    def from_object(
            cls,
            object: Dict
    ) -> Task:
        if 'deviceId' not in object:
            raise Exception("No deviceId given")
        if 'action' not in object:
            raise Exception("No action given")
        task: Task = cls(device_id=object['deviceId'],
                         action=Action.from_str(object['action']))
        if 'args' in object:
            task.action_args = object['args']
        return task

    def verify_action_params(self) -> bool:
        if self.action_args is None:
            return False
        if self.action in (Action.SWITCH, Action.OFF, Action.ON):
            return all(k in self.action_args for k in ['user'])
        elif self.action == Action.TIMER:
            return all(k in self.action_args for k in ['user', 'delay', 'state'])
        return False
