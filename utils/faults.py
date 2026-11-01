"""Bounded fault observations and positive recovery, reusable across components."""
import time
import logging


class FaultReporter:
    def __init__(self, source, emit=None, clock=time.monotonic, interval=60):
        self.source, self.emit, self.clock, self.interval = source, emit, clock, interval
        self.states = {}

    def observe(self, code, subject, failed, comment, details=None, critical=False, force=False):
        key = (code, subject)
        previous = self.states.get(key)
        now = self.clock()
        # Initial positive evidence can also resolve a fault across a restart.
        # Backend drops unmatched recovery observations rather than storing noise.
        if previous:
            old_failed, acknowledged, attempted, old_critical = previous
            force = force or (failed and critical and not old_critical)
            if now-attempted < (30 if not acknowledged else self.interval):
                if old_failed == failed and not force:
                    return False
            if acknowledged and not failed and not old_failed:
                return False
        state = 'fault' if failed else 'recovered'
        try:
            if self.emit:
                accepted = self.emit(code, subject, state, comment, details, critical)
            else:
                from utils.event import Event, EventSeverity, EventType
                accepted = Event(comment, self.source,
                                 EventSeverity.CRITICAL if critical and failed else EventSeverity.IMPORTANT if failed else EventSeverity.INFO,
                                 EventType.ERROR if failed else EventType.DEFAULT,
                                 details, error_code=code, subject_id=subject, state=state).store()
        except Exception as exc:
            # Reporting must not interrupt the existing device-control loop.
            logging.getLogger(__name__).warning('Fault report not acknowledged (%s)', type(exc).__name__)
            accepted = False
        self.states[key] = (failed, bool(accepted), now, critical)
        return bool(accepted)
