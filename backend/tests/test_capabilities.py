from types import SimpleNamespace

import httpx

from app.capabilities import probe_safe_runtime_capabilities


def test_safe_runtime_capability_probe_uses_only_get_and_enables_observed_endpoints(monkeypatch):
    monkeypatch.setattr("app.capabilities.settings.lemonade_url", "http://lemonade.test:13305")

    class Client:
        def __init__(self):
            self.paths = []

        def get(self, url):
            self.paths.append(url)
            path = url.removeprefix("http://lemonade.test:13305")
            if path == "/api/v1/health":
                return SimpleNamespace(status_code=200, json=lambda: {"version": "10.9.0"})
            if path in {"/api/tags", "/api/v1/models"}:
                return SimpleNamespace(status_code=200, json=lambda: {})
            return SimpleNamespace(status_code=404, json=lambda: {})

    client = Client()
    caps = probe_safe_runtime_capabilities(client)

    assert caps.health is True
    assert caps.ollama_tags is True
    assert caps.openai_models is True
    assert caps.stats is False
    assert caps.internal_config is False
    assert caps.cmd_systemctl is False
    assert caps.lemonade_version == "10.9.0"
    assert all("internal" not in url for url in client.paths)


def test_safe_runtime_capability_probe_degrades_on_transport_errors(monkeypatch):
    monkeypatch.setattr("app.capabilities.settings.lemonade_url", "http://offline.test")

    class Client:
        def get(self, url):
            raise httpx.ConnectError("offline")

    caps = probe_safe_runtime_capabilities(Client())

    assert caps.health is False
    assert caps.load is True
    assert caps.pull is True
