# Fault reporting and history cadence

`utils.faults.FaultReporter` gives producers stable per-target fault identities, a first report, 60-second reminders, and positive recovery observations. Failed uploads retry after 30 seconds; reporting failures do not stop control loops. WebSocket retries and individual mail delivery attempts may force an observation. Recovery after an agent restart is acknowledged without creating a raw event unless the backend has a corresponding open group.

Mail diagnostics separate SMTP authentication, TLS, connectivity, recipient rejection, and message failures. They persist exception class and numeric SMTP status, never credentials, recipient lists, message contents or raw replies. Partial recipient refusal is a failure; accepted recipients are not immediately sent the same mail again. A later regular SMTP acceptance is recovery evidence, not proof of recipient delivery. Tests mock SMTP and cannot send mail.

Home Assistant switching and setpoint failures have distinct identities per device; HTTP acceptance confirms recovery of that request path, not physical actuator position. Sensor freshness and inverter failures use the same reporter. Routine no-change controller requests use DEBUG; actual switching decisions and failures remain visible. Physical control thresholds, payloads and hysteresis are unchanged.

History schedules in `power/config.json` and `temperature/config.json` now request:

- Nine fast power channels (grid total, phases, AC/DC production): 10 seconds.
- Twenty inverter diagnostic channels: 30 seconds.
- Four existing temperature channels: 30 seconds.
- Daily energy counter snapshots retain their separate cadence.
- Zendure polling and its existing backend history interval are unchanged.

The existing 10-second acquisition loops remain unchanged; actual history cadence is bounded by device delivery and processing time. `Routine.completed(started_at)` advances the configured schedule without adding HTTP latency or replaying missed samples after an outage. History requests have bounded timeouts and only successfully acknowledged fresh readings advance a routine.

The backend retains 14 days of raw gauge history, then permanent time-weighted five-minute aggregates. Increasing sampling adds roughly 147,000 raw gauge rows/day for these 33 channels before existing Zendure samples, or about 2.06 million rows over the raw retention window. Long-term five-minute storage still grows with time; retention is not a fixed database-size cap.

Network-isolated tests: `python -m unittest test_fault_reporting test_ha_faults test_sampling`. Existing temperature polling regression tests also pass with the new shared helpers. Deployment backs up source/config files, restarts only affected containers, and preserves separate user device configuration.
