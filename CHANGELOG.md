# Changelog

All notable changes to `emmykit` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

### Planned for 0.5.0 (potential breaking changes)

- Drop the 24 stdlib re-exports (`os`, `sys`, `re`, `Path`, `chain`,
  `Enum`, `dataclass`, `field`, `replace`, `annotations`, plus 11
  `typing` names) from the public surface. They were preserved in 0.3.0
  for byte-for-byte parity with the legacy `from univ_defs import *`
  surface, but `import emmykit as ek` users will find `ek.os` /
  `ek.sys` confusing. After that release, callers should import these
  directly from the stdlib. (Deferred from 0.4.0.)

## [0.4.0] - 2026-08-14

Adds a public extension point to the JSON round trip, and removes the
five embedded command-line programs plus the `sys.path` shim.

### Added

- `register_json_type()` / `unregister_json_type()` in
  `emmykit.json_io`, re-exported from the top-level namespace. A
  consuming package can now teach `to_jsonable` / `from_jsonable` about
  its own types without `emmykit` importing that package — the library
  supplies the mechanism, the consumer supplies the knowledge. This also
  reaches `save_options_to_json` / `load_options_from_json`, which call
  the converters internally.

  Previously an unrecognized object fell through to `str(obj)`. That
  fails silently, not loudly: the reloaded file holds a repr string
  where a lookup object should be, and membership tests degrade to
  substring matching (`"ma" in restored` is `True` because the repr
  happens to contain those letters). Nothing raises; the answers are
  just wrong.

  - Dispatch is by `isinstance`, so subclasses of a registered class are
    handled. When two registrations match, the more specific class wins;
    unrelated ties resolve to the most recently registered handler.
  - A registered handler is consulted before every built-in encoder and
    before the `str()` fallback.
  - With `roundtrip=True` the result is `{"__type__": tag, **encode(obj)}`;
    with `roundtrip=False` the bare payload is returned, untagged.
  - The mapping returned by `encode` is itself passed back through the
    converter, so it may contain `Path`, `set`, `datetime`, or another
    registered type. The recursion guard stays in effect across that call.
  - **Encode-only registration** — omitting *both* `tag` and `decode`
    (supplying one without the other raises) serializes the object
    through its encoder but never tags it, in either `roundtrip` mode, so
    it reloads as a plain `dict`. This is a first-class mode, not an
    oversight: some objects can be *described* faithfully but not
    *rebuilt* faithfully, and a readable snapshot plus an honest `dict`
    beats a decoder that fabricates a plausible-but-wrong object.
  - Reusing a registered tag or class raises unless `replace=True`;
    the built-in tags now exposed as `BUILTIN_JSON_TAGS` are rejected
    outright.

- `BUILTIN_JSON_TAGS` — the frozenset of `__type__` tags owned by the
  built-in encoders, so callers can see what a custom tag must avoid.

- `tests/test_json_registry.py` — 42 tests covering round trips, nesting
  inside `dict`/`list`/`set`, `roundtrip=False`, encode-only mode,
  subclass and specificity dispatch, duplicate/built-in tag rejection,
  the recursion guard reached through a registered encoder, and
  unregistration.

### Removed (breaking)

- `PRINTALL_SCRIPT`, `MYDIFF_SCRIPT`, `MYAUDIT_SCRIPT`,
  `MULTIREPLACE_SCRIPT`, and `TREEVIEW_SCRIPT` — the five standalone
  command-line programs carried as string constants in
  `emmykit.embedded_scripts`. They now live as real `.py` files in
  [killett/utilities](https://github.com/killett/utilities), where they
  can be linted, type-checked, tested and imported like ordinary code —
  none of which is possible for a string constant inside the library
  they import.
- `UNIV_DEFS_SYS_PATH_SCRIPT` — deleted outright, not moved. It existed
  because `univ_defs.py` was a loose file that no `sys.path` entry
  pointed at, so a standalone script could not import it. `emmykit` is
  an installed package, so `import emmykit` already works anywhere the
  package is installed; the shim solves a problem packaging has already
  solved. It was also already broken: the constant pointed `sys.path` at
  the *inner* `.../site-packages/emmykit` directory, which would expose
  `json_io`, `constants` and friends as top-level modules and still
  would not make `import emmykit` work.
- `SETUP_CARTOPY_SCRIPT` is unaffected and stays in
  `emmykit.embedded_scripts`.

### Changed

- Public surface: 208 → 205 names (six constants removed, three names
  added).
- `tests/_baseline_signatures.json` updated to match. This is the first
  deliberate divergence from the legacy `dir(univ_defs)` surface.

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
