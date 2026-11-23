import json
from types import SimpleNamespace

import httpx
import psutil
import pytest
from fastapi import HTTPException

from app.models.completions import CompletionResult
from app.models.schemas import RunningModelInfo, RunningModelsResponse
from app.providers.lemonade import LemonadeProvider
from app.routers import bench as bench_router
from app.routers import lemonade as lemonade_router
from app.routers import profiles as profiles_router
from app.services.bench.models import BenchRunRequest
from app.services.diagnostics import collectors
from app.services.loaded_models import (
    find_loaded,
    llama_server_for,
    observed_model,
    primary_model,
)
from app.services.process import find_llama_server, find_llama_servers

EMBED = RunningModelInfo(name="Embed-GGUF", type="embedding", pid=111, port=8001)
CHAT = RunningModelInfo(name="Chat-GGUF", type="llm", pid=222, port=8002)


def _process(pid, name, cmdline, *, status=psutil.STATUS_SLEEPING, rss_gb=1):
    return SimpleNamespace(
        info={
            "pid": pid,
            "name": name,
            "cmdline": cmdline,
            "status": status,
            "memory_info": SimpleNamespace(rss=rss_gb * 1024**3, vms=2 * 1024**3),
            "cpu_percent": 0.0,
            "create_time": None,
        }
    )


def _server(pid, port, *, ctx=4096, rss_gb=1):
    cmdline = ["/opt/vulkan/llama-server", "-m", f"/models/{pid}.gguf", "--ctx-size", str(ctx), "--port", str(port)]
    return _process(pid, "llama-server", cmdline, rss_gb=rss_gb)


@pytest.fixture
def processes(monkeypatch):
    def use(*items):
        monkeypatch.setattr("app.services.process.psutil.process_iter", lambda attrs: iter(items))

    return use


# ── Process detection ──


@pytest.mark.parametrize(
    ("name", "cmdline"),
    [
        pytest.param("bash", ["/bin/bash", "-c", "curl -H 'Authorization: secret' host; pgrep llama-server"], id="shell"),
        pytest.param("grep", ["grep", "llama-server"], id="grep"),
        pytest.param("vim", ["vim", "/etc/llama-server.conf"], id="editor"),
        pytest.param("journalctl", ["journalctl", "-t", "llama_server"], id="journal"),
        pytest.param("python3", ["python3", "/opt/llama-server/run.py"], id="argument-path"),
        pytest.param("helper", ["/opt/llama-server/helper"], id="directory-name"),
        pytest.param("whisper-server", ["/opt/whisper-server", "--model", "x"], id="other-server"),
        pytest.param("llama-bench", ["/opt/llama-bench", "-m", "x"], id="other-llama-tool"),
        pytest.param("watch-llama-server", ["/opt/watch-llama-server"], id="name-contains"),
        pytest.param("kworker", [], id="no-command-line"),
    ],
)
def test_programs_that_only_mention_llama_server_are_ignored(processes, name, cmdline):
    processes(_process(10, name, cmdline))

    assert find_llama_server().found is False
    assert find_llama_servers() == []


@pytest.mark.parametrize(
    ("name", "cmdline"),
    [
        pytest.param("llama-server", ["/var/cache/lemonade/bin/llamacpp/rocm/llama-server", "--port", "8001"], id="lemonade"),
        pytest.param("llama-server", ["/bin/sh", "/usr/local/bin/llama-server", "--port", "8001"], id="script"),
        pytest.param(".llama-server-", ["/nix/store/x/bin/llama-server"], id="wrapped"),
        pytest.param("llama-server-vu", ["llama-server-vulkan"], id="suffix"),
        pytest.param("llama-server", [], id="hidden-command-line"),
        pytest.param("llama-server.exe", [r"C:\lemonade\llama-server.exe"], id="windows"),
    ],
)
def test_llama_server_is_found_by_its_executable(processes, name, cmdline):
    processes(_process(9, "bash", ["bash", "-c", "llama-server"]), _process(10, name, cmdline))

    info = find_llama_server()

    assert info.found is True
    assert info.process.pid == 10


def test_unloaded_zombies_are_ignored(processes):
    processes(_process(10, "llama-server", [], status=psutil.STATUS_ZOMBIE), _server(11, 8001))

    assert [server.process.pid for server in find_llama_servers()] == [11]


def test_a_process_that_ends_during_the_scan_does_not_hide_the_others(processes):
    def gone():
        raise psutil.NoSuchProcess(10)

    ended = _process(10, "llama-server", [])
    ended.info["memory_info"] = None
    ended.memory_info = gone
    processes(ended, _server(11, 8001))

    assert find_llama_server().process.pid == 11


@pytest.mark.parametrize(
    ("pid", "port", "expected"),
    [
        pytest.param(222, 8002, 222, id="pid-and-port"),
        pytest.param(222, None, 222, id="pid"),
        pytest.param(None, 8002, 222, id="port"),
        pytest.param(7, 8002, 222, id="lemonade-in-another-pid-namespace"),
        pytest.param(7, 9999, None, id="no-match"),
        pytest.param(111, 8002, 222, id="port-wins"),
    ],
)
def test_llama_server_is_matched_to_what_lemonade_reports(processes, pid, port, expected):
    processes(_server(111, 8001), _server(222, 8002))

    info = find_llama_server(pid=pid, port=port)

    assert (info.process.pid if info.found else None) == expected


def test_a_pid_that_belongs_to_another_program_is_not_used(processes):
    processes(_process(222, "bash", ["bash"]), _server(111, 8001))

    assert find_llama_server(pid=222).found is False


# ── Which model ──


def test_requested_model_is_found_among_several():
    assert find_loaded([EMBED, CHAT], "Chat-GGUF") is CHAT
    assert find_loaded([EMBED, CHAT], "Chat-GGUF:latest") is CHAT
    assert find_loaded([EMBED, CHAT], "Chat") is None


def test_observed_model_keeps_a_single_mismatch_and_never_guesses_among_several():
    assert observed_model([EMBED, CHAT], "Chat-GGUF") is CHAT
    assert observed_model([EMBED], "Chat-GGUF") is EMBED
    assert observed_model([EMBED, CHAT], "Other-GGUF") is None
    assert observed_model([], "Chat-GGUF") is None


def test_primary_model_prefers_chat_and_falls_back_to_the_first():
    unknown = [RunningModelInfo(name="a"), RunningModelInfo(name="b")]

    assert primary_model([EMBED, CHAT]) is CHAT
    assert primary_model([EMBED]) is EMBED
    assert primary_model(unknown) is unknown[0]
    assert primary_model([]) is None


def test_process_is_unknown_when_lemonade_reports_no_pid_and_several_run(processes):
    legacy = RunningModelInfo(name="Chat-GGUF")

    processes(_server(111, 8001), _server(222, 8002))
    assert llama_server_for(legacy).found is False
    assert llama_server_for(None).found is False
    assert llama_server_for(CHAT).process.pid == 222

    processes(_server(111, 8001))
    assert llama_server_for(legacy).process.pid == 111
    assert llama_server_for(None).process.pid == 111
    assert llama_server_for(CHAT).found is False


# ── What Lemonade reports ──


def _provider(monkeypatch, health, status=200):
    provider = LemonadeProvider("http://lemonade.invalid")
    provider.capabilities = SimpleNamespace(ollama_ps=True)

    async def get(path, **kwargs):
        if path == "/api/ps":
            return httpx.Response(200, json={"models": [{"name": f"{n}:latest"} for n in ("Embed-GGUF", "Chat-GGUF")]})
        assert path == "/api/v1/health"
        if isinstance(health, Exception):
            raise health
        return httpx.Response(status, content=health if isinstance(health, bytes) else json.dumps(health))

    monkeypatch.setattr(provider, "_get", get)
    return provider


@pytest.mark.asyncio
async def test_running_models_carry_the_details_of_lemonade_health(monkeypatch):
    provider = _provider(
        monkeypatch,
        {
            "all_models_loaded": [
                {"model_name": "Chat-GGUF", "type": "llm", "pid": 222, "backend_url": "http://127.0.0.1:8002/v1"},
                {"model_name": "Embed-GGUF", "type": "embedding", "pid": 111, "backend_url": "http://127.0.0.1:8001/v1"},
            ]
        },
    )

    running = await provider.get_running_models()

    assert [(m.name, m.type, m.pid, m.port) for m in running.models] == [
        ("Embed-GGUF", "embedding", 111, 8001),
        ("Chat-GGUF", "llm", 222, 8002),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("health", "status"),
    [
        pytest.param({"status": "ok"}, 200, id="older-lemonade"),
        pytest.param({"all_models_loaded": "Chat-GGUF"}, 200, id="unexpected-type"),
        pytest.param({"all_models_loaded": ["Chat-GGUF", {}, None]}, 200, id="unexpected-items"),
        pytest.param(
            {"all_models_loaded": [{"model_name": "Chat-GGUF", "type": 1, "pid": "222", "backend_url": "http://x:port"}]},
            200,
            id="unexpected-fields",
        ),
        pytest.param({"all_models_loaded": [{"model_name": "Chat-GGUF", "pid": True}]}, 200, id="boolean-pid"),
        pytest.param([], 200, id="not-an-object"),
        pytest.param(b"not json", 200, id="not-json"),
        pytest.param({}, 500, id="error"),
        pytest.param(HTTPException(504, "timed out"), 200, id="timeout"),
    ],
)
async def test_running_models_work_without_usable_details(monkeypatch, health, status):
    running = await _provider(monkeypatch, health, status).get_running_models()

    assert [(m.name, m.type, m.pid, m.port) for m in running.models] == [
        ("Embed-GGUF", None, None, None),
        ("Chat-GGUF", None, None, None),
    ]


# ── Callers ──


class Provider:
    base_url = "http://lemonade.invalid"

    def __init__(self, *models, error=None):
        self.models = list(models)
        self.error = error

    async def get_running_models(self):
        if self.error:
            raise self.error
        return RunningModelsResponse(models=self.models)


@pytest.mark.asyncio
async def test_smoke_test_and_load_observe_the_requested_model():
    assert await lemonade_router._observe(Provider(EMBED, CHAT), "Chat-GGUF") is CHAT
    assert await lemonade_router._observe(Provider(EMBED, CHAT), "Other-GGUF") is None
    assert await lemonade_router._observe(Provider(error=HTTPException(501)), "Chat-GGUF") is None


@pytest.mark.asyncio
async def test_bench_accepts_any_loaded_model_and_records_its_process(processes, monkeypatch):
    processes(_server(111, 8001, ctx=512), _server(222, 8002, ctx=65536))
    stored = []
    monkeypatch.setattr(bench_router, "storage", SimpleNamespace(add_quick_result=stored.append))

    class Runner:
        async def run(self, request):
            return CompletionResult(model=request.model, response_text="ok", endpoint="/v1/chat/completions")

    await bench_router.run_bench(
        BenchRunRequest(model="Chat-GGUF", prompt="hi"), completion_runner=Runner(), provider=Provider(EMBED, CHAT), runtime=None
    )

    assert [(r.observed_model_name, r.observed_pid, r.observed_ctx_size) for r in stored] == [("Chat-GGUF", 222, 65536)]


@pytest.mark.asyncio
async def test_bench_names_every_loaded_model_when_the_requested_one_is_missing():
    with pytest.raises(HTTPException) as refused:
        await bench_router.run_bench(
            BenchRunRequest(model="Other-GGUF", prompt="hi"), completion_runner=object(), provider=Provider(EMBED, CHAT), runtime=None
        )

    assert refused.value.status_code == 409
    assert "'Embed-GGUF', 'Chat-GGUF'" in refused.value.detail


@pytest.mark.asyncio
async def test_diagnostics_describe_the_chat_model_and_its_process(processes, monkeypatch):
    processes(_server(111, 8001, ctx=512), _server(222, 8002, ctx=65536, rss_gb=3))
    monkeypatch.setattr(
        collectors, "capabilities", SimpleNamespace(internal_config=False, internal_set=False, cmd_journalctl=False)
    )
    provider = Provider(EMBED, CHAT)
    provider.admin_headers = None
    monkeypatch.setattr(collectors, "get_provider", lambda: provider)

    state = await collectors.collect_full_state()

    assert (state.loaded_model, state.llama_pid, state.llama_rss_gb, state.ctx_size) == ("Chat-GGUF", 222, 3, 65536)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        pytest.param(Provider(EMBED, CHAT), (True, 3), id="by-name"),
        pytest.param(Provider(error=HTTPException(501)), (True, 3), id="by-file"),
        pytest.param(Provider(EMBED), (True, 3), id="by-file-when-not-listed"),
    ],
)
async def test_recommendation_uses_the_memory_of_the_same_model(processes, provider, expected):
    chat = _process(
        222, "llama-server", ["llama-server", "-m", "/models/Chat-GGUF-Q4.gguf", "--port", "8002"], rss_gb=3)
    processes(_server(111, 8001), chat)
    seen = {}

    class Service:
        def compute_recommendation(self, **kwargs):
            seen.update(kwargs)

    await profiles_router.get_recommendation("Chat-GGUF", None, Service(), provider)

    assert (seen["model_loaded"], seen["loaded_model_rss_gb"]) == expected


@pytest.mark.asyncio
async def test_recommendation_for_a_model_that_is_not_loaded(processes):
    processes(_server(111, 8001))
    seen = {}

    class Service:
        def compute_recommendation(self, **kwargs):
            seen.update(kwargs)

    await profiles_router.get_recommendation("Chat-GGUF", None, Service(), Provider(EMBED))

    assert (seen["model_loaded"], seen["loaded_model_rss_gb"]) == (False, None)
