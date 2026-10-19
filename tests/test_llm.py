"""`LLMs` model selection, run entirely offline.

Only an OpenAI key is set, the internet check reports success, and every real
socket connection fails, so a test that reached the network would notice.
"""

from __future__ import annotations

import socket
import sqlite3
import time
from pathlib import Path

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


# --- rate throttle -----------------------------------------------------------

class _SleptForever(BaseException):
    """Raised by the fake sleep; a BaseException, so the throttle's fail-open can't swallow it."""


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Make time.time a fake clock that time.sleep advances; return the list of sleeps."""
    now = [1_000_000.0]
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) > 5:
            raise _SleptForever(sleeps)
        now[0] += seconds

    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "sleep", sleep)
    return sleeps


@pytest.fixture
def throttled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> LLMs:
    """An LLMs whose model may take 1000 input tokens a minute (900 after the 0.9 headroom)."""
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, rate_db_path=tmp_path / "rate.db"))
    limits = {"scope": "model", "rpm": 0, "tpm_in": 1000, "tpm_out": 0, "tpm_sum": 0}
    monkeypatch.setattr(models, "_get_rate_limits_for", lambda model: limits)
    return models


def _rows(models: LLMs) -> int:
    """Count the requests recorded in the rate log."""
    with sqlite3.connect(models.get_config().rate_db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0])


def test_throttle_waits_until_the_oldest_request_leaves_the_window(
    throttled: LLMs, clock: list[float]
) -> None:
    """500 + 500 input tokens exceed 900, so the second waits for the first to expire."""
    throttled._throttle_if_needed("OpenAI", throttled.model, 500, 0)
    time.sleep(15)

    throttled._throttle_if_needed("OpenAI", throttled.model, 500, 0)

    assert clock == [15, pytest.approx(45.0)]
    assert _rows(throttled) == 2


def test_oversized_request_is_sent_at_once_when_the_window_is_empty(
    throttled: LLMs, clock: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    """A request bigger than the cap on its own goes out with a warning, not after a wait.

    Fails, by sleeping forever, if the throttle waits for room that can never exist.
    """
    throttled._throttle_if_needed("OpenAI", throttled.model, 2000, 0)

    assert clock == []
    assert _rows(throttled) == 1
    assert "exceeds the per-minute token cap" in caplog.text


def test_oversized_request_waits_only_for_an_empty_window(
    throttled: LLMs, clock: list[float], caplog: pytest.LogCaptureFixture
) -> None:
    """With other traffic in the window, an oversized request waits for it to clear, once."""
    throttled._throttle_if_needed("OpenAI", throttled.model, 100, 0)
    time.sleep(10)

    throttled._throttle_if_needed("OpenAI", throttled.model, 2000, 0)

    assert clock == [10, pytest.approx(50.0)]
    assert _rows(throttled) == 2
    assert "exceeds the per-minute token cap" in caplog.text


# --- selection with overrides and after reconnecting --------------------------

def test_alternative_model_scores_with_its_own_overrides() -> None:
    """multi_objective under overrides picks what apply_config with those settings picks.

    Fails if the strategy reads its weights from the applied config, ignoring
    the overrides it was asked to use.
    """
    overrides = {"weight_price": 0.0, "weight_code_skill": 10.0}
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG))
    reference = LLMs()
    reference.apply_config(LLMConfig(**CONFIG, **overrides))
    assert reference.model != models.model, "the overrides must change the choice for this test"

    assert models.alternative_model(strategy="multi_objective", **overrides).name == reference.model


def test_refresh_after_reconnecting_no_longer_forces_local_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Being offline once doesn't pin only_local_models=True for good.

    Fails if refresh_selection re-applies the resolved config, in which the
    offline check had already switched only_local_models on.
    """
    models = LLMs()
    ollama_tags = {"models": [{"name": "qwen2.5-coder:1.5b-base"}]}
    monkeypatch.setattr(models, "_http_get_json",
                        lambda url, timeout=2.0: ollama_tags if url.endswith("/api/tags") else None)
    online = [False]
    monkeypatch.setattr(llm, "is_internet_available", lambda *args, **kwargs: online[0])

    models.apply_config(LLMConfig(availability_probe=False))
    assert models.get_config().only_local_models is True  # forced while offline

    online[0] = True
    models.refresh_selection()

    assert models.get_config().only_local_models is False
