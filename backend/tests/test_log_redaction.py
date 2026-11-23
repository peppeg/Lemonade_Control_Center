import asyncio
import logging
import socket
from types import SimpleNamespace

import pytest
import uvicorn
import websockets
from uvicorn.logging import AccessFormatter, DefaultFormatter
from websockets.exceptions import InvalidHandshake

from app.main import app
from app.services.log_redaction import (
    URL_LOGGERS,
    KeyRedactionFilter,
    redact_key_in_logs,
)

KEY = "s3cret%2Bkey%2F%3D"


def _filtered(message: str, *args: object) -> logging.LogRecord:
    record = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, message, args, None)
    assert KeyRedactionFilter().filter(record) is True
    return record


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (f"/ws/metrics?lcc_key={KEY}", "/ws/metrics?lcc_key=<redacted>"),
        (f"/ws/metrics?a=1&lcc_key={KEY}&b=2", "/ws/metrics?a=1&lcc_key=<redacted>&b=2"),
        (f"/ws/metrics?lcc_key={KEY}&lcc_key={KEY}", "/ws/metrics?lcc_key=<redacted>&lcc_key=<redacted>"),
        ("/ws/metrics?lcc_key=", "/ws/metrics?lcc_key=<redacted>"),
        ("/ws/metrics", "/ws/metrics"),
        ("/api/logs/recent?n=10&xlcc_key=visible", "/api/logs/recent?n=10&xlcc_key=visible"),
    ],
)
def test_websocket_lines(path, expected):
    record = _filtered('%s - "WebSocket %s" [accepted]', "127.0.0.1:5000", path)

    assert DefaultFormatter("%(message)s").format(record) == f'127.0.0.1:5000 - "WebSocket {expected}" [accepted]'


def test_access_lines_keep_the_shape_uvicorn_expects():
    record = _filtered('%s - "%s %s HTTP/%s" %d', "127.0.0.1:5000", "GET", f"/api/x?lcc_key={KEY}", "1.1", 200)

    line = AccessFormatter("%(client_addr)s %(request_line)s %(status_code)s", use_colors=False).format(record)

    assert line == "127.0.0.1:5000 GET /api/x?lcc_key=<redacted> HTTP/1.1 200 OK"


def test_already_formatted_messages_and_other_arguments():
    assert _filtered(f"GET /x?lcc_key={KEY} done").getMessage() == "GET /x?lcc_key=<redacted> done"
    assert _filtered("%d of %s", 3, None).getMessage() == "3 of None"


def test_installing_twice_adds_one_filter(monkeypatch):
    # Own filter lists: the server test below must rely on what app.main installed.
    for name in URL_LOGGERS:
        monkeypatch.setattr(logging.getLogger(name), "filters", [])

    redact_key_in_logs()
    redact_key_in_logs()

    for name in URL_LOGGERS:
        assert [type(item) for item in logging.getLogger(name).filters] == [KeyRedactionFilter]


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
def server_log():
    handler = _Lines()
    loggers = [logging.getLogger(name) for name in URL_LOGGERS]
    levels = [logger.level for logger in loggers]
    for logger in loggers:
        logger.addHandler(handler)
    yield handler.lines
    for logger, level in zip(loggers, levels, strict=True):
        logger.removeHandler(handler)
        logger.setLevel(level)


@pytest.mark.asyncio
async def test_a_real_server_does_not_log_the_key(monkeypatch, server_log):
    monkeypatch.setattr("app.config.settings.lcc_api_key", "s3cret")
    monkeypatch.setattr("app.config.settings.require_auth", True)
    # Without journalctl the log stream closes by itself, so the server can stop.
    monkeypatch.setattr("app.routers.logs.capabilities", SimpleNamespace(cmd_journalctl=False))

    # No lifespan: the background collector must not run in this test.
    config = uvicorn.Config(
        app, lifespan="off", log_config=None, log_level="debug", timeout_graceful_shutdown=2
    )
    server = uvicorn.Server(config)
    with socket.create_server(("127.0.0.1", 0)) as listener:
        port = listener.getsockname()[1]
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    await asyncio.sleep(0.01)
                stream = f"ws://127.0.0.1:{port}/api/logs/ws/logs?lcc_key=s3cret"
                async with websockets.connect(stream) as connection:
                    await connection.wait_closed()
                with pytest.raises(InvalidHandshake):
                    await websockets.connect(f"{stream}-typo")
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(b"GET /api/security/status?lcc_key=s3cret HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
                await reader.read()
                writer.close()
        finally:
            server.should_exit = True
            await task

    log = "\n".join(server_log)
    assert "s3cret" not in log
    assert '/api/logs/ws/logs?lcc_key=<redacted>" [accepted]' in log
    assert '/api/logs/ws/logs?lcc_key=<redacted>" 403' in log
    assert "/api/security/status?lcc_key=<redacted>" in log
