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
        self.timer = Timer(self.timeout, self.handler, args, kwargs)
        self._startet_at = time.time()
        self.timer.start()
        return

    def stop(self):
        self.timer.cancel()
        return

    def rest_time(self) -> int:
        return self.timeout - int(time.time()-self._startet_at)
