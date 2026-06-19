# Security Model

Lemonade Control Center is designed for local operation on a trusted Linux inference host.

It is not intended to be exposed directly to the public internet.

## Access Control

By default:

- localhost is trusted
- LAN and remote API clients require `LCC_API_KEY`
- `REQUIRE_AUTH=true` forces the same key requirement for localhost

Configuration:

```env
LCC_API_KEY=
REQUIRE_AUTH=false
```

Use a long random value for `LCC_API_KEY` if binding LCC to anything other than `127.0.0.1`.

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
