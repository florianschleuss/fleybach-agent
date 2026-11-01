# Local site foundation

Phase 1: shared measurements, device inventory and versioned customer/site metadata.
This is not a new rule engine. Existing hardware connections and device safety
parameters retain their existing configuration; supported device parameters can
still be edited through the existing device UI. Physical wiring, GPIO mappings,
serial ports and credentials are deliberately not exposed as free-form inputs.

All existing measurement sources publish into a shared SQLite WAL volume before
cloud uploads. Values retain raw values, native unit, stable source ID, source
sample time and local receipt time. Invalid, disabled and expired values are
never returned to the controller as current values. Cache identity is bound to
the configured customer domain.

The site service exposes read-only `GET /v1/site` on the internal Docker network.
No host port is published. It synchronizes customer-scoped desired configuration
and inventory through the backend; no cloud access is needed for local reads.
SQLite stores the last accepted config across restarts. Local API reads are
separate from cloud synchronization. Timezone is site metadata at this stage;
legacy scheduling behavior is unchanged until the engine migration.

Start from the repository root using the existing environment. Initialize the
shared volume before starting capture: its directory must belong to UID/GID
65534 with mode 2770 and its SQLite files to UID/GID 65534 with mode 0660.
This preserves the existing non-root Zendure collector. Do not make the collector
root or make the volume world-writable. The initial configuration can be created
by running `utils.site_store.configuration()` in a one-off site container as root,
then applying the ownership/modes before normal services start.

The installed production instance uses a persistent root-level
`docker-compose.override.yaml` and SITE_LOCAL_CONTROL=1 after verified shadow
comparison. Fresh installations deliberately default to capture-only mode.

Start from the repository root using the existing environment:

```
docker compose -f docker-compose.yaml -f site/compose.yaml --profile zendure up -d --build
```

This enables publishing, but leaves the existing controller data path unchanged.
First verify inventory against legacy readings without switching equipment.
`SITE_LOCAL_CONTROL=1` in the device service enables local reads, while using the
same existing tick, temperature and LG algorithms. No automatic cloud fallback
is used after this explicit activation; stale required local values block the
affected decision. Recreate only device after changing the flag. Keep the overlay
in the service's normal deployment command so the feature survives upgrades.

Bindings: `grid.main` and `temperature.<existing sensor name>`. Empty bindings
retain legacy name mappings. UI supports display names, locations, measurement
enabling, maximum age, factor/sign and offset. Device display/location metadata
is independent of actuator safety parameters. Incoming configuration is validated
again locally before atomic persistence and acknowledgement. Rejected revisions
leave the old active revision in place.

Rollback: unset SITE_LOCAL_CONTROL first; recreate device with the overlay. Remove
the overlay only after restoring a consistent set of original component files.
Keep backups and the SQLite volume. Never roll back by deleting data.

Limits: one controlling agent per customer in this foundation; cloud history,
notifications and existing socket startup still have cloud dependencies. No
claim of fully offline startup/control is made in this phase. Sensor roles must
be verified against electrical measurement boundaries before control activation.
Full offline startup, async cloud queues, rule simulation and a node editor are
subsequent engine work. A 24-hour outage test has not been performed.


## Production rollout 2026-11-01

The existing customer backend API, device algorithms and device-config.yaml were
retained. Native buffer_top/buffer_bottom were mapped to verified legacy roles
bufferTop/bufferBottom in configuration revision 1. Native water measurements
match the existing batch path: do not add the driver offset a second time.
Two live comparison cycles before and after activation matched grid power and
all four relevant temperatures exactly. The device restart's possible output
interruptions and timer reset were explicitly approved by the user.

Backups: /home/pi/fleybach-agent-releases/site-foundation-20261101.
No 24-hour outage test was performed. Existing socket startup and cloud event
paths are unchanged; this rollout reduces measurement-path cloud dependencies.
