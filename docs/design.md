# Spec — split `univ_defs.py` into the `emmykit` PyPi package

**Status:** approved (Phase 2 layout signed off 2026-06-05) — ready for `writing-plans`.

**Scope:** restructure the single-file Python module `/workspace/emmykit/univ_defs.py` (9 922 LOC) into a layered, multi-module `emmykit` package suitable for publishing to PyPi. Pure reorganization — preserve every signature, docstring, behaviour, and public symbol verbatim. No logic changes, no renames, no "improvements."

**Non-scope:** publishing to PyPi, adding new features, changing dependencies, touching downstream projects beyond the documented rename `univ_defs → emmykit`.

---

## 1. Constraints locked with user

| Decision                  | Value                                                                                                     |
| ------------------------- | --------------------------------------------------------------------------------------------------------- |
| Package home              | `/workspace/emmykit/` (in-place restructure of the embedded `killett/utilities` repo)                      |
| Layout                    | `src/` layout → `/workspace/emmykit/src/emmykit/`; `pyproject.toml` at `/workspace/emmykit/`               |
| Backward-compat shim      | None. Downstream projects swap the string `univ_defs` → `emmykit` and nothing else.                        |
| Build backend             | `hatchling`                                                                                               |
| Package version           | Bump `__version__` → `"0.3.0"` to mark the restructure                                                     |
| Smoke-test depth          | Signature-diff for every public symbol **plus** invocation of ~5–10 pure helpers vs pre-split baseline    |
| Python floor              | `>=3.12,<3.14` (matches current `PY_VERSION`)                                                              |
| Embedded `.git`           | Fix the stale `worktree = /media/emmy/...` config line before any commit                                   |

---

## 2. Phase 1 analysis — facts

- **Total top-level symbols:** 243 (140 funcs, 15 classes, 73 ann-typed vars, 15 untyped vars).
- **Module-level imports:** 24, all stdlib — `os`, `sys`, `logging`, `pathlib`, `collections.abc`, `itertools`, `typing`, `dataclasses`, `enum`, `concurrent.futures`, `errno`, `re`.
- **In-function (lazy) imports:** 22 third-party packages discovered on full AST sweep (correction logged 2026-06-05). They are NOT triggered by `import emmykit` — every one is imported on demand inside a function body, so a base install has zero third-party requirements. Domains: `datetime` (numpy/pandas/matplotlib/astropy/dateutil), `text` (ftfy/unidecode), `lint` (flake8/autopep8/bugbear), `llm` (litellm/tenacity/tiktoken), `media` (cv2/PIL/imageio_ffmpeg/pulsectl), `files` (atomicwrites/filelock/requests), `inflection` (inflect), `html` (bs4). Exposed via `pyproject.toml` `[project.optional-dependencies]` groups + an `all` umbrella for the Phase-4 test environment.
- **Import-time side effects:** zero. No top-level executable statements outside `def`/`class`/constants/imports.
- **Lazy module-level state:**
  - `_EXECUTOR: ThreadPoolExecutor | None = None` — populated by `_get_executor()` on first call.
  - `_INFLECT_ENGINE: InflectEngine | None = None` — populated by `_get_inflect_engine()` on first call.
  Both are `None` at import time → `import emmykit` is side-effect-free.
- **AST-detected cycles:** one SCC of size 2 → `_make_format_checker ↔ FormatChecker`. **Benign forward reference**: `FormatChecker = _make_format_checker()` is a module-level assignment that runs after `_make_format_checker` is fully defined; the inner reference to `FormatChecker` lives inside a method body resolved lazily at call time. Both stay co-located in `lint.py`. No cross-module break required.
- **Self-loops:** none.
- **Top hubs (most-referenced):**

  | refs | kind   | symbol                    |
  | ---- | ------ | ------------------------- |
  | 39   | func   | `fallback_logging_config` |
  | 28   | func   | `ensure_path`             |
  | 17   | func   | `return_method_name`      |
  | 17   | func   | `ensure_file`             |
  | 14   | class  | `Options`                 |
  | 14   | func   | `safe_is_file`            |
  | 13   | annvar | `DEFAULT_ENCODING`        |
  | 13   | func   | `safe_exists`             |

- **97 leaves** (no internal deps): all ANSI/unicode/extension/embedded-script constants, `Options`, `PlotOptions`, `CheckResult`, `FlushingStreamHandler`, `InflectEngine`, plus standalone funcs (`detect_country`, `my_capitalize`, `my_title_case`, `check_if_command_exists`, `prompt_then_confirm`, `format_date_range`).

---

## 3. Phase 2 layout — 32 modules across 9 layers

Verified by graph analysis: **0 upward references, 0 same-layer cycles, 0 module-graph cycles**. Every dep points strictly downward.

```
emmykit/src/emmykit/
├── __init__.py                   # public-API re-export (curated surface; no longer legacy parity)
│
├── L0 — pure constants ─────────────────────────────────────────────
│   ├── constants.py              # ANSI_*, BACKTICK/quotes/EM_DASH/HORIZONTAL_ELLIPSIS,
│   │                             # DEFAULT_ENCODING, DEFAULT_EXCLUDE_DIRS,
│   │                             # IGNORE_THESE_ERRORS, IGNORED_CODES
│   ├── extensions.py             # all *_EXTENSIONS / *_SET, ALL_KNOWN_*, ARCHIVE_*,
│   │                             # _ARCHIVE_EXTENSIONS_1..4, _ARCHIVE_CATEGORIES,
│   │                             # _ALL_CATEGORIES, TEXT_ENCODINGS, TEXT_ENCODINGS_SET
│   ├── net_targets.py            # IPV4_TARGETS, IPV6_TARGETS, HTTP_PROBES, DNS_TEST_NAMES
│   └── embedded_scripts.py       # SETUP_CARTOPY_SCRIPT string (the five CLI-program
│                                 # strings moved to killett/utilities in 0.4.0;
│                                 # UNIV_DEFS_SYS_PATH_SCRIPT was deleted)
│
├── L1 — leaf utilities ─────────────────────────────────────────────
│   ├── _version.py               # __version__, PY_VERSION
│   ├── options.py                # Options, PlotOptions
│   ├── text_constants.py         # CHARACTERS_TO_SPACE, REPLACE_WITH_SPACE,
│   │                             # QUOTES_TO_DELETE, TRANSLATION_TABLE
│   ├── numeric_helpers.py        # is_float, seconds_in_unit, _UNIT_SECONDS
│   ├── paths_ensure.py           # ensure_path, _IS_PY_3_13
│   ├── inflect_utils.py          # InflectEngine, _INFLECT_ENGINE, _get_inflect_engine, my_plural
│   └── logging_utils.py          # FlushingStreamHandler, MaxLevelFilter, MemoryHandler,
│                                 # fallback_logging_config, configure_logging,
│                                 # print_all_errors, return_method_name
│
├── L2 — safe filesystem + interpreter discovery ────────────────────
│   ├── safe_paths.py             # _is_file, _is_dir,
│   │                             # safe_exists, safe_is_file, safe_is_dir,
│   │                             # safe_stat, safe_size, safe_mtime, safe_ctime,
│   │                             # ensure_file, ensure_dir
│   ├── file_io.py                # my_atomic_write
│   └── python_env.py             # check_python_version, find_preferred_python_version
│
├── L3 — process / critical IO ──────────────────────────────────────
│   └── io_subprocess.py          # MyPopenResult, my_fopen, my_popen, my_critical_error
│
├── L4 — pure utility domains ───────────────────────────────────────
│   ├── prompts.py                # prompt_then_confirm, prompt_then_choose
│   ├── introspection.py          # show_function_source, load_ast_var,
│   │                             # _sanitize_text_signature, _builtin_stub,
│   │                             # normalize_to_dict, compile_code, if_filepath_then_read
│   ├── humanize.py               # human_bytesize, sci_exp, round_out
│   ├── datetime_utils.py         # parse_datetime, parse_timezone, AdaptiveDateFormatter,
│   │                             # adaptive_date_labels, decimal_year_to_datetime,
│   │                             # format_date_range, human_timespan, extract_timestamp,
│   │                             # Precision, ADAPTIVE_FORMAT_LEVELS, AnyDateTimeType,
│   │                             # _TIMESTAMP_PATTERN_RE, _TZ_ABBREV_TO_ZONE, _TZ_OFFSET_RE,
│   │                             # _JD_MJD_SIMPLE_RE, _JD_MJD_CAPTURE_RE, _OFFSET_IN_STR_RE,
│   │                             # _JD_UNIX_EPOCH, _parse_iso, _should_convert,
│   │                             # _finalize_datetime, _normalize_to_datetime
│   ├── json_io.py                # to_jsonable, _to_jsonable, from_jsonable, _coerce_log_mode,
│   │                             # save_options_to_json, load_options_from_json
│   └── diff_view.py              # highlight_changes, _vis_trailing_ws, _vis_all_ws,
│                                 # my_diff, diff_and_confirm, is_python_script
│
├── L5 — composed domains ───────────────────────────────────────────
│   ├── text.py                   # decode_utf8, decode_cp1252, contains_mojibake,
│   │                             # fix_text, fix_mojibake, ensure_utf8_meta,
│   │                             # my_capitalize, my_title_case, normalize_for_search
│   ├── hosts.py                  # get_hostname_socket/platform/os_uname/
│   │                             # subprocess_hostname/subprocess_scutil,
│   │                             # get_computer_name, analyze_computer_name_results,
│   │                             # COMPUTER_NAME, NASA_COMPUTER_NAME_PREFIXES,
│   │                             # NASA_CASEFOLDED_COMPUTER_NAME_PREFIXES, IS_NASA_COMPUTER
│   ├── network.py                # CheckResult, _check_once, is_internet_available,
│   │                             # _dns_resolve, _any_dns_name_resolves,
│   │                             # _http_probe, _http_probe_with_cap,
│   │                             # _http_meets_expectations, _looks_like_captive,
│   │                             # _build_http_opener,
│   │                             # _tcp_connect, _run_tcp_checks_with_pool,
│   │                             # _EXECUTOR, _get_executor, _call_with_timeout,
│   │                             # _should_use_proc_cap, _advisory_user_proc_limit_cap,
│   │                             # _effective_workers
│   └── files.py                  # download_file, query_free_space, verify_script,
│                                 # filename_format, calculate_checksum
│
├── L6 — code-quality tools ─────────────────────────────────────────
│   └── lint.py                   # _make_format_checker, FormatChecker  ← benign cycle stays here
│                                 # check_python_formatting, run_flake8, _gather_flake8_issues,
│                                 # _gather_via_cli, _gather_via_app, get_autopep8_fixable_codes,
│                                 # ask_and_autopep8, ask_and_replace, _validate_glob_pattern,
│                                 # _resolve_dir, _collect_files, multireplace,
│                                 # interactive_flake8, run_mypy
│
├── L7 — high-level workflows ───────────────────────────────────────
│   ├── treeview.py               # treeview_new_files
│   ├── docker_utils.py           # ensure_docker_installed, ensure_daemon_running,
│   │                             # ensure_image_built, run_with_docker_fixes
│   ├── system.py                 # check_if_command_exists, open_terminal_and_run_command,
│   │                             # get_effective_free_memory, kill_process, is_process_running,
│   │                             # start_only_one_instance, open_filemanager_with_dirs,
│   │                             # detect_country
│   ├── media.py                  # open_playlist_in_VLC, open_dir_in_VLC, open_in_vlc,
│   │                             # find_ffmpeg, ensure_even_dimensions,
│   │                             # get_video_duration_seconds,
│   │                             # extract_and_concatenate_segments, set_system_volume
│   └── html_files.py             # remove_prefix_from_filename, remove_prefix_from_html_title,
│                                 # combine_html_files
│
└── L8 — LLM ────────────────────────────────────────────────────────
    └── llm.py                    # LLMConfig, ModelInfo,
                                  # _DEFAULT_MODEL_SKILL, _DEFAULT_MODEL_CONTEXT,
                                  # _DEFAULT_MODEL_PARAMETERS, _DEFAULT_MODEL_RPM,
                                  # _DEFAULT_MODEL_TPM_IN, _DEFAULT_MODEL_TPM_OUT,
                                  # SelectionStrategy, SelectionContext, StrategyFn, LLMs
```

### 3.1 One-line rationale per module

| Layer | Module               | Rationale                                                                                                              |
| ----- | -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| 0     | `constants`          | ANSI escape codes + unicode punctuation + defaults — pure data, used everywhere.                                       |
| 0     | `extensions`         | All file-extension/encoding lists & sets — pure data, large but cohesive.                                              |
| 0     | `net_targets`        | DNS / HTTP / IPv4 / IPv6 probe targets — pure data for `network.py`.                                                   |
| 0     | `embedded_scripts`   | Big multi-kilobyte script strings — kept separate to keep other modules readable.                                      |
| 1     | `_version`           | Single source of truth for `__version__` + `PY_VERSION`.                                                               |
| 1     | `options`            | Plain dataclass-style holders with zero internal deps.                                                                 |
| 1     | `text_constants`     | Tiny translation tables used by `text.py`.                                                                             |
| 1     | `numeric_helpers`    | `is_float`/`seconds_in_unit`/`_UNIT_SECONDS` — shared by `humanize` and `datetime_utils`.                              |
| 1     | `paths_ensure`       | `ensure_path` is the pure pathlib-normalize leaf used by `logging_utils` and everywhere above.                          |
| 1     | `inflect_utils`      | Self-contained singularize/pluralize layer with a lazy engine singleton.                                               |
| 1     | `logging_utils`      | Custom log handlers + `configure_logging` + `return_method_name` — the introspective helper logs via the same handlers. |
| 2     | `safe_paths`         | Exception-swallowing filesystem queries + `ensure_file`/`ensure_dir` which compose `safe_*`.                            |
| 2     | `file_io`            | `my_atomic_write` — single primitive needed by both text fixers and lint workflows.                                    |
| 2     | `python_env`         | Python interpreter discovery (preferred version + version check).                                                      |
| 3     | `io_subprocess`      | `my_fopen` / `my_popen` / `my_critical_error` — subprocess + critical-error wrappers.                                  |
| 4     | `prompts`            | Interactive Y/N + choose helpers.                                                                                       |
| 4     | `introspection`      | Source inspection + AST helpers.                                                                                       |
| 4     | `humanize`           | `human_bytesize` / `sci_exp` / `round_out` — display-side numeric formatters.                                          |
| 4     | `datetime_utils`     | All datetime parsing, formatting, adaptive labels, JD/MJD support.                                                     |
| 4     | `json_io`            | `to_jsonable`/`from_jsonable` + Options JSON load/save.                                                                |
| 4     | `diff_view`          | Visible-whitespace highlighting and `my_diff` invocations — placed low so `text`, `files`, and `lint` can reuse.        |
| 5     | `text`               | Mojibake fixers + casing helpers + normalize-for-search.                                                                |
| 5     | `hosts`              | Hostname/computer-name lookups (5 strategies) + NASA-prefix detection.                                                 |
| 5     | `network`            | Internet-availability framework (DNS/HTTP/TCP probes, captive-portal detection, executor pool).                        |
| 5     | `files`              | Download / free space / atomic-verify / filename helpers.                                                              |
| 6     | `lint`               | flake8/autopep8/mypy interactive runners + `multireplace` (the regex-driven replace tool that shares lint internals).  |
| 7     | `treeview`           | Recursive directory listing with extension grouping.                                                                    |
| 7     | `docker_utils`       | Docker daemon + image lifecycle helpers.                                                                                |
| 7     | `system`             | Misc OS-shell helpers (kill_process, country detection, file-manager launchers).                                       |
| 7     | `media`              | VLC + ffmpeg + volume helpers.                                                                                          |
| 7     | `html_files`         | HTML title + filename munging + concatenation.                                                                          |
| 8     | `llm`                | Large `LLMs` class (2 016 LOC) + its config dataclasses & selection strategies.                                        |

### 3.2 Cycle / cross-module violation resolutions

| Original conflict                                          | Resolution                                                                                                 |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `_make_format_checker ↔ FormatChecker`                     | Benign forward-ref; both stay in `lint.py`. No restructuring.                                              |
| `return_method_name → fallback_logging_config`             | Co-located in `logging_utils` (L1).                                                                         |
| `configure_logging → ensure_path`                          | `ensure_path` lives in `paths_ensure` (L1, loaded first); `logging_utils` (L1) imports it.                  |
| `parse_datetime → is_float`, `seconds_in_unit`             | Both moved into `numeric_helpers` (L1) below `datetime_utils` (L4).                                        |
| `human_timespan → my_plural`                               | `inflect_utils` (L1) is below `datetime_utils` (L4).                                                       |
| `fix_text` / `fix_mojibake → my_diff`, `my_atomic_write`   | `diff_view` (L4) and `file_io.my_atomic_write` (L2) sit below `text` (L5).                                 |
| `ask_and_autopep8` / `ask_and_replace → diff_and_confirm`  | `diff_view` (L4) below `lint` (L6).                                                                        |
| `verify_script → my_diff`                                  | `diff_view` (L4) below `files` (L5).                                                                        |
| `ensure_file` / `ensure_dir → safe_*`                      | Moved into `safe_paths` (L2) since they're built atop the `safe_*` helpers.                                |

**No `if TYPE_CHECKING`, no in-function imports, no `__getattr__`-based lazy modules.** Straight top-of-file imports throughout.

---

## 4. Phase 3 — execution rules (final implementation plan will live in a separate plan doc produced by `writing-plans`)

1. **Pre-flight (no code moves yet).**
   - Fix `/workspace/emmykit/.git/config`: delete the stale `worktree = /media/emmy/G/Documents/Programming/python` line. Confirm `git status` works.
   - Generate baseline snapshot of every public symbol's `inspect.signature` plus `__all__` (computed as `[n for n in dir(univ_defs) if not n.startswith('_')]`) and save to `/workspace/emmykit/tests/_baseline_signatures.json`. Commit baseline.
2. **Scaffold the package.**
   - Create `/workspace/emmykit/pyproject.toml` (hatchling, version `0.3.0`, Python `>=3.12,<3.14`, no runtime deps).
   - Create `/workspace/emmykit/src/emmykit/__init__.py` (initially empty placeholder).
   - Add `/workspace/emmykit/README.md` (one paragraph + install + `from emmykit import …` example).
   - Keep the existing `univ_defs.py` untouched during this step.
3. **Move code layer by layer, lowest first** (L0 → L8). After each layer:
   - Add `from emmykit.<module> import *` lines into `__init__.py` so the public API is rebuilt as we go.
   - Each commit is one module's move (e.g. `refactor: extract emmykit.constants from univ_defs`). Commit message lists every moved symbol.
   - Run `python -c "import emmykit; import univ_defs"` after each commit to confirm both still import successfully (until univ_defs is deleted in the final step).
4. **Final step.** Once every symbol is moved, delete `/workspace/emmykit/univ_defs.py`. Confirm `from emmykit import *` exposes exactly the baseline set.
5. **Preservation rules.** Function bodies, decorators, docstrings, type hints, blank-line layout, and inline comments copy verbatim. No reformatting. No renames. No "improvements." If a comment references `univ_defs` by name, leave the reference (it is documentation about the historical context); only swap the import string in downstream projects, not in the source.

---

## 5. Phase 4 — verification

1. **Public-symbol baseline.**
   - `python -c "import univ_defs; print(sorted(n for n in dir(univ_defs) if not n.startswith('_')))"` → save as `baseline_public_symbols.json`.
   - `python -c "import inspect, univ_defs; print({n: str(inspect.signature(getattr(univ_defs, n))) for n in dir(univ_defs) if callable(getattr(univ_defs, n)) and not n.startswith('_')})"` → save as `baseline_signatures.json`.
2. **Post-split equality test (`tests/test_public_api.py`).**
   - Asserts `sorted(n for n in dir(emmykit) if not n.startswith('_'))` equals the baseline list.
   - Asserts `inspect.signature(getattr(emmykit, n))` equals the baseline string for every callable name.
   - Asserts `emmykit.__version__ == "0.3.0"`.
3. **Submodule import test.** For every module in §3, `from emmykit.<module> import *` must succeed.
4. **Pure-helper smoke test (`tests/test_pure_helpers.py`).** Call ~5–10 pure functions with hand-picked inputs and compare against pre-recorded outputs captured from the original `univ_defs.py`. Candidates:
   - `human_bytesize(1024**2)` → `'1.00 MiB'` (or whatever the original returns)
   - `sci_exp(12345.6, 2)`
   - `round_out(3.14159, 3)`
   - `is_float("12.3")` / `is_float("nope")`
   - `seconds_in_unit("minute")`
   - `my_capitalize("hello world")`
   - `my_title_case("the lord of the rings")`
   - `seconds_in_unit("hour")`
   - `parse_datetime("2026-06-05T12:34:56Z")` (compare `.isoformat()`)
   - `human_timespan(3725)` (`"1 hour, 2 minutes, 5 seconds"` or similar)

   Exact expected values are captured *before* Phase 3 starts by running the original `univ_defs.py`. The test then asserts byte-equal outputs after the split.
5. **Reporting.** Phase 4 final note records:
   - Any symbol that resisted clean separation (we expect none).
   - Any name collisions inside `__init__.py` (none expected — global name space is unique by construction in a single source file).
   - Module-graph diagram (drop into `docs/`).

---

## 6. Out-of-scope clarifications

- **Renames inside `univ_defs.py`.** None. Even mis-spelled or oddly-shaped names stay as-is.
- **Style fixes.** None. `IGNORED_CODES` exists for a reason; don't fight it.
- **Removing dead code.** None. If a symbol is unused internally it may still be public API.
- **Switching to `numpy`/`pandas`/etc.** Not relevant — package is pure-stdlib and stays pure-stdlib.
- **Publishing to PyPi / TestPyPi.** Out of scope. Producing a wheel locally (`hatchling build`) is a verification convenience, not a release step.

---

## 7. Open items deferred to plan-writing

These are recorded so `writing-plans` can ask them or pin them:

- **LICENSE.** The embedded repo already includes Apache 2.0 (commit `890c2cc`); confirm the LICENSE file is copied/kept at `/workspace/emmykit/LICENSE` and referenced from `pyproject.toml`.
- **README content.** One paragraph project description, install (`pip install emmykit`), three-line import example. Plan will draft text.
- **`tests/` location.** `/workspace/emmykit/tests/` (top-level, sibling of `src/`), default hatchling layout.
- **Commit boundary granularity.** One commit per module move (≈30 commits) versus one commit per layer (≈9 commits). Plan to default to per-module unless user requests otherwise.

---

## 8. Risks tracked

| Risk                                                                  | Mitigation                                                                                                                                                            |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AST-detected `_make_format_checker ↔ FormatChecker` cycle is real      | Verified by reading the source: the inner reference is inside a lazy method body. If runtime import surfaces a `NameError`, move `FormatChecker = …` to bottom of `lint.py`. |
| A "pure" helper turns out to read the env / call `time.time()`         | Smoke-test inputs picked from a deterministic subset; `time.time()`-using helpers omitted. Document the exclusion in the test.                                        |
| The 9 922-LOC file actually contains a buried module-level call we missed | AST analysis returned `module-level non-import statements: 0`. If a buried call appears during the move, halt and re-run the AST sweep.                                |
| Embedded `/workspace/emmykit/.git` worktree config issue              | Pre-flight step explicitly fixes it before any commit attempt.                                                                                                        |
| Downstream projects also import `_`-prefixed names                    | Stated explicitly out of scope: only non-`_` names are guaranteed public. Document this in `README.md`.                                                                |

---

**End of spec.** Hand off to `writing-plans` for the executable per-step plan.
