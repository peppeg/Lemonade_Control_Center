# Security Model

Lemonade Control Center is designed for local operation on a trusted Linux inference host.

It is not intended to be exposed directly to the public internet.

## Access Control

By default:

- localhost is trusted, for direct connections that open LCC as `localhost`, as an IP address, or under a name in `ALLOWED_HOSTS`
- LAN, remote, and proxied API clients require `LCC_API_KEY`
- `REQUIRE_AUTH=true` forces the same key requirement for localhost
- the same rules apply to HTTP requests and WebSocket connections

Configuration:

```env
LCC_API_KEY=
REQUIRE_AUTH=false
```

Use a long random value for `LCC_API_KEY` if binding LCC to anything other than `127.0.0.1`.

## Browser Requests

LCC does not accept actions from other web sites, even with a valid key:

- `POST`, `PUT`, `PATCH`, and `DELETE` requests from another site are refused with 403 and written to the audit log;
- WebSocket connections whose `Origin` is not the address LCC was opened at are refused.

The frontend development servers are accepted. Clients that are not browsers send neither `Origin` nor `Sec-Fetch-Site` and are not affected. `ALLOWED_ORIGINS` adds origins; it is needed only behind a reverse proxy that does not forward the original `Host`.

Localhost trust also depends on the name in the address bar, because a web site can point its own domain at 127.0.0.1. If you open LCC on its own host under another name without a key, add that name to `ALLOWED_HOSTS`. List only names you control.

## Lemonade Admin API Key

`LEMONADE_ADMIN_API_KEY` is different from `LCC_API_KEY`.

- `LCC_API_KEY` protects access to LCC.
- `LEMONADE_ADMIN_API_KEY` is passed to Lemonade for protected Lemonade operations.

Most read-only LCC surfaces do not require the Lemonade admin key. Operations that call protected Lemonade endpoints do.

## Guarded Operations

The following actions are disabled unless explicitly enabled:

```env
ENABLE_DELETE=false
ENABLE_RESTART=false
```

- `ENABLE_DELETE=true` enables guarded model deletion.
- `ENABLE_RESTART=true` enables guarded Lemonade service restart.

Service restart can unload the active model. Model deletion is irreversible from LCC.

LCC restarts Lemonade with `sudo systemctl restart lemond.service`, without an interactive prompt. The user running LCC therefore needs a narrow sudoers rule, otherwise the restart fails with a sudo password error. Create it with `sudo visudo -f /etc/sudoers.d/lcc-restart`:

```text
YOUR_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart lemond.service
```

Allow only this exact command. Restart is not available from the container image.

## Diagnostic Bundles

Diagnostic bundles are sanitized before download. LCC redacts common secret keys, bearer tokens, Hugging Face tokens, private LAN IPs, hostnames, local usernames, and home paths on a best-effort basis.

Bundles can still contain sensitive workflow context such as model names, command-line shape, logs, prompts summarized by metadata, and local runtime behavior. Review the archive before attaching it to a public GitHub issue.

## Local Network Mode

For LAN usage:

1. Bind LCC to the desired interface.
2. Set `LCC_API_KEY`.
3. Keep firewall rules narrow.
4. Prefer a trusted private network.

For remote usage across untrusted networks, prefer SSH port forwarding rather than exposing the service.

Example from the client computer:

```bash
ssh -N -L 17600:127.0.0.1:17600 USER@SERVER_IP
```

This keeps LCC bound to localhost on the server. Open `http://127.0.0.1:17600` in the client browser while the SSH session remains active.

Unified runtime LAN example:

```bash
APP_HOST=0.0.0.0 APP_PORT=4242 REQUIRE_AUTH=true LAN_MODE=true python -m app.run
```

With LAN mode active, the client connects directly to `http://SERVER_IP:4242`; no SSH tunnel needs to remain open. The browser must provide the `LCC_API_KEY`, and the host firewall must allow TCP port `4242`.

SSH tunnel mode and LAN mode are alternatives. `LAN_MODE=true` is intentionally strict: it requires a LAN-visible bind address and `REQUIRE_AUTH=true`.

## Reverse Proxy

Localhost trust covers direct connections only. A request with `X-Forwarded-For`, `Forwarded`, or `X-Real-IP` always needs `LCC_API_KEY`, whatever address those headers name.

If you put LCC behind a reverse proxy:

- set `LCC_API_KEY`, and also `REQUIRE_AUTH=true`: a proxy that sends none of these headers and passes a local `Host` is indistinguishable from a local client;
- let the proxy provide TLS;
- forward the original `Host`, or list the public address in `ALLOWED_ORIGINS`.

By default LCC ignores forwarded addresses and records the proxy address in the audit log. To record the real client address, set `TRUSTED_PROXY_IPS` to the proxy address, for example `127.0.0.1`, and make the proxy overwrite `X-Forwarded-For` rather than pass the client's value through. This changes only the recorded address: forwarded clients need the key in both modes.

`TRUSTED_PROXY_IPS` applies to `python -m app.run`. If you start Uvicorn yourself, its own `--proxy-headers` and `--forwarded-allow-ips` options decide which address is recorded; the key requirement is the same.

Clients of the container image reach it through the container network rather than loopback, and the Compose file already requires `LCC_API_KEY`.

## Local Files

LCC keeps its state under `backend/app/data/` (the `lcc-data` volume in the container). `config.json` holds the configured runtimes, including any Lemonade admin keys entered in Settings. `audit.jsonl` records mutating API requests; it is rotated at 5 MB, and three older files are kept.

Only the user running LCC can read these files: the directory has mode `0700`, and LCC writes the files with mode `0600`. On startup LCC tightens a directory and a `config.json` left by an earlier version, and logs a warning if it is not allowed to.

## Known Limitations

These are tracked in the [Roadmap](./roadmap.md) under Security And Maintenance Hardening:

- The browser stores the LCC key in `localStorage` and sends it in the URL of WebSocket connections, because browsers cannot add headers to WebSockets. LCC replaces the key with `<redacted>` in its own log (0.3.0 and earlier wrote it there: if those logs were shared or are readable by others, change `LCC_API_KEY`). Other software sees the full URL: avoid proxies that log it, or strip the `lcc_key` parameter from their logs.
- For remote use, the SSH tunnel is the recommended mode until the remaining hardening work lands.
