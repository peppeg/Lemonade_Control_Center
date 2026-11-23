import asyncio
import json
import os
import socket
import sys
import time
from types import SimpleNamespace

import psutil
import pytest
import uvicorn
import websockets
from starlette.testclient import TestClient

from app.main import app
from app.routers import logs

PATH = "/api/logs/ws/logs"
SILENT = "import time; time.sleep(120)"


@pytest.fixture
def journal(monkeypatch):
    """Replace journalctl with a Python script, and record the processes started."""
    started = []
    create = asyncio.create_subprocess_exec

    async def record(*args, **kwargs):
        process = await create(*args, **kwargs)
        started.append(process.pid)
        return process

    def use(script):
        monkeypatch.setattr(logs, "LOG_STREAM_COMMAND", [sys.executable, "-u", "-c", script])
        return started

    monkeypatch.setattr(logs, "capabilities", SimpleNamespace(cmd_journalctl=True))
    monkeypatch.setattr(logs.asyncio, "create_subprocess_exec", record)
    monkeypatch.setattr("app.config.settings.require_auth", False)
    monkeypatch.setattr("app.config.settings.lcc_api_key", None)
    yield use
    for pid in started:
        if _running(pid):
            os.kill(pid, 9)


def _connect():
    # No lifespan: the background collector must not run in these tests.
    return TestClient(app, client=("127.0.0.1", 50000)).websocket_connect(PATH, headers={"host": "127.0.0.1:17600"})


def _running(pid):
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _stopped(pid, timeout=5):
    deadline = time.monotonic() + timeout
    while _running(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    return not _running(pid)


def _messages(stream):
    messages = []
    while not messages or messages[-1]["type"] not in {"ended", "error"}:
        messages.append(stream.receive_json())
    return messages


def test_lines_are_forwarded_until_the_journal_ends(journal):
    journal("print('first'); print(); print('second')")

    with _connect() as stream:
        messages = _messages(stream)

    assert [message["type"] for message in messages] == ["connected", "log", "log", "ended"]
    assert [message["entry"]["message"] for message in messages[1:3]] == ["first", "second"]


def test_invalid_text_and_overlong_lines_do_not_end_the_stream(journal, monkeypatch):
    monkeypatch.setattr(logs, "MAX_LOG_LINE_BYTES", 64)
    journal(
        "import sys, time; out = sys.stdout.buffer\n"
        "out.write(b'bad \\xff byte\\n'); out.flush()\n"
        "out.write(b'x' * 100000 + b'\\n'); out.flush(); time.sleep(0.5)\n"
        "out.write(b'after\\n'); out.flush()"
    )

    with _connect() as stream:
        messages = _messages(stream)

    texts = [message["entry"]["message"] for message in messages if message["type"] == "log"]
    assert texts[0] == "bad � byte"
    assert texts[-1] == "after"
    assert messages[-1]["type"] == "ended"


def test_a_missing_journalctl_is_reported(journal, monkeypatch):
    journal(SILENT)
    monkeypatch.setattr(logs, "LOG_STREAM_COMMAND", ["/nonexistent/journalctl"])

    with _connect() as stream:
        assert stream.receive_json()["type"] == "error"


def test_closing_a_silent_stream_stops_journalctl(journal):
    started = journal(SILENT)

    begin = time.monotonic()
    with _connect() as stream:
        assert stream.receive_json()["type"] == "connected"
        assert _running(started[0])

    assert _stopped(started[0])
    assert time.monotonic() - begin < 10


def test_messages_from_the_client_do_not_end_the_stream(journal):
    journal("import time; time.sleep(0.5); print('line')")

    with _connect() as stream:
        for _ in range(5):
            stream.send_text("ping")
        messages = _messages(stream)

    assert [message["type"] for message in messages] == ["connected", "log", "ended"]


def test_a_journalctl_that_ignores_the_request_is_killed(journal, monkeypatch):
    monkeypatch.setattr(logs, "STOP_TIMEOUT_SECONDS", 0.2)
    started = journal(
        "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready'); time.sleep(120)"
    )

    with _connect() as stream:
        assert [stream.receive_json()["type"] for _ in range(2)] == ["connected", "log"]

    assert _stopped(started[0])


@pytest.mark.asyncio
@pytest.mark.parametrize("script", [SILENT, "import signal; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); signal.pause()"])
async def test_a_cancelled_handler_still_stops_journalctl(journal, script, monkeypatch):
    started = journal(script)
    connected = asyncio.Event()

    class Socket:
        async def accept(self):
            pass

        async def send_json(self, message):
            connected.set()

        async def receive(self):
            await asyncio.Event().wait()

    async def allow(websocket):
        return True

    monkeypatch.setattr(logs, "authorize_websocket", allow)
    handler = asyncio.create_task(logs.stream_logs(Socket()))
    await connected.wait()
    await asyncio.sleep(0.3)

    # Cancelled again while it waits for the process, as a forced shutdown does.
    handler.cancel()
    await asyncio.sleep(0)
    handler.cancel()
    with pytest.raises(asyncio.CancelledError):
        await handler

    assert await asyncio.to_thread(_stopped, started[0])


@pytest.mark.asyncio
async def test_lcc_stops_while_a_silent_stream_is_open(journal):
    started = journal(SILENT)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_config=None))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started:
            await asyncio.sleep(0.01)

        async with websockets.connect(f"ws://127.0.0.1:{port}{PATH}") as stream:
            assert json.loads(await stream.recv())["type"] == "connected"
            server.should_exit = True
            # Less than STOP_TIMEOUT_SECONDS: journalctl is asked to stop, not just killed.
            await asyncio.wait_for(serving, timeout=3)

    assert _stopped(started[0])
