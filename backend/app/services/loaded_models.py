"""
Which loaded model a request refers to, and which llama-server process runs it.

Lemonade can keep several models loaded at once (chat, embedding, reranking...),
so neither the first model nor the first process can be taken as the active one.
"""
from collections.abc import Sequence

from app.models.schemas import (
    LlamaServerInfoResponse,
    LoadedModelInfo,
    RunningModelInfo,
)
from app.services.process import (
    find_llama_server,
    find_llama_servers,
    match_llama_server,
)


def find_loaded(models: Sequence[RunningModelInfo], requested: str) -> RunningModelInfo | None:
    """The loaded model with the requested name."""
    name = requested.removesuffix(":latest")
    return next((model for model in models if name in (model.name, model.model)), None)


def observed_model(models: Sequence[RunningModelInfo], requested: str) -> RunningModelInfo | None:
    """The loaded model that a request for `requested` was observed with.

    A single model with another name is a mismatch worth recording. With several
    models and no match there is no way to tell, and None is the honest answer.
    """
    match = find_loaded(models, requested)
    if match is None and len(models) == 1:
        return models[0]
    return match


def primary_model(models: Sequence[RunningModelInfo]) -> RunningModelInfo | None:
    """The model to describe when no particular one was asked for: a chat model first."""
    return next((model for model in models if model.type == "llm"), models[0] if models else None)


def llama_server_for(model: RunningModelInfo | None) -> LlamaServerInfoResponse:
    """The llama-server process of a loaded model.

    Without the pid or port from Lemonade (older versions, or no known model) the
    answer is known only when there is a single llama-server.
    """
    if model is not None and (model.pid is not None or model.port is not None):
        return find_llama_server(pid=model.pid, port=model.port)
    servers = find_llama_servers()
    return servers[0] if len(servers) == 1 else LlamaServerInfoResponse(found=False)


def describe_loaded(models: Sequence[RunningModelInfo]) -> list[LoadedModelInfo]:
    """Each loaded model with its own llama-server process, the primary model first."""
    servers = find_llama_servers()

    def server(model: RunningModelInfo) -> LlamaServerInfoResponse:
        if model.pid is not None or model.port is not None:
            return match_llama_server(servers, pid=model.pid, port=model.port)
        # Not reported by Lemonade: known only when there is nothing to choose from.
        if len(models) == 1 and len(servers) == 1:
            return servers[0]
        return LlamaServerInfoResponse(found=False)

    primary = primary_model(models)
    ordered = sorted(models, key=lambda model: model is not primary)
    return [LoadedModelInfo(**model.model_dump(), server=server(model)) for model in ordered]
