# Hygiene notes

A running log of smells that hygiene passes looked at and **deliberately kept**,
with the reason, so later passes don't argue about them again. Locations are
`module.function`, not line numbers, which drift.

## Pass of 2026-10-18/19 (whole repo)

### Kept because the design asks for it

- **No linter or formatter config.** The owner's decision; not to be re-suggested.
- **Code layout from the `univ_defs.py` split**: aligned assignments, one-line
  `if …: logging.debug(...)`, "extracted from univ_defs.py" module docstrings,
  "for mypy" asserts. docs/design.md §4.5 and §6 asked for a verbatim copy;
  `constants.IGNORED_CODES` explains the style codes it tolerates.
- **`if logging.getLogger().isEnabledFor(logging.DEBUG):` guards.** Not
  redundant: an unguarded `logging.debug()` installs a stderr handler on the
  root logger. Moving to `getLogger(__name__)` would be a library-wide decision.
- **`fallback_logging_config()` at the top of public functions.** Its documented
  purpose (`logging_utils.fallback_logging_config`). The exception is code that
  runs at import, which must not configure logging (`hosts.get_computer_name`
  with `rawlog=True`, tested in `tests/test_hosts.py`).
- **Third-party imports inside function bodies.** A bare install is
  stdlib-only (docs/design.md §2, `[project.optional-dependencies]`).
- **`lint._make_format_checker` building `_FormatChecker` at import.** A benign
  forward reference (docs/design.md §2, §3.2).
- **`palette` missing from `__init__`'s submodule scrub list**, and
  **`options` importing the private `palette._mix`**: both explained where they
  occur.
- **"32 submodules" in the README and in `__init__`.** Correct: 32 public
  modules plus `_version`. (The audit miscounted it as 33.)

### Kept because they still do a job

- **`json_io._coerce_log_mode`**: lets Options JSON written before 0.5.0 load.
- **`safe_paths._is_file` / `_is_dir` / `_IS_PY_3_13`**: needed while the
  floor is Python 3.12; drop together once it is 3.13.
- **`embedded_scripts.SETUP_CARTOPY_SCRIPT`**: the module comment says why it
  outlived the other script constants in 0.4.0.
- **`humanize.human_bytesize`'s legacy quirks** and its `promote` /
  `clamp_non_finite` flags: pinned by `tests/_baseline_human_bytesize.json`.
- **`AdaptiveDateFormatter`'s class swap in `__init__`, `__reduce__` /
  `_new_without_init`, and `_FormatterBase = object` at run time**: see
  CHANGELOG 0.6.1–0.6.3 and the inline comments.
- **`datetime_utils._TZ_ABBREV_TO_ZONE` choosing one zone for CST and IST**:
  flagged in comments there. **`numeric_helpers._UNIT_SECONDS` leaving out
  Ms/Ps/Zs/Ys**: casefold collisions, explained there.
- **The five near-identical `except` blocks in `hosts.get_hostname_*`**: a
  shared helper would change the logged method name, because
  `return_method_name()` reads its caller's frame.
- **Broad `except Exception` blocks that carry an intent comment**
  (`io_subprocess.my_popen`, `io_subprocess.my_fopen`,
  `hosts.get_computer_name`, `treeview`, `text`, `llm`, `media`).
- **`llm`'s overridable hooks** (`_default_candidate_models`,
  `_extra_litellm_args_for`, `_after_selection`) and the `alternative_model`
  overloads.
- **`lint.run_mypy`'s unused `options` parameter**: kept for a uniform
  signature, as its docstring says.
- **Tests:** JSON tag literals written out in `tests/test_json_registry.py`
  (they pin the contract independently of the module); tests of the private
  `palette._shift_to_contrast` and `humanize._resolve_as_unit` (the guards
  can't be reached through the shipped palettes); `eval(raw)` in
  `tests/test_humanize._decode_value` (only evaluates numeric literals the
  test file wrote, as its comment says).

### Left for now: not clearly an improvement, or tied to an open bug

- **The five recursion guards in `json_io._to_jsonable` /
  `_encode_registered`.** One helper would have to pass the recursion marker
  through the tuple and set branches' post-processing, which reads worse than
  the explicit copies.
- **`lint._gather_via_cli` / `_gather_via_app` building the bugbear arguments
  twice**, plus a third form in `run_flake8`. `_gather_via_app` sits behind a
  fallback that can't trigger, and a failing flake8 is silently read as no
  issues; fix those together.
- **`safe_paths`' suppressed-errno debug log, written four times.** A helper
  must keep `return_method_name()` pointing at the right frame, and `safe_paths`
  is a third covered by tests.
- **`network._check_once`'s 0.25 s budget floor and 0.3 s HTTP cutoff.** They
  are why the HTTP probe never runs once the TCP phase has used the budget (an
  open bug); rename them when that is fixed.
- **`llm`'s `getattr(cfg, …, default)` calls, the `"multi_objective"` literal
  and the `9e9` unknown-price placeholder.** The placeholder is an open bug
  (it flips the cheapest-model choice), and the rest is best cleaned up with
  `llm`'s other open bugs.
- **`introspection.show_function_source`'s `globals().get("my_atomic_write")`
  branch**, dead since the split. Now that `my_atomic_write` works, restoring
  the atomic append (an import from `file_io`) would change behaviour, so it
  awaits a decision rather than deletion.
- **Private entries in `tools/_layout.json`.** Only public names are read now;
  the private ones served the deleted `tools/extract_symbols.py`. Deriving the
  whole map from the module ASTs would retire the file.
