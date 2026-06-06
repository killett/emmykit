"""llm — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import math
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Type, TypeAlias, overload

from emmykit.constants import DEFAULT_ENCODING
from emmykit.hosts import IS_NASA_COMPUTER
from emmykit.io_subprocess import my_critical_error
from emmykit.network import is_internet_available

class SelectionStrategy(str, Enum):
    """Enumeration of selection strategies for model selection."""
    CHEAPEST                 = "cheapest"
    CONTEXT_THEN_PRICE       = "context_then_price"
    CODE_SKILL_THEN_PRICE    = "code_skill_then_price"
    GENERAL_SKILL_THEN_PRICE = "general_skill_then_price"
    LOWEST_TTFT              = "lowest_TTFT"
    FASTEST                  = "fastest"
    SMALLEST                 = "smallest"

@dataclass
class LLMConfig:
    """Configuration for LLM selection and usage. Data only."""
    # Routing / engines
    # If only_cleared_models is True, only use a model that has been "cleared" for use at NASA on open-source code.
    only_cleared_models:    bool = IS_NASA_COMPUTER
    only_local_models:      bool = False
    allow_local_models:     bool = True

    ollama_base_url:         str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    vllm_base_url:           str = os.getenv("VLLM_BASE_URL",   "http://localhost:8000")

    rate_throttle:          bool = True   # If true, throttle requests to avoid rate limits.
    rate_headroom:         float =  0.90  # e.g., use only 90% of limits to avoid bursts
    rate_retry_max_attempts: int =  6     # Tenacity: max retries on 429/ratelimit
    rate_retry_max_wait:     int = 60     # Tenacity: cap exponential backoff (seconds)
    rate_db_path:           Path = (Path.home() / ".univ_defs_llms_rate_tracking.db").resolve()  # SQLite DB for rate tracking

    availability_probe:                    bool = True
    availability_probe_ttl_sec:           float = 60.0   # cache window
    availability_probe_timeout:           float =  1.0   # seconds; keep short
    availability_probe_allow_costly:       bool = False  # if False, skip the 1-token fallback

    # Selection knobs
    selection_strategy: SelectionStrategy | str = SelectionStrategy.CHEAPEST
    min_context_tokens:                     int =    0
    assumed_prompt_tokens:                  int = 1000
    assumed_output_tokens:                  int = 1000

    # Candidates + scoring
    candidate_models:    list[str] = field(default_factory=list)    # if empty -> _default_candidate_models()

    # Optional: commonly-used knobs some programs keep near config
    default_temperature: float =    0.0
    max_tokens:            int = 1000

    model_scores: dict[str, float | dict[str, float]] = field(default_factory=dict)

    # --- multi-objective preferences ---
    prefer_code:                    bool = False  # emphasize coding skill
    prefer_low_TTFT:                bool = False  # emphasize time-to-first-token
    prefer_local:                   bool = False  # *prefer* local (not a hard requirement)
    max_estimated_cost:     float | None = None   # hard cap per (assumed_in, assumed_out)

    # Optional constraints
    speed_floor:                   float | None = None  # minimum speed (in tokens/sec) (if known)
    model_filter:    str | Sequence[str] | None = None  # only use these (e.g., ["gpt-4o", "mistral-large-2"])
    provider_filter: str | Sequence[str] | None = None  # only use these (e.g., "Anthropic", "OpenAI")

    # --- weights for the composite score (lower = better) ---
    # If a weight remains 0 but a corresponding prefer_* flag is True,
    # defaults are injected in _resolve_config() so you don't have to tune.
    weight_price:                  float = 1.0    # always keep some price pressure
    weight_code_skill:             float = 0.0
    weight_general_skill:          float = 0.0
    weight_TTFT:                   float = 0.0    # lower penalty when higher TTFT
    weight_speed:                  float = 0.0    # lower penalty when lower speed
    weight_nonlocal_penalty:       float = 0.0    # penalty if prefer_local=True and model is not local

_DEFAULT_MODEL_SKILL:      float =    0.5  # default skill level for models without specific default skill

_DEFAULT_MODEL_CONTEXT:      int =  8_192  # default context window for models without specific context

_DEFAULT_MODEL_PARAMETERS: float =   9E99  # default number of parameters for models without specific parameter count

_DEFAULT_MODEL_RPM:          int =     50  # default      requests-per-minute for models without specific RPM

_DEFAULT_MODEL_TPM_IN:       int = 30_000  # default input  tokens-per-minute for models without specific  input TPM

_DEFAULT_MODEL_TPM_OUT:      int =  8_000  # default output tokens-per-minute for models without specific output TPM

@dataclass
class ModelInfo:
    """Information about a candidate Large Language Model (LLM)."""
    name:                    str
    provider:                str  # e.g., "OpenAI", "Anthropic", "Mistral", "IBM"
    context_window:          int  # in+out, in tokens
    input_cost_per_token:  float  # $/token (normalized)
    output_cost_per_token: float  # $/token (normalized)
    available:              bool  # Is env/api key/endpoint reachable (best effort)?
    is_local:               bool  # True for Ollama, vLLM, or similar
    cleared:                bool  # True if "cleared" for use at NASA on open-source code.
    # Values without defaults have to be listed before values with defaults.
    runtime:        str | None = None  # e.g., "Ollama", "vLLM"
    parameters:            float = _DEFAULT_MODEL_PARAMETERS  # number of model parameters
    code_skill:            float = _DEFAULT_MODEL_SKILL  # 0..1, coding-centric capability
    general_skill:         float = _DEFAULT_MODEL_SKILL  # 0..1, broad/academic capability
    TTFT:           float | None = None  # time-to-first-token (seconds); None = unknown
    speed:          float | None = None  # tokens/sec after first token;  None = unknown
    meta:         dict[str, Any] = field(default_factory=dict)  # diagnostics/etc. not used for selection

    def __post_init__(self) -> None:
        """Post-initialization checks."""
        # Enforce runtime only when relevant.
        if self.is_local and not self.runtime:
            raise ValueError(f"runtime is required when is_local=True for model '{self.name}' (e.g., 'Ollama', 'vLLM').")

    def estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost for a given input/output token count."""
        return self.input_cost_per_token * tokens_in + self.output_cost_per_token * tokens_out

@dataclass
class SelectionContext:
    """Context passed to strategy functions."""
    tokens_in:          int
    tokens_out:         int
    min_context_tokens: int
    require_local:     bool = False
    require_cleared:   bool = IS_NASA_COMPUTER
    extras:  dict[str, Any] = field(default_factory=dict)

StrategyFn: TypeAlias = Callable[[Sequence[ModelInfo], SelectionContext], ModelInfo]

class LLMs:
    """
    - Routes via LiteLLM
    - Builds ModelInfo list, filters by availability/context
    - Applies registered/built-in selection strategy
    - Exposes stable send_prompt(...)
    """
    # ----------------------------
    # Default model preferences
    # ----------------------------

    model_info: dict[str, dict[str, Any]] = {

        ##################################
        # OpenAI
        ##################################

        "gpt-3.5-turbo": {
            "provider"      : "OpenAI",
            "context"       : 16_385,
            "code_skill"    : 0.60,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "gpt-4o-mini": {
            "provider"      : "OpenAI",
            "context"       : 128_000,
            "code_skill"    : 0.80,     # improved smalls trend; near 4.1-mini on many evals [S6]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "gpt-4o": {
            "provider"      : "OpenAI",
            "context"       : 128_000,
            "code_skill"    : 0.93,     # strong coding; multiple evals (Aider diff, SWE gains) [S6]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "gpt-4.1": {
            "provider"      : "OpenAI",
            "context"       : 1_000_000,  # [S5,S6]
            "code_skill"    : 0.94,       # OpenAI shows +21% vs 4o on SWE-bench Verified [S6]
            "general_skill" : 0.92,       # MMLU 90.2%, GPQA Diamond 66.3% [S6]
            "TTFT"          : 15.0,       # ~15s TTFT at 128k; ~60s at 1M (OpenAI) [S7]
            "speed"         : 124.0,      # ArtificialAnalysis provider aggregate [S2]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "gpt-4.1-mini": {
            "provider"      : "OpenAI",
            "context"       : 1_000_000,  # [S6] (OpenAI says 4.1 family supports up to 1M)
            "code_skill"    : 0.82,       # "beats 4o on many evals"; keep slightly above 4o-mini [S6]
            "speed"         : 75.8,       # AA aggregate (time-varying)
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "gpt-4.1-nano": {
            "provider"      : "OpenAI",
            "context"       : 1_000_000,  # [S6]
            "code_skill"    : 0.65,       # small, but 1M ctx and better than 4o-mini on some evals [S6]
            "TTFT"          : 5.0,        # "often <5s" for 128k inputs (OpenAI) [S7]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "o1-mini": {
            "provider"      : "OpenAI",
            "context"       : 128_000,  # context per OpenAI docs; o3/o4-mini are 200k [S28]
            "code_skill"    : 0.86,     # strong reasoning; coding solid but slower TTFT [S14,S7]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "o3-mini": {
            "provider"      : "OpenAI",
            "context"       : 200_000,  # [S28]
            "code_skill"    : 0.88,     # faster TTFT than o1-mini; coding near o1 mini [S12,S6]
            "general_skill" : 0.89,     # strong reasoning for size [S6,S7]
            "TTFT"          : 8.0,      # AA & coverage: higher latency than smalls, but improved vs o1 [S14,S7]
            "speed"         : 163.0,    # AA [S12]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "o4-mini": {
            "provider"      : "OpenAI",
            "context"       : 200_000,  # [S28]
            "code_skill"    : 0.90,     # newer small reasoning; top small-code in AA index
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "gpt-5": {
            "provider"      : "OpenAI",
            "context"       : 400_000,  # API total context, 128k max output (OpenAI) [S1]
            "code_skill"    : 0.96,     # frontier; AA shows top "intelligence index" class [S1,S21]
            "general_skill" : 0.95,     # AA Intelligence Index leader tier [S1,S21]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        ##################################
        # Anthropic
        ##################################

        "claude-3-haiku-20240307": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # Anthropic docs & launch note (200k at launch) [S60]
            "code_skill"    : 0.70,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : 50_000,
                               "tpm_out" : 10_000},
        },

        "claude-3-sonnet-20240229": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # Claude 3 family launched with 200k context [S60]
            "code_skill"    : 0.88,     # balanced capability/perf; below 3 Opus, well above Haiku
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "claude-3-opus-20240229": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # Claude 3 family launched with 200k context [S60]
            "code_skill"    : 0.91,     # strong reasoning/coding; below Claude 4 era, above 3 Sonnet
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : 20_000,
                               "tpm_out" : 4_000},
        },

        "claude-3-5-sonnet-20240620": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # GA with 200k; launch & cloud listings [S61,S62]
            "code_skill"    : 0.92,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : 40_000,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "claude-3-7-sonnet-20250219": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # [S21,S26,S27] (Sonnet 4 has 1M, not 3.7) [S20]
            "code_skill"    : 0.93,     # leads/near-top on SWE-bench Verified [S13,S16]
            "general_skill" : 0.90,     # hybrid reasoning; strong OSWorld & agentic [S16]
            "TTFT"          : 1.16,     # launch + AA metrics [S16,S36]
            "speed"         : 65.5,     # AA [S36]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : 20_000,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "claude-sonnet-4-20250514": {
            "provider"      : "Anthropic",
            "context"       : 1_000_000,  # Sonnet 4 supports 1M (Aug 12, 2025) [S50]
            "code_skill"    : 0.94,       # strong coding & reasoning; successor to 3.7 Sonnet [S52,S53]
            "general_skill" : 0.91,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "claude-opus-4-20250514": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # Opus 4 default 200k ctx (launch) [S52,S55]
            "code_skill"    : 0.95,     # frontier coding/agents positioning at launch [S52,S55]
            "general_skill" : 0.94,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "claude-opus-4-1-20250805": {
            "provider"      : "Anthropic",
            "context"       : 200_000,  # Opus 4.1 docs & Bedrock pages list 200k ctx [S49,S56]
            "code_skill"    : 0.95,     # upgrade vs Opus 4 on agentic coding & reasoning [S49]
            "general_skill" : 0.94,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "claude-sonnet-4-5-20250929": {
            "provider"      : "Anthropic",
            "context"       : 1_000_000,  # 1M context variant referenced; models overview [S47,S50]
            "code_skill"    : 0.95,       # SOTA on SWE-bench Verified; 30+ hr autonomous runs [S47]; strong agentic + computer-use gains [S58,S59]
            "general_skill" : 0.94,
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        ##################################
        # Mistral
        ##################################

        "mistral-large-2": {
            "provider"      : "Mistral",
            "context"       : 128_000,  # product pages and summaries [S9,S23]
            "code_skill"    : 0.90,     # claims match GPT-4o on coding; multiple writeups [S11,S17]
            "general_skill" : 0.86,     # broad improvements vs Large 1; multilingual [S9]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "mistral-medium-2505": {
            "provider"      : "Mistral",
            "context"       : 128_000,  # [S8]
            "code_skill"    : 0.82,     # below Large, above earlier Mediums; frontier multi [S8]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "codestral-25.01": {
            "provider"      : "Mistral",
            "context"       : 256_000,  # Mistral docs list Codestral 25.01/25.08 at 256k [S8,S10]
            "code_skill"    : 0.86,     # upgraded Codestral; ~2x speed & strong HE/MBPP [S10,S9]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        "codestral-25.08": {
            "provider"      : "Mistral",
            "context"       : 256_000,  # [S8]
            "code_skill"    : 0.88,     # latest Codestral (summer 2025) [S8]
            "local"         : False,
            "cleared"       : True,
            "parameters"    : _DEFAULT_MODEL_PARAMETERS,
            "rate_limit"    : {"scope"   : "provider",
                               "rpm"     : _DEFAULT_MODEL_RPM,
                               "tpm_in"  : _DEFAULT_MODEL_TPM_IN,
                               "tpm_out" : _DEFAULT_MODEL_TPM_OUT},
        },

        ##################################
        # Local (Ollama)
        ##################################

        "ollama/qwen2.5-coder:1.5b-base": {
            "provider"      : "Alibaba Cloud",
            "context"       : 32_768,
            "code_skill"    : 0.41,    # ~41 average across 9 langs for 1.5B *base* [S3]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 1.5E9,
            "cleared"       : False,  # Not cleared for use at NASA.
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/qwen2.5-coder:3b-base": {
            "provider"      : "Alibaba Cloud",
            "context"       : 32_768,
            "code_skill"    : 0.48,    # ~48 average across 9 langs for 3B *base* [S3]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 3.0E9,
            "cleared"       : False,  # Not cleared for use at NASA.
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/codegemma:2b-code": {
            "provider"      : "Google",
            "context"       : 8_192,   # [S38, S39]
            "code_skill"    : 0.311,   # HumanEval pass@1 = 31.1% (official model card)
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 2.0E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/starcoder2:3b": {
            "provider"      : "BigCode",
            "context"       : 16_384,  # StarCoder2 smalls default 16k
            "code_skill"    : 0.317,   # ~31.7% pass@1 typical; ~31.1 avg across langs in Qwen2.5 tbl [S3,S30]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 3.0E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/granite-code:3b": {
            "provider"      : "IBM",
            "context"       : 128_000,  # IBM Granite-3B-Code-Instruct-128K [S18]
            "code_skill"    : 0.262,    # [S40, S41]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 3.0E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/phi3.5:3.8b": {
            "provider"      : "Microsoft",
            "context"       : 128_000,  # Microsoft release/Foundry catalog [S34]
            "code_skill"    : 0.56,     # mid-estimate: reports cluster ~0.50–0.63 HE for 3.5-mini [S31,S33]
            "general_skill" : 0.69,     # Phi-3 mini MMLU ~69%; 3.5 mini similar+ [S32]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 3.8E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/mistral:7b-instruct-q4_0": {
            "provider"      : "Mistral",
            "context"       : 8_192,     # conservative default; some builds enable up to ~32k
            "code_skill"    : 0.52,      # solid general LLM; decent coding for 7B instruct
            "general_skill" : 0.64,      # typical bench range for Mistral-7B-Instruct [S42, S43, S44]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 7.0E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/llama3:8b": {
            "provider"      : "Meta",
            "context"       : 8_192,
            "code_skill"    : 0.55,   # aligns w/ public mid-tier code results
            "general_skill" : 0.66,   # Llama3-8B MMLU ballpark; public reports ~66–67% [S35]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 8.0E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },

        "ollama/llama3.1:8b-instruct-q4_0": {
            "provider"      : "Meta",
            "context"       : 128_000,   # Llama 3.1 8B supports 128k
            "code_skill"    : 0.58,      # slight bump vs Llama 3 8B; quantized
            "general_skill" : 0.70,      # stronger reasoning/knowledge vs 3.0 [S45, S46]
            "local"         : True,
            "runtime"       : "Ollama",
            "parameters"    : 8.0E9,
            "cleared"       : True,
            "rate_limit"    : {"scope": "model", "rpm": 0, "tpm_in": 0, "tpm_out": 0},  # unlimited
        },
    }

    ##################################
    # References
    ##################################
    #  S1 — OpenAI: Introducing GPT-5 for developers — https://openai.com/index/introducing-gpt-5-for-developers/
    #  S2 — Artificial Analysis: GPT-4.1 (speed/latency/TPS aggregates) — https://artificialanalysis.ai/models/gpt-4-1
    #  S3 — Aider LLM Leaderboards (Polyglot code-editing benchmark) — https://aider.chat/docs/leaderboards/
    #  S4 — OpenAI: Introducing GPT-5 (overview/benchmarks) — https://openai.com/index/introducing-gpt-5/
    #  S5 — OpenAI: Introducing GPT-4.1 in the API (capabilities & SWE-bench Verified) — https://openai.com/index/gpt-4-1/
    #  S6 — OpenAI: GPT-4.1 long-context details (up to 1M tokens) — https://openai.com/index/gpt-4-1/#long-context
    #  S7 — Artificial Analysis: GPT-4.1 (Providers view; TTFT/output speed) — https://artificialanalysis.ai/models/gpt-4-1/providers
    #  S8 — Mistral Docs: Models Overview (incl. mistral-medium-2505/2508, codestral-2508) — https://docs.mistral.ai/getting-started/models/models_overview/
    #  S9 — Mistral Blog: "Large Enough" (Mistral Large 2; 128k context, positioning) — https://mistral.ai/news/mistral-large-2407
    # S10 — Mistral Blog: Codestral 25.01 announcement — https://mistral.ai/news/codestral-2501
    # S11 — Artificial Analysis: Mistral Large 2 (quality/price/speed aggregates) — https://artificialanalysis.ai/models/mistral-large-2
    # S12 — Artificial Analysis: o3-mini (speed/latency metrics) — https://artificialanalysis.ai/models/o3-mini
    # S13 — OpenAI: Introducing o3 and o4-mini (reasoning series) — https://openai.com/index/introducing-o3-and-o4-mini/
    # S14 — TextCortex review: o3-mini vs o1-mini (relative response speed) — https://textcortex.com/post/openai-o3-mini-review
    # S15 — Mistral Docs: Codestral 2508 (latest Codestral release entry) — https://docs.mistral.ai/getting-started/models/models_overview/#codestral-2508
    # S16 — Anthropic News: Claude 3.7 Sonnet launch/overview — https://www.anthropic.com/news/claude-3-7-sonnet
    # S17 — AWS Blog: Mistral Large 2 now in Bedrock (confirms 128k context) — https://aws.amazon.com/blogs/machine-learning/mistral-large-2-is-now-available-in-amazon-bedrock/
    # S18 — IBM Granite-3B-Code-Instruct model card (context/perf references) — https://huggingface.co/ibm-granite/granite-3b-code-instruct
    # S19 — OpenAI: New tools & features in the Responses API (o3/o4-mini integration; 2025) — https://openai.com/index/new-tools-and-features-in-the-responses-api/
    # S20 — Anthropic News: Claude Opus 4.1 (SWE-bench Verified 74.5%) — https://www.anthropic.com/news/claude-opus-4-1
    # S21 — OpenAI: GPT-5 (coding focus; SWE-bench methodology note) — https://openai.com/index/introducing-gpt-5/
    # S22 — The Verge: GPT-4.1 in ChatGPT (rollout; context & coding improvements) — https://www.theverge.com/news/667507/openai-chatgpt-gpt-4-1-ai-model-general-availability
    # S23 — NVIDIA NIM Ref: Mistral Large 2 Instruct (128k context confirmation) — https://docs.api.nvidia.com/nim/reference/mistralai-mistral-large-2-instruct
    # S24 — OpenAI Blog: GPT-4o mini (128k context & pricing) — https://openai.com/index/gpt-4o-mini-advancing-cost-efficient-intelligence/
    # S25 — OpenAI Docs: o4-mini model page — https://platform.openai.com/docs/models/o4-mini
    # S26 — Qwen2.5-Coder technical report (benchmarks overview) — https://arxiv.org/abs/2501.03012
    # S27 — HF Model Card: Qwen2.5-Coder-3B-Base — https://huggingface.co/Qwen/Qwen2.5-Coder-3B
    # S28 — OpenAI Help: o3 & o4-mini context (200k) — https://help.openai.com/en/articles/9855712-openai-o1-models-faq-chatgpt-enterprise-and-edu
    # S29 — StarCoder2 paper (model details; evals) — https://arxiv.org/abs/2402.19173
    # S30 — HF Model Card: BigCode/StarCoder2-3B — https://huggingface.co/bigcode/starcoder2-3b
    # S31 — Phi-3 Technical Report (MMLU 69% etc.) — https://arxiv.org/abs/2404.14219
    # S32 — Meta Llama 3 models overview (general capability references) — https://www.llama.com/models/llama-3/
    # S33 — HF Model Card: microsoft/Phi-3-mini-128k-instruct (3.8B; 128k ctx) — https://huggingface.co/microsoft/Phi-3-mini-128k-instruct
    # S34 — NVIDIA NIM / HF: Phi-3.5-MoE (128k ctx; MoE details) — https://docs.api.nvidia.com/nim/reference/microsoft-phi-3_5-moe
    # S35 — HF Model Card: meta-llama/Meta-Llama-3-8B (8k ctx; base references) — https://huggingface.co/meta-llama/Meta-Llama-3-8B
    # S36 — Artificial Analysis: Claude 3.7 Sonnet (standard/thinking; TTFT & TPS) — https://artificialanalysis.ai/models/claude-3-7-sonnet / https://artificialanalysis.ai/models/claude-3-7-sonnet-thinking
    # S37 — OpenAI Community - https://community.openai.com/t/what-is-the-token-context-window-size-of-the-gpt-4-o1-preview-model/954321
    # S38 - https://huggingface.co/google/codegemma-2b
    # S39 - https://arxiv.org/pdf/2406.11409
    # S40 - https://huggingface.co/ibm-granite/granite-3b-code-instruct-128k/blame/main/README.md
    # S41 - https://www.ibm.com/docs/en/watsonx/w-and-w/2.2.0?topic=models-granite-3b-code-instruct-v2-model-card
    # S42 - MMLU-CF leaderboard — row "Mistral-7B-instruct-v0.3" (MMLU 5-shot 60.3; MMLU-CF 5-shot 50.7; also 0-shot values) - https://github.com/microsoft/MMLU-CF
    # S43 - Evaluating Code Quality from Quantized LLMs — reports Mistral Instruct 7B HumanEval+ pass@1 ≈ 25% (notes the EvalPlus variant) - https://arxiv.org/pdf/2411.10656
    # S44 - Mistral 7B announcement — qualitative coding claim "approaches CodeLlama 7B performance on code" - https://mistral.ai/news/announcing-mistral-7b
    # S45 - Meta Llama 3.1 8B Instruct model card — instruction-tuned benchmarks incl. MMLU 69.4, HumanEval 72.6, MBPP++ 72.8 - https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
    # S46 - Llama 3.1 8B Instruct eval details dataset — per-task results backing the model card table - https://huggingface.co/datasets/meta-llama/Llama-3.1-8B-Instruct-evals
    # S47 — Anthropic: Introducing Claude Sonnet 4.5 — https://www.anthropic.com/news/claude-sonnet-4-5
    # S48 — Anthropic: Claude 3.5 Haiku page (availability/pricing) — https://www.anthropic.com/claude/haiku
    # S49 — Anthropic News: Claude Opus 4.1 — https://www.anthropic.com/news/claude-opus-4-1
    # S50 — Claude Docs: Models overview (Sonnet 4 & 4.5 1M context header) — https://docs.claude.com/en/docs/about-claude/models/overview
    # S51 — Google Vertex AI: Claude Sonnet 4 (release date) — https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/sonnet-4
    # S52 — Anthropic: Introducing Claude 4 (Opus 4 & Sonnet 4 launch) — https://www.anthropic.com/news/claude-4
    # S53 — OpenRouter: Claude Sonnet 4 (capabilities & benchmarks) — https://openrouter.ai/anthropic/claude-sonnet-4
    # S54 — Google Vertex AI: Claude 3.5 Haiku (release date listing) — https://cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude/haiku-3-5
    # S55 — AWS Blog: Introducing Claude 4 in Amazon Bedrock (200k ctx) — https://aws.amazon.com/blogs/aws/claude-opus-4-anthropics-most-powerful-model-for-coding-is-now-in-amazon-bedrock/
    # S56 — AWS Bedrock model page: Anthropic (Opus 4.1, 200k ctx) — https://aws.amazon.com/bedrock/anthropic/
    # S57 — AWS Blog: Claude Sonnet 4.5 in Amazon Bedrock — https://aws.amazon.com/blogs/aws/introducing-claude-sonnet-4-5-in-amazon-bedrock-anthropics-most-intelligent-model-best-for-coding-and-complex-agents/
    # S58 — The Verge: Anthropic releases Claude Sonnet 4.5 (30-hour agents, coding) — https://www.theverge.com/ai-artificial-intelligence/787524/anthropic-releases-claude-sonnet-4-5-in-latest-bid-for-ai-agents-and-coding-supremacy
    # S59 — Reuters: Anthropic launches Claude 4.5 (enterprise focus; 30-hour autonomy) — https://www.reuters.com/business/retail-consumer/anthropic-launches-claude-45-touts-better-abilities-targets-business-customers-2025-09-29/
    # S60 — Anthropic: Claude 3 family launch (200k context at launch) — https://www.anthropic.com/news/claude-3-family
    # S61 — Anthropic: Claude 3.5 Sonnet announcement (Jun 21, 2024) — https://www.anthropic.com/news/claude-3-5-sonnet
    # S62 — Google Cloud Blog: Claude 3.5 Sonnet on Vertex AI (Jun 20, 2024) — https://cloud.google.com/blog/products/ai-machine-learning/announcing-anthropics-claude-3-5-sonnet-on-vertex-ai-providing-more-choice-for-enterprises

    # Provider -> required env var
    _provider_env: dict[str, str] = {
        "OpenAI"    : "OPENAI_API_KEY",
        "Anthropic" : "ANTHROPIC_API_KEY",
        "Mistral"   : "MISTRAL_API_KEY",
    }

    _vllm_aliases = ("vllm", "vllm-openai", "vllm_compatible")

    def __init__(self) -> None:
        """Initialize LLMs manager. Call apply_config() before use."""
        self._config:                           LLMConfig | None = None
        self._base_config:                      LLMConfig | None = None  # re-apply after failure/reconnect
        self._temp_unavailable_models:                  set[str] = set()  # transient banlist after failures
        self._temp_unavailable_providers:               set[str] = set()
        self._selected:                         ModelInfo | None = None
        self._candidates_after_filter:           list[ModelInfo] = []
        self._strategies:                  dict[str, StrategyFn] = {}
        self._last_strategy:                                 str = str(SelectionStrategy.CHEAPEST.value)
        self._pricing_cache: dict[str, tuple[float, float, int]] = {}
        self._litellm_ready:                                bool = False  # True when/if LiteLLM client has been imported
        self._litellm_mod:                            Any | None = None
        self._availability_cache: dict[tuple[str, str], tuple[bool, float]] = {}
        self._register_builtin_strategies()

    @property
    def selected(self) -> ModelInfo | None:
        """Read-only handle to the currently selected model (or None)."""
        return self._selected

    @property
    def model(self) -> str | None:
        """Selected model name."""
        return self._selected.name     if self._selected else None

    @property
    def provider(self) -> str | None:
        """Selected provider name."""
        return self._selected.provider if self._selected else None

    def apply_config(self, config: LLMConfig) -> None:
        """
        Store config, hydrate defaults, compute candidates, select a model.
        """
        # Keep the user-provided config so we can re-apply it later on failure
        self._base_config = replace(config)
        cfg               = self._resolve_config(config)
        self._config      = cfg

        # Build pool and context with the resolved cfg
        eff, ctx, reasons_map = self._selection_pool(cfg)

        # Choose strategy (same logic you already have)
        if isinstance(cfg.selection_strategy, SelectionStrategy):
            strategy_name = cfg.selection_strategy.value
        else:
            strategy_name = str(cfg.selection_strategy)

        wants_multi = any([
            cfg.prefer_code,
            cfg.prefer_low_TTFT, cfg.prefer_local,
            cfg.max_estimated_cost is not None,
            cfg.speed_floor        is not None,
            cfg.weight_code_skill       > 0.0,
            cfg.weight_general_skill    > 0.0,
            cfg.weight_TTFT             > 0.0,
            cfg.weight_speed            > 0.0,
            cfg.weight_nonlocal_penalty > 0.0,
        ])
        if wants_multi and strategy_name == SelectionStrategy.CHEAPEST.value:
            strategy_name = "multi_objective"

        strategy_fn         = self._strategies.get(strategy_name) or \
                              self._strategies[SelectionStrategy.CHEAPEST.value]
        self._last_strategy = strategy_name

        winner              = strategy_fn(eff, ctx)
        self._selected      = winner
        self._candidates_after_filter = eff
        for mi in self._candidates_after_filter:
            mi.meta["filter_reasons"] = reasons_map.get(mi.name, [])
        self._after_selection(winner.name, winner.provider)

    def refresh_selection(self) -> None:
        """Re-run selection using the current LLMConfig."""
        if self._config is None:
            raise RuntimeError("refresh_selection() called before apply_config().")
        self.apply_config(self._config)

    def get_config(self) -> LLMConfig:
        """Return a copy of the current config (or default if none applied yet)."""
        if self._config is None:
            # Return a default config if none applied yet.
            return LLMConfig()
        return replace(self._config)

    def register_strategy(self, name: str, fn: StrategyFn) -> None:
        """Register a custom strategy for model selection."""
        self._strategies[name] = fn

    def _register_builtin_strategies(self) -> None:
        """Define built-in strategies for model selection."""

        def cheapest(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """Cheapest model among candidates, ignoring any other factors."""
            return min(cands, key=lambda m: m.estimate_cost(ctx.tokens_in, ctx.tokens_out))

        def context_then_price(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """Context-aware selection, then price."""
            # cands already filtered by context; cheapest among them
            return min(cands, key=lambda m: m.estimate_cost(ctx.tokens_in, ctx.tokens_out))

        def code_skill_then_price(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """Highest code skill, then cheapest among those."""
            def key(m: ModelInfo) -> tuple[float, float]:
                """Key function for code_skill-then-price strategy."""
                return (-m.code_skill, m.estimate_cost(ctx.tokens_in, ctx.tokens_out))
            return min(cands, key=key)

        def general_skill_then_price(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """Highest general skill, then cheapest among those."""
            def key(m: ModelInfo) -> tuple[float, float]:
                """Key function for general_skill-then-price strategy."""
                return (-m.general_skill, m.estimate_cost(ctx.tokens_in, ctx.tokens_out))
            return min(cands, key=key)

        def lowest_TTFT(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """
            Lowest TTFT (Time To First Token) among candidates.
            Treat unknown TTFT as worst; tie-break by price.
            """
            def key(m: ModelInfo) -> tuple[float, float]:
                """Key function for lowest_TTFT strategy."""
                TTFT = m.TTFT if m.TTFT is not None else float("inf")
                return (TTFT, m.estimate_cost(ctx.tokens_in, ctx.tokens_out))
            return min(cands, key=key)

        def fastest(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """
            Fastest model among candidates.
            Highest speed is best; unknown speed is worst; tie-break by price.
            """
            def key(m: ModelInfo) -> tuple[float, float]:
                """Key function for fastest strategy."""
                sp = m.speed if m.speed is not None else -1.0
                # We invert for max; min() will prefer higher speed by sorting negative
                return (-sp, m.estimate_cost(ctx.tokens_in, ctx.tokens_out))
            return min(cands, key=key)

        def smallest(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """Model with fewest parameters among candidates."""
            return min(cands, key=lambda m: m.parameters)

        def multi_objective(cands: Sequence[ModelInfo], ctx: SelectionContext) -> ModelInfo:
            """Using multiple preferences and weights, choose the best-fit model."""
            cfg = self._config or LLMConfig()

            # Group stats for normalization
            costs     = [m.estimate_cost(cfg.assumed_prompt_tokens,
                                         cfg.assumed_output_tokens) for m in cands]
            max_cost  = max(costs) if costs else 1.0

            TTFTs     = [m.TTFT for m in cands if m.TTFT is not None]
            max_TTFT  = max(TTFTs) if TTFTs else 1.0

            speeds    = [m.speed for m in cands if m.speed is not None]
            max_speed = max(speeds) if speeds else 1.0

            def key(m: ModelInfo) -> float:
                """Key function for multi-objective optimization."""
                # Hard caps first: if user set max cost, filter; if all filtered, caller will fallback
                est_cost = m.estimate_cost(cfg.assumed_prompt_tokens, cfg.assumed_output_tokens)
                if cfg.max_estimated_cost is not None and est_cost > cfg.max_estimated_cost:
                    logging.warning("multi_objective: candidate %s excluded by max_estimated_cost=%.6g despite the fact that _selection_pool() should have filtered it out. est_cost=%.6g", m.name, cfg.max_estimated_cost, est_cost)

                # Normalized penalties (0=best)
                cost_pen = est_cost / max_cost if max_cost > 0 else 0.0

                if m.TTFT is not None and max_TTFT > 0:
                    TTFT_pen = m.TTFT / max_TTFT
                else:
                    TTFT_pen = 1.0  # unknown => mild penalty if weighted

                if m.speed is not None and max_speed > 0:
                    speed_pen = 1.0 - (m.speed / max_speed)  # higher speed => lower penalty
                else:
                    speed_pen = 1.0  # unknown speed

                code_pen = 1.0 - (m.code_skill    if m.code_skill    is not None else _DEFAULT_MODEL_SKILL)
                gen_pen  = 1.0 - (m.general_skill if m.general_skill is not None else _DEFAULT_MODEL_SKILL)
                nonlocal_pen = 0.0 if m.is_local else 1.0

                # Optional floor on speed (soft penalty, not exclusion)
                if cfg.speed_floor is not None:
                    if m.speed is None:
                        speed_pen += 1.0
                    elif m.speed < cfg.speed_floor:
                        # Scale the penalty relative to how far below the floor to avoid a hard jump:
                        speed_pen += (cfg.speed_floor - m.speed) / max_speed if max_speed else 1.0

                score = (  cfg.weight_price            * cost_pen
                         + cfg.weight_TTFT             * TTFT_pen
                         + cfg.weight_speed            * speed_pen
                         + cfg.weight_code_skill       * code_pen
                         + cfg.weight_general_skill    * gen_pen
                         + cfg.weight_nonlocal_penalty * nonlocal_pen)
                return score

            return min(cands, key=key)

        self._strategies[SelectionStrategy.CHEAPEST.value]                 = cheapest
        self._strategies[SelectionStrategy.CONTEXT_THEN_PRICE.value]       = context_then_price
        self._strategies[SelectionStrategy.CODE_SKILL_THEN_PRICE.value]    = code_skill_then_price
        self._strategies[SelectionStrategy.GENERAL_SKILL_THEN_PRICE.value] = general_skill_then_price
        self._strategies[SelectionStrategy.LOWEST_TTFT.value]              = lowest_TTFT
        self._strategies[SelectionStrategy.FASTEST.value]                  = fastest
        self._strategies[SelectionStrategy.SMALLEST.value]                 = smallest
        self._strategies["multi_objective"]                                = multi_objective

    def list_candidates(self, with_reasons: bool = False) -> list[ModelInfo]:
        """
        Return the candidate list after filtering.
        If with_reasons=True, include 'filter_reasons' in meta where applicable.
        """
        res = [replace(mi, meta=dict(mi.meta)) for mi in self._candidates_after_filter]  # deep-copy meta
        if not with_reasons:
            for mi in res:
                mi.meta.pop("filter_reasons", None)
        return res

    def _selection_pool(self, cfg: LLMConfig) -> tuple[list[ModelInfo],
                                                       SelectionContext,
                                                       dict[str, list[str]]]:
        """Build the effective candidate pool and SelectionContext for a given config."""
        raw_candidates = [self._build_model_info(m, cfg) for m in cfg.candidate_models]
        ctx = SelectionContext(
            tokens_in=cfg.assumed_prompt_tokens,
            tokens_out=cfg.assumed_output_tokens,
            min_context_tokens=cfg.min_context_tokens,
            require_local=cfg.only_local_models,
            require_cleared=cfg.only_cleared_models,
        )
        eff, reasons_map = self._filter_candidates(raw_candidates, ctx)
        if cfg.max_estimated_cost is not None:
            capped = [
                m for m in eff
                if m.estimate_cost(cfg.assumed_prompt_tokens, cfg.assumed_output_tokens) <= cfg.max_estimated_cost
            ]
            if capped:
                eff = capped
            else:
                # Helpful failure: the cap is below the cheapest candidate
                cheapest      = min(eff, key=lambda m: m.estimate_cost(cfg.assumed_prompt_tokens,
                                                                       cfg.assumed_output_tokens))
                cheapest_cost = cheapest.estimate_cost(cfg.assumed_prompt_tokens,
                                                       cfg.assumed_output_tokens)
                raise RuntimeError(
                    f"No candidates under max_estimated_cost={cfg.max_estimated_cost:.6g}. "
                    f"Cheapest is '{cheapest.name}' at ~${cheapest_cost:.4g} "
                    f"for assumed_in={cfg.assumed_prompt_tokens}, assumed_out={cfg.assumed_output_tokens}."
                )
        if cfg.speed_floor is not None:
            tmp = [m for m in eff if (m.speed is not None and m.speed >= cfg.speed_floor)]
            if tmp:
                eff = tmp
        if not eff:
            sample = dict(list(reasons_map.items())[:5])
            raise RuntimeError(
                "No candidates available after filtering. "
                f"candidates={len(raw_candidates)}; reasons_sample={sample}. "
                "Check allow_local_models, min_context_tokens, candidate_models, and provider availability."
            )
        return eff, ctx, reasons_map

    # Use overloads to indicate the different return types based on return_reasons to appease mypy.
    @overload
    def alternative_model(self, *, strategy: SelectionStrategy | str,
                          return_reasons: Literal[True],
                          **cfg_overrides: Any) -> tuple[ModelInfo, dict[str, list[str]]]:
        """Overload: return (ModelInfo, reasons_map) when return_reasons=True."""
        ...

    @overload
    def alternative_model(self, *, strategy: SelectionStrategy | str,
                          return_reasons: Literal[False] = False,  # This shows the default value for return_reasons is False
                          **cfg_overrides: Any) -> ModelInfo:
        """Overload: return ModelInfo when return_reasons=False (default)."""
        ...

    def alternative_model(self, *, strategy: SelectionStrategy | str,
                          return_reasons: bool = False, **cfg_overrides: Any) -> ModelInfo | tuple[ModelInfo, dict[str, list[str]]]:
        """
        Return the best candidate under a given strategy using a TEMPORARY config
        built from the current config + partial overrides (e.g., only_local_models=True),
        WITHOUT mutating the current selection.

        Args:
            strategy:        SelectionStrategy enum or string name of a registered strategy.
            return_reasons:  If True, return a tuple (ModelInfo, reasons_map) where
                             reasons_map is a dict of model name -> list of filter reasons.
            **cfg_overrides: Partial overrides to apply to the current config
                             (e.g., only_local_models=True).

        Returns:
            The selected ModelInfo, or (ModelInfo, reasons_map) if return_reasons is True.

        Raises:
            ValueError: If the strategy is unknown or if overrides are invalid.
        """
        base_cfg = self.get_config()  # snapshot of current config (already resolved by apply_config)
        # apply partial overrides
        try:
            tmp_cfg = replace(base_cfg, **cfg_overrides)
        except TypeError as e:
            raise ValueError(f"Invalid override(s): {e}")
        # Re-resolve in case overrides trigger weight injections, etc.
        tmp_cfg  = self._resolve_config(tmp_cfg)
        # Build pool (handles forced-local inside)
        eff, ctx, reasons_map = self._selection_pool(tmp_cfg)
        # Pick strategy
        name = strategy.value if isinstance(strategy, SelectionStrategy) else str(strategy)
        fn = self._strategies.get(name)
        if fn is None:
            raise ValueError(f"Unknown strategy: {name}")
        winner = fn(eff, ctx)
        return (winner, reasons_map) if return_reasons else winner

    def describe_selection(self) -> dict[str, Any]:
        """Describe the current model selection."""
        chosen = self._selected
        cfg    = self._config or LLMConfig()
        if chosen is None:
            return {
                "chosen_model" : None,
                "provider"     : None,
                "strategy"     : getattr(self, "_last_strategy", str(cfg.selection_strategy)),
                "explanation"  : "No selection computed yet. Call apply_config().",
            }
        considered = []
        for mi in self._candidates_after_filter:
            considered.append({
                "name"                  : mi.name,
                "provider"              : mi.provider,
                "context_window"        : mi.context_window,
                "input_cost_per_token"  : mi.input_cost_per_token,
                "output_cost_per_token" : mi.output_cost_per_token,
                "code_skill"            : mi.code_skill,
                "general_skill"         : mi.general_skill,
                "TTFT"                  : mi.TTFT,
                "speed"                 : mi.speed,
                "estimated_cost"        : mi.estimate_cost(cfg.assumed_prompt_tokens,
                                                           cfg.assumed_output_tokens),
                "available"             : mi.available,
                "local"                 : mi.is_local,
                "runtime"               : mi.runtime,
                "meta"                  : {"filter_reasons": mi.meta.get("filter_reasons", [])},
            })
        return {
            "chosen_model"   : chosen.name,
            "provider"       : chosen.provider,
            "context_window" : chosen.context_window,
            "estimated_cost" : chosen.estimate_cost(cfg.assumed_prompt_tokens,
                                                    cfg.assumed_output_tokens),
            "strategy"       : getattr(self, "_last_strategy", str(cfg.selection_strategy)),
            "weights"        : {
                "price"               : cfg.weight_price,
                "code_skill"          : cfg.weight_code_skill,
                "general_skill"       : cfg.weight_general_skill,
                "TTFT"                : cfg.weight_TTFT,
                "speed"               : cfg.weight_speed,
                "nonlocal_penalty"    : cfg.weight_nonlocal_penalty,
            },
            "prefs": {
                "prefer_code"         : cfg.prefer_code,
                "prefer_low_TTFT"     : cfg.prefer_low_TTFT,
                "prefer_local"        : cfg.prefer_local,
                "max_estimated_cost"  : cfg.max_estimated_cost,
                "speed_floor"         : cfg.speed_floor,
                "provider_filter"     : cfg.provider_filter,
                "model_filter"        : cfg.model_filter,
                "only_local_models"   : cfg.only_local_models,
                "only_cleared_models" : cfg.only_cleared_models,
            },
            "considered"     : considered,
        }

    def _call_with_backoff(self, litellm_mod: Any, **kwargs: Any) -> Any:
        """
        When rate_throttle=True, use Tenacity to retry on 429/ratelimit-ish errors
        with exponential backoff. Otherwise call once (respecting LiteLLM's built-in retries if used).
        """
        cfg         = self._config or LLMConfig()
        use_backoff = bool(cfg.rate_throttle)

        # Helper to detect rate-limit-ish errors
        def _is_rate_limit_exc(err: Exception) -> bool:
            """Return True if the exception looks like a rate-limit error."""
            m = str(err).casefold()
            return ("rate limit" in m) or ("ratelimit" in m) or ("429" in m) or ("too many requests" in m)

        if not use_backoff:
            comp_with_retries = getattr(litellm_mod, "completion_with_retries", None)
            if callable(comp_with_retries):
                return comp_with_retries(max_retries=2, **kwargs)
            return litellm_mod.completion(**kwargs)

        try:
            from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception
        except Exception:
            # Tenacity not installed: do a light single backoff using Retry-After if present
            try:
                return litellm_mod.completion(**kwargs)
            except Exception as e:
                if _is_rate_limit_exc(e):
                    import re
                    import time
                    m = re.search(r"retry[- ]after[:=]\s*(\d+)", str(e).lower())
                    if m:
                        time.sleep(float(m.group(1)))
                    else:
                        time.sleep(2.0)
                    return litellm_mod.completion(**kwargs)
                raise

        # With Tenacity
        max_attempts = int(getattr(cfg, "rate_retry_max_attempts", 6))
        max_wait     = int(getattr(cfg, "rate_retry_max_wait",    60))

        @retry(
            retry=retry_if_exception(_is_rate_limit_exc),           # only 429-ish
            wait=wait_random_exponential(min=1, max=max_wait),
            stop=stop_after_attempt(max_attempts),
            reraise=True,
        )
        def _do() -> Any:
            """Inner function to apply Tenacity retry logic."""
            comp_with_retries = getattr(litellm_mod, "completion_with_retries", None)
            if callable(comp_with_retries):
                return comp_with_retries(max_retries=1, **kwargs)   # keep LiteLLM retries small under Tenacity
            return litellm_mod.completion(**kwargs)

        return _do()

    def send_prompt(self, prompt: str, system_message: str,
                    model: str, temperature: float,
                    max_tokens: int = 1000) -> str:
        """
        Send a prompt+system message to the specified model, return the text response.

        Args:
            prompt:         The user prompt to send.
            system_message: The system message to include.
            model:          The model name to use (must be in model_info).
            temperature:    Sampling temperature.
            max_tokens:     Maximum tokens to generate in the response.

        Returns:
            The text response from the model.

        Raises:
            RuntimeError: If the model is unknown or if the request fails.
            ValueError:   If the prompt is empty.
        """
        if prompt is None:
            raise ValueError("prompt must not be None")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string")

        # Ensure LiteLLM and prepare common kwargs
        self._ensure_litellm()
        litellm = self._litellm_mod  # type: ignore
        messages = [{"role": "system", "content": system_message},
                  {"role": "user",   "content": prompt}]
        extra = self._extra_litellm_args_for(model)

        # --- Throttle preflight: estimate tokens and enforce caps ---
        inp_tok, out_tok = self._estimate_tokens_io(messages, model, max_tokens)
        self._throttle_if_needed(
            provider=(self.model_info.get(model, {}) or {}).get("provider", "Unknown"),
            model=model,
            tokens_in=inp_tok,
            tokens_out=out_tok,
        )

        # ---- Preflight: context-window warning (best-effort; never blocks the call) ----
        try:
            _, _, context_window = self._get_model_pricing_and_context(model)
            if context_window:
                input_tokens = self._count_chat_tokens(messages, model)
                if input_tokens + max_tokens > context_window:
                    orig       = max_tokens
                    max_tokens = max(0, context_window - input_tokens)
                    if max_tokens == 0:
                        raise ValueError(f"Prompt+system ({input_tokens} toks) fully occupies the {context_window} token window for {model}.")
                    logging.warning("Clamped max_tokens from %d to %d to fit context for %s",
                                    orig, max_tokens, model)
        except Exception as e:
            logging.warning("send_prompt: context window check failed for %s: %s", model, e)

        # ---- Invoke LiteLLM (prefer retries when available) ----
        kwargs = dict(model=model,
                      messages=messages,
                      temperature=temperature,
                      max_tokens=max_tokens,
                      **extra)
        try:
            resp = self._call_with_backoff(litellm, **kwargs)
            try:
                self._temp_unavailable_models.clear()
                self._temp_unavailable_providers.clear()
            except Exception as e2:
                logging.warning("Could not clear temporary banlists: %s", e2)
        except Exception as e:
            # Mark the current model as temporarily unavailable for re-selection
            try:
                self._temp_unavailable_models.add(model)
                prov = (self.model_info.get(model, {}) or {}).get("provider")
                # Only ban the provider if it looks like a provider-wide issue
                if isinstance(prov, str) and prov and self._should_ban_provider_for(e):
                    self._temp_unavailable_providers.add(prov)
            except Exception as e3:
                logging.warning("Could not update temporary banlists: %s", e3)
            # ---- Iterative failover: try the next best candidates under the same strategy ----
            base_cfg = self._base_config or self.get_config()
            last_exc = e
            tried_models: set[str] = {model}
            max_attempts = 5
            for _ in range(max_attempts):
                try:
                    self.apply_config(base_cfg)
                    failover_model = self.model or model
                    if failover_model in tried_models:
                        alt = self.alternative_model(strategy=self._last_strategy)
                        failover_model = alt.name
                    tried_models.add(failover_model)
                    extra2  = self._extra_litellm_args_for(failover_model)
                    kwargs2 = dict(model=failover_model,
                                   messages=messages,
                                   temperature=temperature,
                                   max_tokens=max_tokens,
                                   **extra2)
                    resp = self._call_with_backoff(litellm, **kwargs2)
                    # success -> clear bans and RETURN immediately
                    try:
                        self._temp_unavailable_models.clear()
                        self._temp_unavailable_providers.clear()
                    except Exception as e4:
                        logging.warning("Could not clear temporary banlists: %s", e4)
                    return self._extract_text_from_openai_like(resp)
                except Exception as e5:
                    last_exc = e5
                    try:
                        self._temp_unavailable_models.add(failover_model)
                        prov2 = (self.model_info.get(failover_model, {}) or {}).get("provider")
                        if isinstance(prov2, str) and prov2 and self._should_ban_provider_for(e5):
                            self._temp_unavailable_providers.add(prov2)
                    except Exception as e6:
                        logging.warning("Could not update temporary banlists: %s", e6)
            # If we reach here, all failovers failed
            my_critical_error(
                f"LiteLLM request failed for model '{model}' and iterative failover also failed. "
                f"original_error={e}; last_error={last_exc}"
            )
        return self._extract_text_from_openai_like(resp)

    # ====================================================
    # overridable hooks (tiny, intentional)
    # ====================================================

    def _default_candidate_models(self) -> list[str]:
        """Return a sane default list combining remote + local names."""
        return list(self.model_info.keys())

    def _extra_litellm_args_for(self, model: str) -> dict[str, Any]:
        """
        Per-model transport args for LiteLLM (e.g., {'api_base': self.ollama_base_url}
        for "runtime == "Ollama"). Default returns {}.
        """
        cfg   = self._config or LLMConfig()
        entry = self.model_info.get(model, {})
        runtime = (entry.get("runtime") or "").strip().casefold()
        if entry.get("local") is True and runtime:
            if runtime == "ollama":
                base = (cfg.ollama_base_url or "").rstrip("/")
                return {"api_base": base} if base else {}
            if runtime in self._vllm_aliases:
                base = (cfg.vllm_base_url or "").rstrip("/")
                return {"api_base": base} if base else {}
        return {}

    def _after_selection(self, model: str, provider: str) -> None:
        """Optional hook for telemetry/logging; default no-op."""
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Selected model %s (%s)", model, provider)

    # ====================================================
    # internals
    # ====================================================

    def _resolve_config(self, config: LLMConfig) -> LLMConfig:
        """Hydrate defaults: candidates, scores (with env JSON merge)."""
        try:
            if not config.only_local_models and not is_internet_available():
                logging.warning("Internet not available; forcing only_local_models=True")
                config = replace(config, only_local_models=True)
        except Exception as e:
            # Never fail just because connectivity check had an issue
            logging.warning("Ignoring the fact that the internet connectivity check failed: %s", e)
        # Candidate models
        cands = list(config.candidate_models) if config.candidate_models else self._default_candidate_models()
        if not config.allow_local_models:
            cands = [m for m in cands if not self.model_info.get(m, {}).get("local",   False)]
        if     config.only_local_models:
            cands = [m for m in cands if     self.model_info.get(m, {}).get("local",   False)]
        if     config.only_cleared_models:
            cands = [m for m in cands if     self.model_info.get(m, {}).get("cleared", False)]

        # Provider filter (accepts str or sequence of str)
        if config.provider_filter:
            allowed_models = ({config.provider_filter}
                              if isinstance(config.provider_filter, str)
                              else set(config.provider_filter))
            cands = [m for m in cands if self.model_info.get(m, {}).get("provider") in allowed_models]

        # Model filter (accepts str or sequence of str)
        if config.model_filter:
            allowed_models = ({config.model_filter}
                              if isinstance(config.model_filter, str)
                              else set(config.model_filter))
            cands = [m for m in cands if m in allowed_models]

        # Merge env JSON (if present) into cfg.model_scores; allow both float and {'code','general'} forms
        scores        = dict(config.model_scores)  # copy
        json_path_str = os.getenv("LLM_MODEL_SCORES_JSON")
        if json_path_str:
            try:
                import json
                with open(json_path_str, "r", encoding=DEFAULT_ENCODING) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    scores.update(data)
            except Exception as e:
                logging.warning("Failed to load LLM_MODEL_SCORES_JSON from %s: %s", json_path_str, e)

        hydrated = replace(config, candidate_models=cands, model_scores=scores)

        # If user flipped prefs but left weights at 0, inject reasonable defaults.
        # Price stays at 1.0 unless user overrides.
        if hydrated.prefer_code and hydrated.weight_code_skill == 0.0:
            hydrated = replace(hydrated, weight_code_skill=0.60)
        if hydrated.prefer_low_TTFT and hydrated.weight_TTFT == 0.0:
            hydrated = replace(hydrated, weight_TTFT=0.40)
        if hydrated.prefer_local and hydrated.weight_nonlocal_penalty == 0.0:
            hydrated = replace(hydrated, weight_nonlocal_penalty=0.30)
        # You can optionally bias throughput when TTFT isn't critical
        if hydrated.weight_speed == 0.0 and not hydrated.prefer_low_TTFT and hydrated.speed_floor:
            hydrated = replace(hydrated, weight_speed=0.20)

        return hydrated

    def _filter_candidates(self, candidates: list[ModelInfo],
                           ctx: SelectionContext) -> tuple[list[ModelInfo], dict[str, list[str]]]:
        """Filter by availability, context, and optional locality. Return filtered list and reasons per model name."""
        filtered:     list[ModelInfo] = []
        reasons: dict[str, list[str]] = {}
        for mi in candidates:
            r: list[str] = []
            if not mi.available:
                r.append("provider_not_available")
            if mi.context_window < ctx.min_context_tokens:
                r.append(f"context_too_small({mi.context_window}<{ctx.min_context_tokens})")
            if ctx.require_local and not mi.is_local:
                r.append("requires_local")
            if ctx.require_cleared and not mi.cleared:
                r.append("requires_cleared")
            if mi.name in getattr(self, "_temp_unavailable_models", set()):
                r.append("temporarily_unavailable(model)")
            if mi.provider in getattr(self, "_temp_unavailable_providers", set()):
                r.append("temporarily_unavailable(provider)")
            if r:
                reasons[mi.name] = r
            else:
                filtered.append(mi)
                reasons[mi.name] = []  # << capture "no reasons" for included models
        return filtered, reasons

    def _probe_provider_available(self, provider: str, model: str) -> bool:
        """
        Best-effort, fast, cached probe to avoid DX issues where env var exists
        but auth/network is actually broken.

        Strategy:
        1) Prefer litellm.get_model_info(model) (usually no tokens, very fast).
        2) Fallback to a 1-token completion with a tiny timeout.
        Results cached by (provider, model) for availability_probe_ttl_sec.
        """
        cfg = self._config or LLMConfig()
        if not cfg.availability_probe:
            return True

        import time
        now    = time.time()
        key    = (provider, model)
        ttl    = float(getattr(cfg, "availability_probe_ttl_sec", 60.0) or 60.0)
        cached = self._availability_cache.get(key)
        if cached and (now - cached[1] < ttl):
            return bool(cached[0])

        ok = False
        # Ensure litellm is importable once
        try:
            self._ensure_litellm()
            litellm = self._litellm_mod  # type: ignore
            if litellm is None:
                raise RuntimeError("LiteLLM not available")
            # 1) Zero-cost-ish metadata path
            get_info = getattr(litellm, "get_model_info", None)
            if callable(get_info):
                try:
                    # Many providers will validate creds/host here; keep very short timeout if supported
                    md = get_info(model) or {}
                    # If we got a dict back without raising, consider it OK
                    ok = isinstance(md, dict)
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("availability probe (get_model_info) failed for %s/%s: %s", provider, model, e)
            # 2) Minimal completion (last resort). Guard with tiny timeout & 1 token.
            if not ok and (getattr(cfg, "availability_probe_allow_costly", False) is True):
                try:
                    logging.warning("Availability probe: doing 1-token completion for %s/%s", provider, model)
                    kwargs = dict(
                        model=model,
                        messages=[{"role": "user", "content": "ping"}],
                        temperature=0,
                        max_tokens=1,
                    )
                    # Add transport extras (api_base for ollama/vLLM, etc.)
                    kwargs.update(self._extra_litellm_args_for(model))

                    # Respect a tiny timeout if litellm supports it
                    # (newer versions accept request_timeout; older may ignore)
                    if "request_timeout" not in kwargs:
                        kwargs["request_timeout"] = float(getattr(cfg, "availability_probe_timeout", 1.0) or 1.0)

                    # Call with minimal retries; failures should be fast.
                    comp_with_retries = getattr(litellm, "completion_with_retries", None)
                    if callable(comp_with_retries):
                        comp_with_retries(max_retries=0, **kwargs)
                    else:
                        litellm.completion(**kwargs)
                    ok = True
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("availability probe (1-token completion) failed for %s/%s: %s", provider, model, e)
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("availability probe setup failed for %s/%s: %s", provider, model, e)
            ok = False
        self._availability_cache[key] = (ok, now)
        return ok

    def _is_provider_available(self, provider: str, model: str) -> bool:
        """Check if a model provider is available."""
        entry = self.model_info.get(model, {})
        if entry.get("local") is True:
            runtime = (entry.get("runtime") or "").strip().casefold()
            if runtime == "ollama":
                cfg = self._config or LLMConfig()
                base = (cfg.ollama_base_url or "").rstrip("/")
                if not base:
                    return False
                # Ping /api/tags to ensure server is up and to list pulled models
                data = self._http_get_json(f"{base}/api/tags", timeout=2.0)
                if not isinstance(data, dict):
                    return False
                models = data.get("models", [])
                if not isinstance(models, list):
                    return False
                # Build installed set
                installed = set()
                for m in models:
                    name = (m.get("name") or m.get("model"))
                    if isinstance(name, str):
                        installed.add(name.strip().casefold())
                installed |= {(m.get("digest") or "").strip().casefold()
                              for m in models if isinstance(m, dict)}
                # Derive the tag from the registry key (no extra fields required)
                target = self._derive_ollama_tag(model, runtime)
                if not target:
                    return False  # runtime mismatch or empty tag
                # Match directly; (optional) also accept ':latest' normalization
                if target in installed:
                    return True
                if not target.endswith(":latest") and f"{target}:latest" in installed:
                    return True
                return False
            # ---- vLLM quick probe ----
            if runtime in self._vllm_aliases:
                cfg  = self._config or LLMConfig()
                base = (cfg.vllm_base_url or "").rstrip("/")
                if not base:
                    return False
                # /v1/models is a cheap liveness check for OpenAI-compatible servers
                data = self._http_get_json(f"{base}/v1/models", timeout=2.0)
                if not isinstance(data, dict):
                    return False
                # If it returned a models list, consider vLLM up (we don't require the exact model here)
                return isinstance(data.get("data"), list)
            # Unknown local runtime → not available
            return False
        # Non-local: require env var only if we know one for that provider
        env_var = self._provider_env.get(provider)
        if not env_var:
            return True
        if env_var not in os.environ:
            return False
        # Optional fast probe + cached result to avoid "env set but broken" DX
        try:
            if not self._probe_provider_available(provider, model):
                return False
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Ignoring availability probe failure for %s/%s: %s", provider, model, e)
            # Fail-open to avoid blocking selection entirely on probe hiccups
        return True

    def _build_model_info(self, model: str, cfg: LLMConfig) -> ModelInfo:
        """Build ModelInfo for a given model name, using config and defaults as needed."""
        entry                  = self.model_info.get(model, {})
        provider               = entry.get("provider", "Unknown")
        available              = self._is_provider_available(provider, model)
        in_cost, out_cost, ctx = self._get_model_pricing_and_context(model)

        # ---- pull skills / speed from defaults if present; fallback safely ----
        code_skill = self._score_override(cfg, model, "code")
        if code_skill is None:
            code_skill = float(entry.get("code_skill", _DEFAULT_MODEL_SKILL))
        general_skill = self._score_override(cfg, model, "general")
        if general_skill is None:
            general_skill = float(entry.get("general_skill", _DEFAULT_MODEL_SKILL))
        TTFT       = entry.get("TTFT")
        speed      = entry.get("speed")
        parameters = entry.get("parameters", _DEFAULT_MODEL_PARAMETERS)
        is_local   = bool(entry.get("local",   False))
        cleared    = bool(entry.get("cleared", False))
        runtime    = entry.get("runtime")

        meta: dict[str, Any] = {"pricing_source": "cache_or_litellm_or_fallback"}

        return ModelInfo(
            name=model,
            provider=provider,
            context_window=ctx,
            input_cost_per_token=in_cost,
            output_cost_per_token=out_cost,
            available=available,
            is_local=is_local,
            cleared=cleared,
            parameters=parameters,
            runtime=runtime,
            code_skill=float(code_skill),
            general_skill=float(general_skill),
            TTFT=TTFT,
            speed=speed,
            meta=meta,
        )

    def _ensure_litellm(self) -> None:
        """Ensure LiteLLM is imported and ready to use."""
        if self._litellm_ready:
            return
        try:
            import litellm  # type: ignore
            self._litellm_mod   = litellm
            self._litellm_ready = True
        except ImportError as e:
            my_critical_error(f"LiteLLM is enabled but not installed. 'pip install litellm' Error: {e}")

    def _should_ban_provider_for(self, exc: Exception) -> bool:
        """
        Return True only for likely provider-wide issues. We avoid banning the provider
        for BadRequest/unknown-model style errors so a single bad alias doesn't knock out
        the whole vendor.
        """
        msg = str(exc).casefold()
        # Heuristics for "broad" provider problems
        provider_wide_hints = (
            "rate limit", "ratelimit", "too many requests",
            "service unavailable", "temporarily unavailable",
            "overloaded", "timeout", "timed out",
            "connection error", "api connection", "dns",
            "authentication error", "invalid api key", "unauthorized"
        )
        # Heuristics for "bad request / model not found" -> DO NOT provider-ban
        model_only_hints = (
            "llm provider not provided",    # LiteLLM unknown model/provider mapping
            "invalid request", "bad request",
            "unknown model", "model not found",
            "unsupported model", "unrecognized model"
        )
        if any(h in msg for h in model_only_hints):
            return False
        return any(h in msg for h in provider_wide_hints)

    # --- BEGIN: rate throttling helpers ---

    def _init_rate_db(self, path: Path) -> None:
        """Initialize the SQLite rate log if not already present."""
        import sqlite3
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(os.fspath(path), timeout=5.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requests(
                provider   TEXT NOT NULL,
                model      TEXT NOT NULL,   -- '*' when bucket is provider-wide
                ts         REAL NOT NULL,   -- time.time()
                tokens_in  INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_req_scope ON requests(provider, model, ts)")
        finally:
            conn.close()

    def _get_rate_limits_for(self, model: str) -> dict[str, int | str]:
        """Return the rate limit dict for a given model, with defaults filled in."""
        entry = self.model_info.get(model, {}) or {}
        rl    = entry.get("rate_limit") or {}
        return {
            "scope"  : str(rl.get("scope") or "provider"),   # "provider" | "model"
            "rpm"    : int(rl.get("rpm")    or 0),           # 0 = unlimited
            "tpm_in" : int(rl.get("tpm_in") or 0),
            "tpm_out": int(rl.get("tpm_out") or 0),
            "tpm_sum": int(rl.get("tpm_sum") or 0),          # OPTIONAL blanket cap
        }

    def _effective_scope_bucket(self, provider: str,
                                model: str, scope: str) -> tuple[str, str]:
        """
        Return the (provider, model) tuple to use for rate limiting based on scope.
        If scope=="provider", model is replaced with "*".
        """
        # provider bucket stores model='*'; model bucket stores the model
        return (provider, "*") if scope == "provider" else (provider, model)

    def _estimate_tokens_io(self, messages: list[dict[str, Any]],
                            model: str, max_tokens: int) -> tuple[int, int]:
        """Estimate input/output tokens for rate limiting purposes."""
        try:
            inp = int(self._count_chat_tokens(messages, model))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_count_chat_tokens(messages, model) failed for %s, %s: %s", messages, model, e
            )
            inp = 0
        return inp, int(max_tokens)

    def _throttle_if_needed(self, provider: str, model: str,
                            tokens_in: int, tokens_out: int) -> None:
        """
        Enforce RPM / TPM_IN / TPM_OUT / TPM_SUM over a sliding 60s window
        using a cross-process SQLite log. Inserts a row before sending to
        serialize bursts across agents/processes.
        """
        cfg = self._config or LLMConfig()
        if not cfg.rate_throttle:
            return

        self._init_rate_db(cfg.rate_db_path)

        import time
        import sqlite3
        now     = time.time()
        rl      = self._get_rate_limits_for(model)
        scope   = str(rl["scope"])
        rpm     = int(rl["rpm"])
        tpm_in  = int(rl["tpm_in"])
        tpm_out = int(rl["tpm_out"])
        tpm_sum = int(rl["tpm_sum"])

        # Apply headroom so we don't run into boundary flapping
        head = float(getattr(cfg, "rate_headroom", 1.0) or 1.0)
        if head <= 0.0 or head > 1.0:
            head = 1.0
        rpm     = int(rpm     * head) if rpm     > 0 else 0
        tpm_in  = int(tpm_in  * head) if tpm_in  > 0 else 0
        tpm_out = int(tpm_out * head) if tpm_out > 0 else 0
        tpm_sum = int(tpm_sum * head) if tpm_sum > 0 else 0

        # Unlimited?
        if rpm == 0 and tpm_in == 0 and tpm_out == 0 and tpm_sum == 0:
            return

        bucket_provider, bucket_model = self._effective_scope_bucket(provider, model, scope)
        conn = sqlite3.connect(str(cfg.rate_db_path), timeout=5.0, isolation_level=None)
        try:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")  # lock to make check+insert atomic
            window_start = now - 60.0

            # Scope filter
            where  = "provider=? AND model=? AND ts>=?"
            params = (bucket_provider, bucket_model, window_start)

            need_sleep = 0.0

            # Requests per minute
            if rpm > 0:
                cur.execute(f"SELECT COUNT(*) FROM requests WHERE {where}", params)
                used_req = int(cur.fetchone()[0])
                if used_req >= rpm:
                    # when does the oldest in-window request expire?
                    cur.execute(f"""
                        SELECT MIN(ts) FROM (
                        SELECT ts FROM requests WHERE {where} ORDER BY ts DESC LIMIT ?
                        )
                    """, params + (rpm,))
                    oldest = float(cur.fetchone()[0] or now)
                    need_sleep = max(need_sleep, (oldest + 60.0) - now)

            # Tokens per minute (in/out/sum)
            def _sum(col: str) -> int:
                """Sum a column over the current window, return 0 if no rows."""
                cur.execute(f"SELECT COALESCE(SUM({col}),0) FROM requests WHERE {where}", params)
                v = cur.fetchone()[0]
                return int(v or 0)

            if tpm_in > 0:
                used_in = _sum("tokens_in")
                if used_in + int(tokens_in) > tpm_in:
                    # compute earliest drop time to get under the cap
                    cur.execute(f"""
                        SELECT ts, tokens_in FROM requests
                        WHERE {where} ORDER BY ts ASC
                    """, params)
                    total = used_in
                    cutoff_ts = now
                    for ts, t in cur.fetchall():
                        total -= int(t)
                        if total + int(tokens_in) <= tpm_in:
                            cutoff_ts = float(ts); break
                    need_sleep = max(need_sleep, (cutoff_ts + 60.0) - now)

            if tpm_out > 0:
                used_out = _sum("tokens_out")
                if used_out + int(tokens_out) > tpm_out:
                    cur.execute(f"""
                        SELECT ts, tokens_out FROM requests
                        WHERE {where} ORDER BY ts ASC
                    """, params)
                    total = used_out
                    cutoff_ts = now
                    for ts, t in cur.fetchall():
                        total -= int(t)
                        if total + int(tokens_out) <= tpm_out:
                            cutoff_ts = float(ts); break
                    need_sleep = max(need_sleep, (cutoff_ts + 60.0) - now)

            if tpm_sum > 0:
                used_sum = _sum("(tokens_in + tokens_out)")
                new_sum  = int(tokens_in) + int(tokens_out)
                if used_sum + new_sum > tpm_sum:
                    cur.execute(f"""
                        SELECT ts, (tokens_in + tokens_out) AS t FROM requests
                        WHERE {where} ORDER BY ts ASC
                    """, params)
                    total = used_sum
                    cutoff_ts = now
                    for ts, t in cur.fetchall():
                        total -= int(t)
                        if total + new_sum <= tpm_sum:
                            cutoff_ts = float(ts); break
                    need_sleep = max(need_sleep, (cutoff_ts + 60.0) - now)

            if need_sleep > 0.0:
                cur.execute("COMMIT")   # release lock while sleeping
                import time as _t
                _t.sleep(max(0.0, need_sleep))
                # re-check once after sleep
                self._throttle_if_needed(provider, model, tokens_in, tokens_out)
                return

            # Reserve capacity by recording now (serialize bursts)
            cur.execute(
                "INSERT INTO requests(provider, model, ts, tokens_in, tokens_out) VALUES (?,?,?,?,?)",
                (bucket_provider, bucket_model, now, int(tokens_in), int(tokens_out)),
            )
            cur.execute("COMMIT")
        except Exception as e1:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_throttle_if_needed failed for %s/%s: %s", provider, model, e1
            )
            try:
                cur.execute("ROLLBACK")
            except Exception as e2:
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                    "_throttle_if_needed ROLLBACK failed for %s/%s: %s", provider, model, e2
                )
            # fail-open on throttle store problems
            return
        finally:
            conn.close()

    # --- END: rate throttling helpers ---

    def _http_get_json(self, url: str, timeout: float = 2.0) -> dict[str, Any] | None:
        """Helper to GET a URL and parse JSON, returning None on any failure."""
        from urllib import request, error
        req = request.Request(url, headers={"Accept": "application/json"})
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except (error.URLError, error.HTTPError, TimeoutError):
            return None
        try:
            import json
            return json.loads(raw.decode(DEFAULT_ENCODING))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_http_get_json: JSON parse failed for %s: %s", url, e
            )
            return None

    def _derive_ollama_tag(self, model: str, runtime: str | None) -> str:
        """
        Map your registry key to an Ollama tag without needing extra registry fields.
        Rules:
        - If the model key starts with 'ollama/', strip that prefix and use the rest.
        - Else, if runtime is ollama, assume the key itself is the tag.
        - Normalize to lowercase for matching against /api/tags results.
        """
        r = (runtime or "").strip().casefold()
        tag = model
        if model.startswith("ollama/"):
            tag = model[len("ollama/") :]
        return tag.strip().casefold() if r == "ollama" else ""

    # Pricing/context helpers with caching

    def _get_model_pricing_and_context(self, model: str) -> tuple[float, float, int]:
        """
        Returns (input_cost_per_token, output_cost_per_token, context_window).
        Prices normalized to $/token (not per-1k). Unknown remote prices get a very high sentinel;
        local models always return 0 for both.
        """
        if model in self._pricing_cache:
            return self._pricing_cache[model]

        entry:  dict[str, Any] = self.model_info.get(model, {})
        context:           int = int(entry.get("context", _DEFAULT_MODEL_CONTEXT))
        in_cost:  float | None = None
        out_cost: float | None = None

        # Local models: $0 and registry context
        if entry.get("local") is True:
            in_cost = out_cost = 0.0
            self._pricing_cache[model] = (in_cost, out_cost, context)
            return self._pricing_cache[model]

        # ---- non-local path ----
        try:
            import litellm  # type: ignore
            info_fn = getattr(litellm, "get_model_info", None)
            md: dict[str, Any] = {}
            if callable(info_fn):
                try:
                    md = info_fn(model) or {}
                except Exception as e2:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                        "LiteLLM get_model_info(%s) failed: %s", model, e2
                    )
                    md = {}

            cpit    = self._deep_get(md, ["input_cost_per_token"])
            cppt    = self._deep_get(md, ["output_cost_per_token"])
            cpik    = self._deep_get(md, ["input_cost_per_1k_tokens"])
            cpok    = self._deep_get(md, ["output_cost_per_1k_tokens"])
            max_ctx = self._deep_get(md, ["max_input_tokens"]) or self._deep_get(md, ["max_tokens"])

            if max_ctx:
                try:
                    context = int(max_ctx)
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                        "_get_model_pricing_and_context: context extraction failed for %s: %s", model, e
                    )

            if cpit is not None and cppt is not None:
                in_cost, out_cost = float(cpit), float(cppt)
            elif cpik is not None and cpok is not None:
                in_cost, out_cost = float(cpik) / 1000.0, float(cpok) / 1000.0

            if in_cost is None or out_cost is None:
                cost_map = getattr(litellm, "model_cost", None) or getattr(litellm, "litellm_model_cost", None)
                if isinstance(cost_map, dict) and model in cost_map:
                    row = cost_map[model]
                    if in_cost is None:
                        if "input_cost_per_token" in row:
                            in_cost = float(row["input_cost_per_token"])
                        elif "input_cost_per_1k_tokens" in row:
                            in_cost = float(row["input_cost_per_1k_tokens"]) / 1000.0
                    if out_cost is None:
                        if "output_cost_per_token" in row:
                            out_cost = float(row["output_cost_per_token"])
                        elif "output_cost_per_1k_tokens" in row:
                            out_cost = float(row["output_cost_per_1k_tokens"]) / 1000.0

        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "LiteLLM pricing/context lookup failed for %s: %s", model, e
            )

        if in_cost is None:
            in_cost = 9e9
        if out_cost is None:
            out_cost = 9e9

        self._pricing_cache[model] = (float(in_cost), float(out_cost), int(context))
        return self._pricing_cache[model]

    @staticmethod
    def _deep_get(d: dict[str, Any], path: list[str]) -> Any:
        """Safely get a nested value from a dict."""
        cur: Any = d
        for key in path:
            if not isinstance(cur, dict) or key not in cur:
                return None
            cur = cur[key]
        return cur

    @staticmethod
    def _extract_text_from_openai_like(resp: Any) -> str:
        """Normalize content extraction across dict/object forms."""
        # pydantic-like / attribute
        try:
            return resp.choices[0].message.content  # type: ignore[attr-defined]
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: pydantic-like extraction failed for %s: %s", resp, e
            )
        # dict-like
        try:
            return resp["choices"][0]["message"]["content"]  # type: ignore[index]
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: dict-like extraction failed for %s: %s", resp, e
            )
        # object-like with dict message
        try:
            return resp.choices[0].message["content"]  # type: ignore[index]
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: object-like extraction failed for %s: %s", resp, e
            )
        # completion-style (no chat message wrapper)
        try:
            return resp["choices"][0]["text"]  # type: ignore[index]
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: completion-style extraction failed for %s: %s", resp, e
            )
        try:
            return resp.choices[0].text  # type: ignore[attr-defined]
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: completion-style extraction failed for %s: %s", resp, e
            )
        # Anthropic / segment-style lists
        try:
            segs = resp["choices"][0]["message"]["content"]
            if isinstance(segs, list):
                parts = []
                for s in segs:
                    if isinstance(s, dict):
                        if "text" in s and isinstance(s["text"], str):
                            parts.append(s["text"])
                        elif s.get("type") == "output_text" and isinstance(s.get("content"), str):
                            parts.append(s["content"])
                if parts:
                    return "".join(parts)
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: segment-style extraction failed for %s: %s", resp, e
            )
        # delta fragments (best-effort)
        try:
            d = resp["choices"][0].get("delta")  # type: ignore[index]
            if isinstance(d, dict):
                if "content" in d and isinstance(d["content"], str):
                    return d["content"]
                if "text" in d and isinstance(d["text"], str):
                    return d["text"]
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_extract_text_from_openai_like: delta extraction failed for %s: %s", resp, e
            )
        # As last resort, stringify
        return str(resp)

    def _score_override(self, cfg: LLMConfig, model: str, which: str) -> float | None:
        """
        which: 'code' or 'general'
        Accepts cfg.model_scores[model] as float (code only) or dict with keys 'code'/'general'.
        """
        if not cfg.model_scores:
            return None
        val = cfg.model_scores.get(model)
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val) if which == "code" else None
        if isinstance(val, dict):
            v = val.get(which)
            return float(v) if v is not None else None
        return None

    def _count_chat_tokens(self, messages: list[dict[str, Any]], model: str) -> int:
        """
        Return token count for a chat payload.
        Prefers litellm.token_counter(messages=...) to include role/markup overhead,
        otherwise falls back to self.tokenize() on joined text with a tiny overhead.
        """
        # 1) Prefer litellm's chat-aware counter
        try:
            import importlib
            litellm = getattr(self, "_litellm_mod", None) or importlib.import_module("litellm")  # type: ignore
            token_counter = getattr(litellm, "token_counter", None)
            if callable(token_counter):
                res = token_counter(model=model, messages=messages)
                if isinstance(res, dict):
                    for k in ("input_tokens", "total_tokens", "num_tokens"):
                        v = res.get(k)
                        if isinstance(v, (int, float)):
                            return int(v)
                elif isinstance(res, int):
                    return int(res)
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_count_chat_tokens: litellm.token_counter failed for %s: %s", model, e
            )

        # 2) Fallback: join textual parts and use self.tokenize()
        chunks: list[str] = []
        for m in messages:
            c = m.get("content")
            if isinstance(c, str):
                chunks.append(c)
            elif isinstance(c, list):
                # e.g., Anthropic-style [{"type":"text","text": "..."}]
                for part in c:
                    if isinstance(part, dict) and part.get("type") == "text":
                        t = part.get("text")
                        if isinstance(t, str):
                            chunks.append(t)
        text = "\n".join(chunks)
        tokens = self.tokenize(text, model)

        # 3) Tiny overhead heuristic for chat separators (mostly OpenAI-style ChatML)
        try:
            provider = (self.model_info.get(model, {}) or {}).get("provider", "")
            if isinstance(provider, str) and provider.strip() == "OpenAI":
                 tokens += 4 * len(messages) + 2
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_count_chat_tokens: tiny overhead heuristic failed for %s: %s", model, e
            )
        return int(tokens)

    def tokenize(self, text: str, model: str | None = None) -> int:
        """
        Return the number of tokens in 'text' under the tokenizer best-suited to 'model'.

        Preference order:
        1) Local Ollama runtime -> call /api/tokenize
        2) LiteLLM's token counters (if importable)
        3) tiktoken with OpenAI-family heuristics (o200k_base vs cl100k_base)
        4) Rough heuristic fallback

        Args:
            text: The input text to tokenize.
            model: The model to use for tokenization (optional).

        Returns:
            The number of tokens in the input text.

        Raises:
            ValueError: If tokenization fails.
        """
        if not text:
            return 0

        if model is None:
            model = self._selected.name if self._selected else ""

        entry    = self.model_info.get(model, {})
        runtime  = (entry.get("runtime") or "").strip().casefold()
        is_local = bool(entry.get("local", False))
        provider = (entry.get("provider") or "").strip()

        # --- 1) Local Ollama: ask the server's tokenizer directly ---
        if is_local and runtime == "ollama":
            cfg  = self._config or LLMConfig()
            base = (cfg.ollama_base_url or "").rstrip("/")
            tag  = self._derive_ollama_tag(model, "ollama")
            if base and tag:
                try:
                    import json
                    from urllib import request
                    payload = json.dumps({"model": tag, "prompt": text}).encode(DEFAULT_ENCODING)
                    req = request.Request(f"{base}/api/tokenize",
                                        data=payload,
                                        headers={"Content-Type": "application/json"})
                    with request.urlopen(req, timeout=2.0) as resp:
                        raw = resp.read()
                    data = json.loads(raw.decode(DEFAULT_ENCODING, "replace"))
                    toks = data.get("tokens")
                    if isinstance(toks, list):
                        return len(toks)
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                        "_count_chat_tokens: local ollama tokenizer failed for %s: %s", model, e
                    )
                    # fall through to other methods

        # --- 2) LiteLLM counters (if the library is available) ---
        try:
            import importlib
            litellm = importlib.import_module("litellm")  # type: ignore

            # Preferred: get_num_tokens(model=..., text=...)
            get_num_tokens = getattr(litellm, "get_num_tokens", None)
            if callable(get_num_tokens):
                try:
                    return int(get_num_tokens(model=model, text=text))
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                        "_count_chat_tokens: litellm.get_num_tokens failed for %s: %s", model, e
                    )

            # Fallbacks: token_counter APIs across versions
            token_counter = getattr(litellm, "token_counter", None)
            if token_counter:
                # Some versions accept raw text
                try:
                    out = token_counter(model=model, text=text)
                    if isinstance(out, int):
                        return int(out)
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                        "_count_chat_tokens: litellm.token_counter (raw text) failed for %s: %s", model, e
                    )
                # Others want chat messages, returning a dict
                try:
                    out = token_counter(model=model, messages=[{"role": "user", "content": text}])
                    if isinstance(out, dict):
                        for k in ("input_tokens", "total_tokens", "num_tokens"):
                            v = out.get(k)
                            if isinstance(v, (int, float)):
                                return int(v)
                except Exception as e:
                    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                        "_count_chat_tokens: litellm.token_counter (chat messages) failed for %s: %s", model, e
                    )
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "_count_chat_tokens: litellm.token_counter failed for %s: %s", model, e
            )

        # --- 3) tiktoken heuristics (works well for OpenAI families) ---
        try:
            import tiktoken  # type: ignore

            enc_name = "cl100k_base"
            m        = model.casefold()

            # Use o200k_base for OpenAI's o*/4o/4.1/5 families (long-context tokenization)
            if provider == "OpenAI" or m.startswith(("gpt", "o")):
                if any(x in m for x in ("gpt-4.1", "gpt-4o", "gpt-5", "o1", "o3", "o4", "4.1", "4o")):
                    enc_name = "o200k_base"

            try:
                enc = tiktoken.get_encoding(enc_name)
            except Exception as e:
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                    "tiktoken.get_encoding(%s) failed for %s: %s", enc_name, model, e
                )
                # fallback to cl100k_base if the preferred encoding is unavailable
                enc = tiktoken.get_encoding("cl100k_base")

            return len(enc.encode(text))
        except Exception as e:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
                "tiktoken-based tokenization failed for %s: %s", model, e
            )

        # --- 4) Rough heuristic fallback (no libs / no server tokenizer) ---
        import math
        import re
        s = text if isinstance(text, str) else str(text)
        # Count word-like + punctuation chunks; ensure at least 1
        rough = len(re.findall(r"\w+|[^\s\w]", s, flags=re.UNICODE))
        if rough == 0:
            rough = math.ceil(len(s) / 4.0) or 1
        return int(rough)
