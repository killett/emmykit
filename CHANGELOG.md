# Changelog

All notable changes to `emmykit` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

### Removed (breaking)

- `detect_shell`, `find_shell_rc_file` and `find_additional_alias_files`
  in `emmykit.python_env`, and their re-exports from the top-level
  namespace. They existed to support a script installing itself by
  appending an alias to the user's shell configuration file. `veny`, the
  only known consumer, now ships a console-script entry point
  (`[project.scripts]`) and deleted its alias installer, which left all
  three with no caller. `emmykit.python_env` keeps
  `check_python_version` and `find_preferred_python_version`.
- The five `Options` fields the group used: `shell`, `rc_file`, `alias`,
  `alias_command` and `additional_alias_files`. `alias` and
  `alias_command` had no reader and no writer anywhere in the library —
  they were the payload the consumer's installer filled in. This is a
  softer break than the function removal: `Options` has no `__slots__`,
  so external code can still assign these attributes; only code that
  *reads* the former `None` default without assigning first now raises
  `AttributeError`.
- Drop the 24 stdlib re-exports from the public surface, taking it from
  202 names to 178. In full: the modules `os`, `sys`, `re`, `errno` and
  `logging`; `Path`, `chain`, `Enum`, `ThreadPoolExecutor` and
  `annotations`; `dataclass`, `field` and `replace` from `dataclasses`;
  the eight `typing` names `Any`, `Final`, `Literal`, `Protocol`,
  `TextIO`, `Type`, `TypeAlias` and `overload`; and `Callable`,
  `Iterable` and `Sequence` from `collections.abc`.

  They were preserved in 0.3.0 to match `dir(univ_defs)` exactly, since
  the legacy single-file module imported them at its top level and the
  split had to reproduce its surface name-for-name. That parity is worth
  less than it looked: callers reached the module as `import univ_defs
  as ud`, never by star-import, so the re-exports were only ever
  reachable as `ud.os` / `ek.os` — an access pattern nobody used.

  Two halves with different risk. Removing the corresponding import
  lines from `__init__.py` is what actually makes `ek.os` raise
  `AttributeError`; those imports serve no other purpose, as
  `__init__.py`'s own body never uses them and no submodule imports them
  back out of the package. Removing the 24 `__all__` entries affects
  `from emmykit import *` and nothing else, so it is invisible to
  `import emmykit as ek` callers.

  Surveyed on 2026-08-16 across every known consumer: `veny` (108 `ek.*`
  accesses), `killett/utilities` (16 scripts, 134 `ek.*` accesses across
  25 distinct names), and the five pre-split scripts that became
  `utilities` (35 `ud.*` accesses). Zero uses of any of the 24 in 277
  accesses — no star-import and no `from emmykit import` of a re-exported
  name anywhere. Callers should import these directly from the stdlib.

### Changed

- Public surface: 205 → 202 names.
- `tests/_baseline_signatures.json` updated to match.
- Options JSON written by 0.4.0 still loads. `load_options_from_json`
  restores attributes with a `setattr` loop over whatever keys the file
  holds, so the five removed keys reload as dynamic attributes rather
  than raising. Newly written files simply no longer contain them, since
  `save_options_to_json` serializes `options.__dict__` wholesale.
- Public surface: 202 → 178 names. Combined with the shell/alias removal
  above, 0.5.0 takes the package from 205 to 178 — a deliberate 13%
  reduction, not a packaging accident.
- `python_env` is now documented at layer 2 rather than layer 5. After
  the shell/alias removal its only intra-package import is
  `emmykit._version` (L1). The stale number implied an L4 dependency was
  legal, which is the coupling that removal deleted.
- `tools/generate_readme.py` no longer carries the `STDLIB_REEXPORTS`
  frozenset, which existed solely to keep the 24 out of the README.
- `emmykit.<submodule>` attribute access (e.g. `emmykit.json_io`) is
  intentionally unavailable: `__init__.py` strips submodule attributes
  after import, so reach a submodule with `from emmykit.json_io import X`
  or `import emmykit.json_io as jio` — plain `import emmykit.json_io`
  does not leave `emmykit.json_io` resolvable afterward, since the module
  is already in `sys.modules` and the import system skips re-attaching it
  to the parent package.

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
