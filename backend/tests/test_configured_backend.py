from types import SimpleNamespace

import pytest

from app.models.schemas import LemonadeConfigResponse
from app.services.diagnostics import collectors


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param({"config_version": 2, "llamacpp": {"backend": "rocm", "args": ""}}, "rocm", id="nested"),
        pytest.param({"llamacpp.backend": "vulkan"}, "vulkan", id="dotted"),
        pytest.param({"llamacpp_backend": "cpu"}, "cpu", id="flat"),
        pytest.param({"backend": "cuda"}, "cuda", id="oldest"),
        pytest.param({"llamacpp": {"backend": "rocm"}, "llamacpp_backend": "cpu"}, "rocm", id="nested-wins"),
        pytest.param({"llamacpp": {"args": ""}, "llamacpp_backend": "cpu"}, "cpu", id="section-without-backend"),
        pytest.param({"llamacpp": "rocm"}, None, id="unexpected-section"),
        pytest.param({}, None, id="missing"),
    ],
)
def test_configured_backend(config, expected):
    assert collectors._configured_backend(config) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("executable", "expected"),
    [
        pytest.param("/opt/vulkan/llama-server", "vulkan", id="process"),
        pytest.param("/opt/llama-server", "auto", id="process-without-a-known-backend"),
    ],
)
async def test_diagnostics_prefer_the_running_backend(monkeypatch, executable, expected):
    class Provider:
        base_url = "http://lemonade.invalid"
        admin_headers = None

        async def get_config(self):
            return LemonadeConfigResponse(raw={"llamacpp": {"backend": "auto"}})

    process = SimpleNamespace(
        info={
            "pid": 1,
            "name": "llama-server",
            "cmdline": [executable],
            "status": "sleeping",
            "memory_info": SimpleNamespace(rss=1, vms=1),
            "cpu_percent": 0.0,
            "create_time": None,
        }
    )
    monkeypatch.setattr("app.services.process.psutil.process_iter", lambda attrs: iter([process]))
    monkeypatch.setattr(collectors, "get_provider", Provider)
    monkeypatch.setattr(
        collectors, "capabilities", SimpleNamespace(internal_config=True, internal_set=True, cmd_journalctl=False)
    )

    assert (await collectors.collect_full_state()).llamacpp_backend == expected
