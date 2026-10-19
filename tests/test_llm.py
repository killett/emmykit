"""`LLMs` model selection, run entirely offline.

Only an OpenAI key is set, the internet check reports success, and every real
socket connection fails, so a test that reached the network would notice.
"""

from __future__ import annotations

import socket

import pytest

from emmykit import llm
from emmykit.llm import LLMConfig, LLMs

# Restrict selection to OpenAI, so no local Ollama/vLLM server is probed, and
# skip the paid availability probe, so a set API key is enough.
CONFIG = {"provider_filter": "OpenAI", "availability_probe": False}


@pytest.fixture(autouse=True)
def offline_with_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake an OpenAI key and a working connection; refuse every real connection."""
    def refuse(*args: object, **kwargs: object) -> None:
        raise OSError("tests must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(llm, "is_internet_available", lambda *args, **kwargs: True)
    for var in ("ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "LLM_MODEL_SCORES_JSON"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _openai_models(models: LLMs) -> set[str]:
    """Return the registry's OpenAI model names."""
    return {name for name, entry in models.model_info.items() if entry.get("provider") == "OpenAI"}


def test_apply_config_selects_a_model_from_the_allowed_provider() -> None:
    """Selection runs and honours the provider filter.

    Fails with NameError if `dataclasses.replace` isn't imported, as in 0.3.0–0.6.3.
    """
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG))

    assert models.provider == "OpenAI"
    assert models.model in _openai_models(models)


def test_get_config_returns_a_copy_of_the_applied_config() -> None:
    """Changing the returned config doesn't change the one in use."""
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, max_tokens=500))

    copy = models.get_config()
    copy.max_tokens = 1

    assert models.get_config().max_tokens == 500
    assert models.get_config().provider_filter == "OpenAI"


def test_refresh_selection_keeps_the_same_model_when_nothing_changed() -> None:
    """Re-running selection on an unchanged config picks the same model."""
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG))
    chosen = models.model

    models.refresh_selection()

    assert models.model == chosen
