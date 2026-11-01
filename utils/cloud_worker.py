"""Bounded, coalescing cloud work. Producers never execute network calls.

An in-flight operation cannot hold the queue lock. New measurements supersede
pending old snapshots; expired snapshots are never replayed as current data.
"""
from collections import OrderedDict
from threading import Condition, Thread
import logging
import time

log = logging.getLogger(__name__)


class CloudWorker:
    def __init__(self, name, capacity=64, retry_seconds=5, observer=None):
        self.name, self.capacity = name, capacity
        self.retry_seconds, self.observer = retry_seconds, observer
        self._pending = OrderedDict()
        self._condition = Condition()
        self._closed = False
        self._thread = Thread(target=self._run, name=name, daemon=True)
        self._thread.start()

    def submit(self, key, action, max_age=60):
        with self._condition:
            if self._closed:
                return False
            self._pending.pop(key, None)
            self._pending[key] = (action, time.monotonic()+max_age, 0)
            while len(self._pending) > self.capacity:
                self._pending.popitem(last=False)
            self._condition.notify()
        return True

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def _run(self):
        failed = False
        while True:
            with self._condition:
                while not self._closed:
                    now = time.monotonic()
                    self._pending = OrderedDict((k,v) for k,v in self._pending.items() if v[1] > now)
                    ready = next((k for k,v in self._pending.items() if v[2] <= now), None)
                    if ready is not None:
                        action, deadline, _ = self._pending.pop(ready)
                        break
                    self._condition.wait(timeout=.5)
                else:
                    return
            try:
                if action() is False:
                    raise ConnectionError('Cloud operation not acknowledged')
                if failed:
                    log.info('%s connection restored', self.name)
                if self.observer:
                    self.observer(False)
                failed = False
            except Exception as exc:
                if not failed:
                    log.warning('%s unavailable (%s); local acquisition continues', self.name, type(exc).__name__)
                if self.observer:
                    try:
                        self.observer(True)
                    except Exception:
                        log.warning('%s fault status could not be recorded', self.name)
                failed = True
                with self._condition:
                    if ready not in self._pending and deadline > time.monotonic():
                        self._pending[ready] = (action, deadline, time.monotonic()+self.retry_seconds)
                        while len(self._pending) > self.capacity:
                            self._pending.popitem(last=False)

