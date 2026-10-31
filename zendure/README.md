# Optional read-only Zendure collector

Each installation keeps its existing CUSTOMER_DOMAIN/CUSTOMER_SECRET and
therefore its existing backend customer ID. Configure only the sources present
at that installation. Several batteries and a meter can coexist without being
combined. The reader never sends device writes, MQTT setup or control commands.

1. Copy `zendure/config.example.json` to `zendure/config.json`.
2. Enable desired sources, set private LAN IP, label, `kind` (`battery` or
   `smart_meter`) and **expectedSerial** (battery `sn` or meter `deviceId`).
   This pins identity even if DHCP changes; a different device at that IP is
   rejected. Static DHCP leases are recommended. The live file is gitignored.
3. Check without authentication/upload:
   `docker compose --profile zendure run --rm zendure python collector.py --check`
4. Start only this service:
   `docker compose --profile zendure up -d --build --no-deps zendure`
5. Inspect `docker compose logs --tail 30 zendure`.

`--once` reads **and uploads** one sample per enabled source. `--check` only
reads devices. Defaults: poll every 10 seconds, device timeout 5 seconds,
stale after 60 seconds; threshold must cover at least three polling intervals.
Request failures are retried on the next poll, independently per source; old
values retain their age and are not replaced with zeros. No unbounded backlog.
Backend records history at most once per minute per source.

AUTH_URL accepts the usual scheme-less production API host or an explicit
HTTPS base URL, including `https://dev.app.fleybach.com/api`. Use independent
Dev credentials for Dev; never reuse production credentials. The backend must
have its additive telemetry migration/API installed first.

Read-only, non-root Python 3.12 container with no host devices/privileges.
The existing shared auth helper provides customer login and early token renewal;
one rejected token triggers a refresh/retry. Tokens/secrets are not logged.
Existing temperature, power and device services are not restarted.

Supported: tested SolarFlow 2400 AC version-3 reports and flat Zendure meter
reports. Numeric normalization is the same `utils/zendure.py` as the backend.
Missing data stays missing. Battery discharge/charge are separate; no control,
energy estimation or inference of overall house consumption is performed.

To disable: `docker compose --profile zendure stop zendure`. Backend source
freshness will expire normally. Other installations remain disabled unless
explicitly configured and started with the `zendure` profile.
