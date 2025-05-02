from enum import Enum
from typing import Dict, List, Optional, TypeVar

Task = TypeVar('Task')  # type: ignore


class Action(Enum):
    SWITCH = 'switch'
    ON = 'on'
    OFF = 'off'
    TIMER = 'timer'
    STATE = 'state'
    STATEALL = 'stateAll'
    UPDATE = 'update'

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
        elif action == 'stateAll':
            return Action.STATEALL
        elif action in ('state'):
            return Action.STATE
        elif action in ('update'):
            return Action.UPDATE
        else:
            raise Exception("No matching action")


class Task():
    def __init__(self,
                 action: Action,
                 action_args: Dict = {}) -> None:

        self.action: Action = action
        self.action_args: Dict = action_args

    @classmethod
    def from_object(
            cls,
            object: Dict
    ) -> Task:
        if 'action' not in object:
            raise Exception("No action given")
        task: Task = cls(action=Action.from_str(object['action']))
        task.action_args = object.get('args', {})
        return task

    def verify_action_params(self) -> bool:
        if self.action_args == {}:
            return self.action in []
        if self.action in [Action.SWITCH, Action.OFF, Action.ON]:
            return all(k in self.action_args for k in ['user', 'deviceName'])
        elif self.action == Action.TIMER:
            return all(k in self.action_args for k in ['user', 'delaySeconds', 'state', 'deviceName'])
        elif self.action == Action.STATE:
            return all(k in self.action_args for k in ['details', 'deviceName'])
        elif self.action == Action.STATEALL:
            return all(k in self.action_args for k in ['details'])
        elif self.action == Action.UPDATE:
            return all(k in self.action_args for k in ['updates', 'deviceName'])
        return False
