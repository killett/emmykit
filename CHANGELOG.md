# Changelog

All notable changes to `emmykit` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

### Planned for 0.4.0 (potential breaking changes)

- Drop the 24 stdlib re-exports (`os`, `sys`, `re`, `Path`, `chain`,
  `Enum`, `dataclass`, `field`, `replace`, `annotations`, plus 11
  `typing` names) from the public surface. They were preserved in 0.3.0
  for byte-for-byte parity with the legacy `from univ_defs import *`
  surface, but `import emmykit as ek` users will find `ek.os` /
  `ek.sys` confusing. After 0.4.0, callers should import these directly
  from the stdlib.

## [0.3.0] - 2026-06-05

First public release. Splits the historical single-file `univ_defs.py`
module (9 922 LOC, 243 top-level symbols) into a 32-module layered
package.

### Added

- `pyproject.toml` with hatchling build backend, Python ≥3.12,<3.14.
- `[project.optional-dependencies]` covering 22 lazily-imported
  third-party packages, grouped into 8 domains (`datetime`, `text`,
  `lint`, `llm`, `media`, `files`, `inflection`, `html`) plus an `all`
  umbrella.
- Apache-2.0 LICENSE.
- 208-symbol `__all__` matching the legacy `dir(univ_defs)` surface.
- `tests/test_public_api.py` — pins the post-split surface against
  `tests/_baseline_signatures.json` (name set, callable signatures,
  submodule importability).
- `tests/test_pure_helpers.py` — parametrized byte-comparison of ~30
  pre-recorded pure-helper outputs against `tests/_baseline_pure_helpers.json`.
- `tools/extract_symbols.py` — AST-based extractor used to produce
  each module's source verbatim from `univ_defs.py`; handles decorators
  and auto-emits `typing` / `collections.abc` imports.

### Changed

- Package now exposes 32 submodules across 9 dependency layers:
  - **L0**: `constants`, `extensions`, `net_targets`, `embedded_scripts`
  - **L1**: `_version`, `paths_ensure`, `options`, `text_constants`,
    `numeric_helpers`, `inflect_utils`, `logging_utils`
  - **L2**: `safe_paths`, `file_io`
  - **L3**: `io_subprocess`
  - **L4**: `prompts`, `introspection`, `humanize`, `datetime_utils`,
    `json_io`, `diff_view`
  - **L5**: `text`, `hosts`, `network`, `python_env`, `files`
  - **L6**: `lint`
  - **L7**: `treeview`, `docker_utils`, `system`, `media`, `html_files`
  - **L8**: `llm`
- `import emmykit` is side-effect-free; every third-party dep is
  imported lazily inside the function that uses it.
- Module-level annotations now compile cleanly under
  `typing.get_type_hints()` (Task-2 review caught missing `Final`/`Any`
  imports masked by PEP 563).

### Removed

- The flat `univ_defs.py` module (replaced by the layered package).

### Migration

For consumers of the legacy `univ_defs.py`:

```python
# before
import univ_defs
from univ_defs import parse_datetime, Options, LLMs

# after
import emmykit as ek
from emmykit import parse_datetime, Options, LLMs
```

A single string replacement (`univ_defs` → `emmykit`) covers every
documented import path. Underscore-prefixed names are not part of the
public API and may break across releases.
