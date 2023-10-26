from threading import Timer
from typing import Dict, List, Any, Callable, Optional


class DelayTimer:
    def __init__(self, timeout: int,
                 userHandler: Callable,
                 args: Optional[List[Any]] = None,
                 kwargs: Optional[Dict[str, Any]] = None):
        self.timeout = timeout
        self.handler = userHandler
        self.timer = Timer(self.timeout, self.handler, args, kwargs)
        self.timer.start()
        return

    def stop(self):
        self.timer.cancel()
        return
