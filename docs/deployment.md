# Container Deployment

LCC ships as one web/API container. Lemonade remains a separate host or remote service; the LCC image does not install, manage, or embed Lemonade.

## API-only default

The default Compose file is the recommended starting point. It persists LCC profiles, evidence, Bench results, setup state, and audit history in the `lcc-data` volume.

```bash
export LCC_API_KEY='replace-with-a-long-random-value'
docker compose up --build -d
```

Open `http://127.0.0.1:17600` and enter the same LCC key when prompted. The port binds to loopback by default. Set `LCC_PORT` to change the host port.

For Lemonade on the Docker host, the default URL is `http://host.docker.internal:13305`. For a remote server:

```bash
export LEMONADE_URL='http://lemonade.example.internal:13305'
docker compose up -d
```

The default deployment sets `TELEMETRY_SCOPE=container` and `CAPABILITIES_MODE=safe_runtime`. At startup LCC probes only non-mutating Lemonade GET endpoints; it does not run the full host probe or any administrative POST. It can prove Lemonade API reachability, API-returned model/runtime state, and explicitly container-visible process counters. It suppresses accelerator sysfs claims even if the container engine happens to expose part of host sysfs. It cannot be treated as trusted host process, accelerator, systemd, or journal evidence.

## Optional Linux host telemetry

The override below joins the host PID namespace, exposes host sysfs read-only, and mounts the Lemonade cache read-only for saved recipe options:

```bash
export LCC_API_KEY='replace-with-a-long-random-value'
export LEMONADE_CACHE_DIR="$HOME/.cache/lemonade"
docker compose -f compose.yaml -f compose.host-telemetry.yaml up --build -d
```

This is a meaningful reduction in isolation. Use it only on a trusted Linux host. `pid: host` may let LCC observe host process command lines and resource counters. `/sys` exposes hardware topology and counters. Read-only mounts prevent ordinary file writes but do not make the disclosed information non-sensitive.

### Accelerator devices

GPU/NPU device access is not enabled by default because missing device nodes make Compose startup fail and group ids vary by host. Add only devices that exist:

```yaml
services:
  lcc:
    devices:
      - /dev/dri:/dev/dri
      - /dev/accel:/dev/accel
    group_add:
      - "${RENDER_GID}"
      - "${VIDEO_GID}"
```

Set `RENDER_GID` and `VIDEO_GID` from the host groups. A mapped device makes counters/tools reachable; it still does not prove that Lemonade owned observed accelerator activity. Evidence remains time-correlated and ownership stays `unproven`.

## Telemetry boundary

| Facility | Default container | Host telemetry override | Remaining limitation |
|---|---|---|---|
| Lemonade HTTP API | Available when routed | Available when routed | API reachability is not host telemetry |
| `/proc` process view | Container only | Host PID namespace | Host security settings may hide command lines |
| `/sys` counters | Container-visible subset | Host sysfs mounted read-only | Counter presence does not prove workload ownership |
| `/dev/dri` | Not mapped | Explicit opt-in only | Host permissions and drivers still apply |
| `/dev/accel` | Not mapped | Explicit opt-in only | Host permissions and drivers still apply |
| `journalctl` | Unavailable | Unavailable by default | Requires host journal tooling/socket/files and broader disclosure |
| `systemctl` restart | Unsupported | Unsupported by default | Container does not own the host Lemonade service manager |

Do not mount host `/proc`, `/sys`, journal files, Docker socket, or device nodes merely to remove an `unavailable` label. Unavailable or degraded evidence is safer and more accurate than implied access.

## Secrets and persistence

- `LCC_API_KEY` is required because the application listens on `0.0.0.0` inside the container.
- Keep the published port loopback-bound unless a trusted reverse proxy provides TLS and access control.
- Pass `LEMONADE_ADMIN_API_KEY` only when the configured Lemonade endpoint requires it.
- Do not bake keys into the image or commit a Compose `.env` file.
- Back up the `lcc-data` volume if local profiles and evidence must be retained.
- The image runs as non-root UID/GID `10001`; bind-mounted data directories must be writable by that identity.

## Useful commands

```bash
docker compose ps
docker compose logs -f lcc
docker compose down
docker compose down --volumes  # also deletes LCC local data
```
