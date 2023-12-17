from threading import Timer
import time
from typing import Dict, List, Any, Callable, Optional


class DelayTimer:
    def __init__(self, timeout: int,
                 userHandler: Callable,
                 args: Optional[List[Any]] = None,
                 kwargs: Optional[Dict[str, Any]] = None):
        self.timeout = timeout
        self.handler = userHandler
        self._args = args
        self._kwargs = kwargs
        self.timer = Timer(self.timeout, self.handler,
                           self._args, self._kwargs)
        self._startet_at = time.time()
        self.timer.start()
        return

    def stop(self):
        """
        Stop the timer
        """
        self.timer.cancel()
        return

    def rest_time(self) -> int:
        """
        Get the rest time of the timer
        """
        return self.timeout - int(time.time()-self._startet_at)

    def reset(self) -> None:
        """
        Reset the timer
        """
        self.timer.cancel()
        self.timer = Timer(self.timeout, self.handler,
                           self._args, self._kwargs)
        self.timer.start()
