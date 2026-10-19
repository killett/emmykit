"""`LLMs` model selection, run entirely offline.

Only an OpenAI key is set, the internet check reports success, and every real
socket connection fails, so a test that reached the network would notice.
"""

from __future__ import annotations

import re
import socket
import sqlite3
import sys
import time
import types
from contextlib import closing
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
    # closing(): a sqlite3 connection's own `with` commits but doesn't close.
    with closing(sqlite3.connect(models.get_config().rate_db_path)) as conn:
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


# --- send_prompt preflight, rate-store failures, litellm absence, retries ------

class _Sent(BaseException):
    """Raised by a fake completion call; a BaseException, so no handler swallows it."""


def test_prompt_filling_the_context_window_is_a_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prompt that leaves no room for a reply raises before anything is sent.

    Fails if the error is swallowed and the request goes out with max_tokens=0.
    """
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, rate_throttle=False))
    monkeypatch.setattr(models, "_get_model_pricing_and_context", lambda model: (0.0, 0.0, 100))
    monkeypatch.setattr(models, "_count_chat_tokens", lambda messages, model: 150)

    def send(*args: object, **kwargs: object) -> object:
        raise _Sent(kwargs.get("max_tokens"))

    monkeypatch.setattr(models, "_call_with_backoff", send)
    with pytest.raises(ValueError, match="fully occupies"):
        models.send_prompt("hello", "be brief", model=models.model, temperature=0.0)


def test_unusable_rate_store_skips_throttling_instead_of_failing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A rate database that can't be created turns throttling off for the call, with a warning."""
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, rate_db_path=blocker / "rate.db"))

    models._throttle_if_needed("OpenAI", models.model, 10, 10)

    assert "throttling" in caplog.text


def test_missing_litellm_makes_a_model_unavailable_not_the_process_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The availability probe reports False without litellm; it must not call sys.exit."""
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG))
    models._config = LLMConfig(**CONFIG | {"availability_probe": True})
    monkeypatch.setattr(models, "_litellm_ready", False)
    monkeypatch.setitem(sys.modules, "litellm", None)

    assert models._probe_provider_available("OpenAI", "gpt-4.1-nano") is False


def test_send_prompt_without_litellm_raises_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_prompt with litellm missing is an ImportError saying so, not sys.exit."""
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, rate_throttle=False))
    monkeypatch.setattr(models, "_litellm_ready", False)
    monkeypatch.setitem(sys.modules, "litellm", None)

    with pytest.raises(ImportError, match=r"^LiteLLM is enabled but not installed\. 'pip install litellm' Error: "):
        models.send_prompt("hello", "be brief", model=models.model, temperature=0.0)


class _Down(Exception):
    """A provider error from the fake completion call."""


def test_send_prompt_raises_when_every_failover_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the failover runs out of models, send_prompt raises RuntimeError chained to the last error."""
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, rate_throttle=False))
    monkeypatch.setattr(models, "_litellm_ready", True)
    tried: list[str] = []

    def down(litellm: object, **kwargs: object) -> object:
        tried.append(str(kwargs["model"]))
        raise _Down(f"{kwargs['model']} is down")

    monkeypatch.setattr(models, "_call_with_backoff", down)
    first = models.model

    with pytest.raises(RuntimeError, match=rf"^LiteLLM request failed for model '{re.escape(first)}' and iterative failover also failed\. ") as excinfo:
        models.send_prompt("hello", "be brief", model=first, temperature=0.0)

    assert tried[0] == first and len(tried) > 1
    assert isinstance(excinfo.value.__cause__, _Down)
    assert str(excinfo.value.__cause__) == f"{tried[-1]} is down"


def test_paid_availability_probe_makes_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 1-token probe is billed, so it is tried exactly once.

    Fails if it passes max_retries=0, which completion_with_retries ignores in
    favour of num_retries (default 3 attempts).
    """
    litellm = pytest.importorskip("litellm")
    attempts: list[str] = []

    def completion(*args: object, **kwargs: object) -> object:
        attempts.append(str(kwargs.get("model")))
        raise RuntimeError("auth failed")

    monkeypatch.setattr(litellm.main, "completion", completion)
    monkeypatch.setattr(litellm, "get_model_info", lambda model: (_ for _ in ()).throw(RuntimeError("no info")))
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG))
    models._config = LLMConfig(**CONFIG | {"availability_probe": True, "availability_probe_allow_costly": True})

    assert models._probe_provider_available("OpenAI", "gpt-4.1-nano") is False
    assert attempts == ["gpt-4.1-nano"]


def test_send_under_tenacity_retries_a_non_rate_limit_error_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Under Tenacity, LiteLLM's own retry layer makes two attempts (one retry), not three."""
    litellm = pytest.importorskip("litellm")
    attempts: list[int] = []

    def completion(*args: object, **kwargs: object) -> object:
        attempts.append(1)
        raise RuntimeError("server error")

    monkeypatch.setattr(litellm.main, "completion", completion)
    models = LLMs()
    models.apply_config(LLMConfig(**CONFIG, rate_db_path=tmp_path / "rate.db"))

    with pytest.raises(RuntimeError, match="server error"):
        models._call_with_backoff(litellm, model=models.model, messages=[])
    assert len(attempts) == 2


# --- reply text extraction ----------------------------------------------------

def _chat(content: object) -> dict[str, object]:
    """A dict-shaped chat completion whose first choice holds `content`."""
    return {"choices": [{"message": {"content": content}}]}


@pytest.mark.parametrize(
    ("resp", "text"),
    [
        (_chat("hello"), "hello"),
        (_chat([{"type": "text", "text": "hel"}, {"type": "output_text", "content": "lo"}]), "hello"),
        (_chat(None), ""),
        (types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content=None))]), ""),
        ({"choices": [{"text": "completion"}]}, "completion"),
    ],
    ids=["string", "segments", "none-dict", "none-object", "completion-style"],
)
def test_reply_text_is_always_a_string(resp: object, text: str) -> None:
    """Segment lists are joined and a missing text is "", so send_prompt returns str.

    Fails if the content is returned as found, a list or None.
    """
    assert LLMs._extract_text_from_openai_like(resp) == text
