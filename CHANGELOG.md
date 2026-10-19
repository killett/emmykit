# Changelog

All notable changes to `emmykit` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/).

## [Unreleased]

### Fixed

- The README's table of contents did nothing when clicked on PyPI. PyPI
  points every in-page link at an id starting with `user-content-` but
  keeps the README's own anchors as written, so all 191 links missed.
  Each anchor now also carries the `user-content-` form, and the links
  work on PyPI, GitHub and in local previews.
- The README's `palette` link opened the `Palette` class, because both
  names had the anchor `palette`. The function's anchor is now
  `palette-1`; all other anchors are unchanged.
- `my_atomic_write` failed on every call. Current filelock rejects the
  default `lock_timeout=None`, and `atomicwrites` refused both append
  mode and an option the function passed it. It now uses only the
  standard library: the new contents go to a temp file in the same folder,
  are flushed to disk and are renamed over the target. An existing file
  keeps its permissions, append mode writes the old contents and the new
  data together, and `lock_timeout=None` waits for the lock indefinitely,
  as documented. Writing through a symlink updates the file it points to
  and keeps the link. The lock file now lives in
  `<cache>/emmykit/locks/`, named by a hash of the target's path, instead
  of beside the target: current filelock versions leave lock files in
  place, deliberately, because deleting them can let two processes hold
  the lock at once (filelock issue #574).
- `fix_mojibake` could lose the file it was fixing. With
  `make_backup=True`, the default, it renamed the original to the backup
  name before writing the fixed text, so when that write failed (and it
  always did, see `my_atomic_write` above) only the `.bak` file remained.
  The backup is now a copy, and the original stays in place until the
  fixed text replaces it.
- `LLMs` model selection raised `NameError: name 'replace' is not
  defined` on every call to `apply_config`, `refresh_selection`,
  `alternative_model` and (once a config was applied) `get_config`, and
  so on every failover inside `send_prompt`. The 0.3.0 split had dropped
  `replace` from `llm.py`'s `dataclasses` import.
- `import emmykit` configured the root logger (level INFO, format
  `%(message)s`) while computing `COMPUTER_NAME`, so a program's own
  `logging.basicConfig()` after the import silently did nothing.
  `get_computer_name(rawlog=True)` and
  `analyze_computer_name_results(..., rawlog=True)`, which log nothing,
  now leave logging unconfigured too; with `rawlog=False` they behave as
  before.
- `round_out` bumped some values that already had the requested number of
  significant figures: `round_out(1.11, 3)` gave `1.12`, because the
  float 1.11 is really 1.1100000000000001 (30 of the 900 three-figure
  values in [1, 10) were affected). Results also carried binary tails
  (`round_out(2.3, 2)` gave `2.3000000000000003`), and values below
  `10**-max_digits` came back unconverted, e.g. `0` as an `int`. It now
  rounds the number as written, always returns a plain `float`, and no
  longer needs numpy.
- `kill_process` crashed after every successful kill: `pgrep` exits with
  status 1 when nothing matches, and the re-check raised
  `CalledProcessError` instead of printing "process successfully killed".
  When no process matched in the first place it raised `ValueError`
  instead of printing "No … process found." and returning. Both now
  behave as written; a real `pgrep` failure still raises `ValueError`.
- `set_system_volume` raised `UnboundLocalError` instead of falling back
  to `pactl` when pulsectl was installed but couldn't load, for example
  without libpulse. It now logs a warning and uses `pactl`.
- `my_popen` hung forever when a command printed bytes that aren't valid
  in the locale's encoding and then more than a pipe's worth of output:
  the reader thread died on the decode error, the pipe filled, and the
  command blocked. Undecodable bytes now come through as U+FFFD (�).
- `parse_datetime` decided between converting to the target timezone
  and attaching it by looking at the input text, not at what was parsed.
  A time with a named zone was given the target zone instead of being
  converted: `"Tue, 25 Jun 2025 14:00:00 EST"` came back as 14:00 UTC
  (correct: 19:00 UTC), and `"2025-06-25 14:00:00 UTC"` with New York
  as 14:00 New York time. A trailing year such as `"18-Oct-2002"` was
  mistaken for a UTC offset, and the result then depended on the
  machine's local timezone. Now anything that parses with a zone or
  offset is converted and anything without one is attached, and a naive
  value that `should_convert=True` forces to convert is read as UTC
  rather than as local time.
- `parse_datetime` shifted years into the target timezone: `"2002"` or
  `2002.0` with New York gave 19:00 on 31 December 2001, although the
  docstring says midnight on 1 January and `"2002-10"` already gave
  midnight. Years and decimal years are now read in the target timezone,
  so `"2002"` is midnight on 1 January there and 2002.5 is noon on 2 July
  there; results in UTC, the default, are unchanged. An epoch written as
  a year (`"days since 2000"`) follows suit.
- `parse_datetime` cut a `pandas.Timestamp` to midnight and dropped its
  timezone, the docstring's own example included, because a Timestamp
  is also a `datetime.date`. It now keeps its time and zone.
- `parse_datetime` raised `UnboundLocalError` instead of the intended
  `ValueError` when the epoch in a format string such as
  `"days since notadate"` couldn't be parsed.
- `parse_datetime` with `timezone="Naive"` turned a `numpy.datetime64`
  into the machine's local wall time, so the same call gave different
  answers on different hosts. It now gives the datetime64's own UTC wall
  time.
- `is_internet_available` reported no connection behind a proxy that
  drops direct TCP: the TCP step used up the attempt's whole time budget,
  so the HTTP probe, which works through proxies, never ran. TCP, DNS and
  HTTP now each get `timeout_per_step`, as the name says, so an attempt
  with nothing reachable can take up to about three times that long.
- `LLMs.send_prompt` could wait forever when one request on its own needed
  more tokens than 90% of the model's per-minute cap (for example a
  prompt of over 27,000 tokens to gpt-4.1): the rate throttle slept 60
  seconds at a time waiting for room that could never exist. Such a
  request now waits only until no other request is in the minute window,
  then goes out with a warning.
- `ensure_file`'s messages for an empty file read "BLAHFile is empty" (the
  `raise_on_empty` error) and "BLAH2File is empty" (the warning), debugging
  leftovers seen by every function that checks its input file. Both now
  read "File is empty: <path>".
- `check_python_formatting` logged a note-to-self in capitals, "LOOK FOR
  logging.debug STATEMENTS THAT USE F-STRINGS…", at WARNING level on every
  call. It is gone.
- `interactive_flake8` never took its "No flake8 errors—nothing to do."
  shortcut, because it tested flake8's report object for truth, and that
  object is always true. On a clean file it went on to run flake8 again
  as a subprocess and query autopep8. It now checks the error count.
- `ask_and_autopep8`'s error for an empty file read
  `('Empty file: %s', '/path')`, and a non-integer `diff_choice` made the
  logging call itself fail ("--- Logging error ---") instead of saying
  what was wrong. Both messages now name the file or value.
- `interactive_flake8` treated a flake8 that couldn't run (for example
  "No module named flake8") as a file with no issues. It now raises
  `RuntimeError` with flake8's message.
- `my_diff` (and so `diff_and_confirm` and the lint helpers) drew lines
  that were only added in red, the colour for deleted lines, ignoring
  `added_color`. They are now drawn in `added_color`, yellow by default,
  and the docstrings give the defaults correctly.
- `my_plural` without the `inflection` extra pluralised its own list of
  f-word exceptions with "-ves" anyway (chief → "chieves", roof →
  "rooves", cliff → "clifves"), because it checked the list against the
  word with its f removed. Those words now just add "s".
- `my_title_case` capitalized letters after apostrophes and digits, as
  `str.title()` does: "don't" became "Don'T" and "2nd" became "2Nd". It
  now capitalizes only each word's first letter (and each hyphenated
  part's, so "well-known" is still "Well-Known").
- `prompt_then_choose(default="")` showed "(default )" but refused
  Enter. Any default other than `None`, including an empty string, is now
  returned when Enter is pressed.
- `configure_logging` removed the root logger's handlers before opening
  its log files, so when a file couldn't be created the program was left
  with no logging at all, and a first file that did open was never closed.
  The files are now opened first; on failure nothing changes.
- `MaxLevelFilter` skipped `logging.Filter.__init__`, so its instances had
  no `name`.
- `decimal_year_to_datetime` (and so `parse_datetime` with a number or a
  numeric string) raised `OverflowError` instead of `ValueError` for
  infinite or enormous years such as `"1e10"`, and couldn't convert any
  time in the year 9999. Both now work as documented.
- `extract_timestamp` accepted any character before "pkl"
  (`"…123456xpkl"`), and its docstring now says it reads names ending in
  `YYYYMMDD-HHMMSS.pkl`. `parse_timezone` rejected a full zone name with
  surrounding spaces (`" America/New_York "`) although abbreviations
  with spaces worked.
- `seconds_in_unit("rs")` and `("qs")` returned 1e27 and 1e30
  (ronnasecond, quettasecond). Units are case-folded, so "rs" can't tell
  ronna (R) from ronto (r); as with "ms", the lowercase symbol now means
  the small prefix: rontosecond (1e-27) and quectosecond (1e-30), which
  are also accepted by name. Ronnaseconds and quettaseconds are still
  accepted by name.
- `human_quantity`'s error for a width too narrow for the value named an
  `si=` setting, which only `human_bytesize` has. It now reports
  `system='si'` or `system='iec'`; `human_bytesize`'s message is unchanged.
- `is_internet_available`'s DNS step looked only at the first lookup to
  finish, so one test name failing quickly (for example a filtering
  resolver's NXDOMAIN) gave False although another name would have
  resolved. Any success now counts. The DNS and TCP steps also return as
  soon as one attempt succeeds, instead of waiting for the slowest.
- `detect_country` asked IPinfo where 8.8.8.8 (Google's DNS server) is, so
  with a token set it reported the same country wherever you were. It
  now asks about your own address (`/lite/me`). The token travels in an
  `Authorization` header instead of the URL of a `curl` command, so it no
  longer shows up in the process list or in DEBUG logs.
- `check_if_command_exists` ran the `which` program, so it raised
  `FileNotFoundError` on systems without one. It now uses
  `shutil.which`.
- `treeview_new_files` ignored `last_mtime`: without `last_file_path` it
  always reset the cutoff to 0, so every file counted as new. The
  caller's `last_mtime` is now used; `last_file_path`, when given, still
  takes precedence.
- `load_ast_var` raised `FileNotFoundError("Failed to open …")` for an
  empty module. It now returns None, as for any variable the module
  doesn't define. Its docstring no longer promises an `AttributeError`
  that was never raised.
- `LLMs.alternative_model(strategy="multi_objective", ...)` scored with the
  applied config's weights and assumed token counts, ignoring the
  overrides passed to it. Strategies now receive the config they are
  selecting for in `SelectionContext.extras["config"]`.
- `LLMs.refresh_selection()` re-applied the resolved config, so if the
  first selection happened offline (which forces `only_local_models`)
  remote models stayed excluded after reconnecting. It now re-applies the
  config last passed to `apply_config`.
- `fix_mojibake` left CP1252 files as CP1252 unless they also contained
  mojibake, although its docstring promises to recode them to UTF-8. A
  file that isn't valid UTF-8 is now always written back as UTF-8.

### Removed (breaking)

- `CheckResult`, `InflectEngine` and `FormatChecker` from the top-level
  namespace. All three were helpers for a single public function and
  became public only because the 0.3.0 split exported every name in
  `univ_defs.py` without a leading underscore. `CheckResult` holds the
  probe results that `is_internet_available` reduces to a `bool`; nothing
  public returns or accepts one. `InflectEngine` is the type hint for the
  `inflect` engine behind `my_plural`. `FormatChecker` is the AST visitor
  behind `check_python_formatting`. They are now `_CheckResult`,
  `_InflectEngine` and `_FormatChecker` in their modules, and none of the
  three public functions changes.

### Changed

- Public surface: 193 → 190 names.
- `tests/_baseline_signatures.json` updated to match.
- The README's opening line now gives the size of the public surface as
  `tools/generate_readme.py` counts it, so it can no longer drift. It had
  said 181.
- The `files` extra no longer installs `atomicwrites`, which is archived
  upstream and no longer used.

## [0.6.3] - 2026-10-17

### Fixed

- Some `AdaptiveDateFormatter` subclasses came back from `pickle` or
  `copy.deepcopy` as the wrong class, a regression in 0.6.2. A subclass
  that lists `Formatter` itself, `class S(AdaptiveDateFormatter,
  Formatter)`, silently came back as a plain `AdaptiveDateFormatter`
  without its overrides; with `Formatter` listed first it came back as a
  bare matplotlib `Formatter`; and a subclass of `type(fmt)` could not be
  pickled. Every subclass now comes back as itself. Subclasses that list
  only `AdaptiveDateFormatter` were never affected.
- Subclasses lost ordinary Python behaviour in 0.6.1. A constructor
  parameter of their own, positional or keyword, raised `TypeError` from
  `AdaptiveDateFormatter.__new__()`; their `__getstate__` and
  `__setstate__` were ignored by `pickle` and `copy.deepcopy`, so a
  subclass holding a lock could not be pickled; and values kept in
  `__slots__` were lost. Construction and copying now work as for any
  class. The switch to the `Formatter`-backed class moved from `__new__`
  into `__init__`, so a subclass's `__init__` must call
  `super().__init__()`, and the signature is 0.6.0's again. Pickling takes
  the state from `__getstate__` and restores it without calling
  `__init__`, as Python's default pickling does, so a subclass whose
  `__init__` has required arguments unpickles too.

### Changed

- Formatters pickled by 0.6.3 cannot be unpickled by earlier versions.
  Pickles from earlier versions still load.
- The class docstring now says that `__init_subclass__` hooks also see the
  class built at run time, and that a subclass listing `Formatter` among
  its bases, `class S(AdaptiveDateFormatter, Formatter)`, gets none.

## [0.6.2] - 2026-10-17

### Fixed

- Type checkers rejected `AdaptiveDateFormatter` where matplotlib wants a
  `Formatter`: `ax.xaxis.set_major_formatter(AdaptiveDateFormatter())` was
  an `arg-type` error under mypy, though every instance is a `Formatter` at
  run time. The class now declares `Formatter` as its base for type
  checkers only (behind `TYPE_CHECKING`); at run time nothing changes and
  `import emmykit` still does not import matplotlib. A
  `cast(Formatter, ...)` workaround can go.
- `type(fmt)(...)` built a second run-time class on top of the first, and
  the result could not be pickled. It now constructs an ordinary
  formatter of the same class.
- `round_out` returned a `numpy.float64` despite its `-> float`
  annotation, so its repr depended on the numpy major version
  (`np.float64(3.15)` under numpy 2, `3.15` under numpy 1), and three
  pinned results failed on numpy 1.26. It now returns a plain `float`.
  `np.float64` already subclassed `float`, so arithmetic and `isinstance`
  checks behave as before. The test suite passes on numpy 1.26.4 with
  matplotlib 3.8.4 as well as on numpy 2.

## [0.6.1] - 2026-10-17

### Fixed

- `AdaptiveDateFormatter` never adapted on a real axis. It was not a
  `matplotlib.ticker.Formatter`, so `set_major_formatter` silently wrapped
  it in a `FuncFormatter`, which asks for one label at a time;
  `format_ticks`, the method that compares the ticks, never ran, and every
  label fell back to day precision. A four-year axis read `2021-01-01,
  2021-07-01, ...` instead of `2021-01, 2021-07, ...`, on the x axis and on
  colorbars alike. Every instance is now a real `Formatter`, so matplotlib
  installs it as-is. `adaptive_date_labels` was always correct and is
  unchanged.
- `import emmykit` still does not import matplotlib: the formatter builds
  its matplotlib-backed class on first construction. Without matplotlib,
  construction raises an `ImportError` that names `emmykit[datetime]`.
  Figures carrying the formatter still pickle.
- The constructor keywords are unchanged. Its signature now reads
  `-> 'AdaptiveDateFormatter'` rather than `-> 'None'`, because it comes
  from the new `__new__`; the public surface is otherwise unchanged at
  193 names.
- New tests draw the formatter on a real x axis and colorbar. There were
  none before, which is how this shipped.

## [0.6.0] - 2026-08-23

### Added

- `as_unit` on `human_quantity` and `choose_prefix`: name the unit you want
  and the formatter stops choosing for you. `human_quantity(0.02, METERS,
  as_unit="cm")` is `"2.0 cm"` under the default engineering mode, and
  `choose_prefix(ticks, METERS, as_unit="cm")` pins a whole axis to `("c",
  0.01)` without reading the ticks at all — the case that matters for a
  colorbar whose data would otherwise pick its own scale.
- The string is parsed against the `Unit` you passed, so custom units work
  too: `"cm"`, `"centimeter"`, `"centimeters"`, `"m"`, `"KiB"`,
  `"kibibytes"`, and both micro spellings, `"µm"` and `"um"`, each echoed
  back as written. The spelling of the request decides the spelling of the
  result. Matching is case-sensitive: `"KB"` raises rather than guessing
  between `"kB"` and `"KiB"`.
- `mode` is bypassed, since it only ever governed automatic selection, and a
  binary prefix implies the binary system. `system="iec"` is never a default,
  so a decimal prefix under it raises.

### Changed

- `human_quantity`'s `long_units` default is now `None`, meaning "follow the
  `as_unit` spelling, short otherwise". Every 0.5.0 call behaves identically;
  the sentinel is what lets an explicit `long_units=False` beat a long
  `as_unit`.
- Public surface unchanged at 193 names. `human_bytesize` is untouched, and
  its 4032-case baseline still passes byte-for-byte.
- `requires-python` drops its upper bound: `>=3.12,<3.14` becomes `>=3.12`.
  The cap locked the package out of every Python after 3.13 for no reason
  the code supports — the base is stdlib-only and nothing here depends on a
  language feature that a later release removes. The floor stays 3.12, and
  the `Programming Language :: Python` classifiers still list only the
  versions actually tested.

## [0.5.0] - 2026-08-23

### Added

- `human_quantity(num, unit, ...)` in `emmykit.humanize`: the general
  form of `human_bytesize`, formatting any quantity with an SI or IEC
  prefix (`"3.2 ZJ"`, `"1.5 KiB"`, `"1.5 kilometers"`). Units are
  `Unit` value objects carrying symbol, singular and plural long names,
  since long names are not derivable from the symbol (`"Hz"` →
  `"hertz"`/`"hertz"`); `BYTES`, `METERS`, `GRAMS`, `SECONDS`, `JOULES`,
  `WATTS` and `HERTZ` ship ready-made.
- Values below 1.0 now reach a prefix. `mode="engineering"` (default)
  keeps to powers of 1000, so `0.02` metres is `"20.0 mm"`;
  `mode="full_si"` also allows deci, centi, deka and hecto, so the same
  value is `"2.0 cm"`. Micro is `"µ"` (U+00B5), or `"u"` with
  `ascii_micro=True`. The binary system has no submultiples, so
  `system="iec"` with `mode="full_si"` raises `ValueError` rather than
  silently falling back to decimal prefixes.
- `choose_prefix(values, unit, ...)` returns one `(symbol, factor)` pair
  for a whole set of values — the shared scale an axis or colorbar needs,
  so ticks read `"0.1"`, `"0.2"`, `"1.1"` against a single `"cm"` label
  instead of drifting between `"1 mm"` and `"1 cm"`. The choice comes
  from the largest finite magnitude; NaN and infinity are ignored, and
  empty or all-zero sets return the unprefixed scale `("", 1.0)`.
- `emmykit.palette` (layer 0, stdlib-only): `Palette`, a frozen value
  object holding an ordered tuple of qualitative `series` colours plus
  the `background` / `foreground` / `grid` roles a figure needs;
  `palette(name)` and `palette_names()` over a registry that ships
  `"light"` and `"dark"`; `contrast_ratio(color, background)` returning
  the WCAG 2.1 ratio; and `MIN_CONTRAST_RATIO` (4.5), the threshold every
  series colour clears against its own palette's background. Colour is
  now usable without constructing an `Options` — the reason for the
  extraction. Requesting an unregistered name raises `ValueError` listing
  the names that are registered.
- `Palette.rc_params()` returns a matplotlib rcParams mapping — the
  colour cycle plus figure/axes/savefig face colours, text/label/edge and
  tick colours, and the grid colour — so
  `with plt.rc_context(palette.rc_params()):` themes every artist without
  the caller naming a colour. This is the only matplotlib-aware code in
  the module and it imports lazily; the rest is stdlib, and matplotlib
  stays an optional dependency.
- Series colours derive from the Okabe-Ito colourblind-safe set, minus
  black (a role here, and invisible on the dark palette) and minus yellow
  (`#F0E442`, which converges on the darkened orange once both are forced
  to clear 4.5:1 against white). Per-theme readability comes from
  shifting luminance toward or away from the background only as far as
  the threshold requires, not from picking replacements by eye.

### Fixed

- `PlotOptions.lightcolors` ended with `"lightpurple"`, which is in
  neither matplotlib's CSS4 nor its base colour table, so
  `matplotlib.colors.to_rgb` raised `ValueError` for any caller reaching
  the fifth entry. Every colour is now an explicit `#RRGGBB` string, and
  a test resolves every colour of every registered palette through
  `to_rgb`.
- Dark mode left unreadable colours in `PlotOptions.colors`. The old
  `_apply_theme` swapped only `black` → `darkgrey`, leaving `purple`
  (2.2:1 on black), `blue` (2.4:1) and `green` (4.1:1) in place, and
  relied on the caller remembering to reach for `lightcolors` instead —
  which nothing enforced and forgetting was silent. The dark palette's
  six series colours now measure 4.5:1 to 9.3:1 against its own
  background, asserted in a test.

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

- `human_bytesize` is now a thin wrapper over the general formatter. Its
  name, signature and output are unchanged byte-for-byte, including the
  three behaviours the general formatter deliberately does not inherit:
  no submultiples (`0.5` stays `"0.5 B"`), no prefix promotion after
  rounding (`999999` with `si=True` stays `"1000.0 kB"`, where
  `human_quantity` gives `"1.0 MW"` for the same shape of input), and
  infinity walking the table to the largest prefix (`"inf QiB"`, where
  `human_quantity` renders non-finite values unprefixed, `"inf m"`).
  `tests/_baseline_human_bytesize.json` pins 4032 (value, option)
  combinations, including both width-constrained `ValueError` messages.
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
- Public surface: 178 → 183 names, the five `emmykit.palette` exports.
- Public surface: 183 → 193 names, the ten `emmykit.humanize` exports
  (`Unit`, seven ready-made units, `human_quantity`, `choose_prefix`).
- `PlotOptions` now holds a `Palette` (new `palette` attribute) and
  exposes `colors`, `lightcolors`, `background_color` and `text_color` as
  read-only properties delegating to it. Readers are unaffected; the
  values change (hex strings from the Okabe-Ito-derived series rather
  than matplotlib colour names) and *writers* now raise `AttributeError`,
  since a settable `colors` would let a caller reintroduce exactly the
  unreadable dark-mode list this release removed. Set `dark_mode` to
  change theme, or use `emmykit.palette` directly.
- `PlotOptions._base_colors`, `._base_lightcolors` and `._apply_theme()`
  are gone. Private, but `_apply_theme` was documented as the hook a
  child class inherited through `dark_mode`; that responsibility now sits
  in the `dark_mode` setter, which swaps the whole palette in one step.
- `PlotOptions.lightcolors` is now derived rather than hand-maintained:
  each entry is its `colors` counterpart blended half-way toward the
  background, so the two lists correspond positionally at any length.
  Under the old lists that correspondence was coincidental.
- `myfigsize`, `fsize`, `dpi_choice`, `markers` and `linestyles` stay on
  `PlotOptions` unchanged — geometry and dash/marker cycles are not
  colour, and a caller with its own geometry conventions should be able
  to take the palette without inheriting a figure size.
- `emmykit.<submodule>` attribute access (e.g. `emmykit.json_io`) is
  intentionally unavailable: `__init__.py` strips submodule attributes
  after import, so reach a submodule with `from emmykit.json_io import X`
  or `import emmykit.json_io as jio` — plain `import emmykit.json_io`
  does not leave `emmykit.json_io` resolvable afterward, since the module
  is already in `sys.modules` and the import system skips re-attaching it
  to the parent package. `palette` is the one name where module and
  function collide: `emmykit.palette` is the lookup *function*, and the
  scrub-list deliberately omits the name so that binding survives.
  `from emmykit.palette import palette` — the documented form — resolves
  through `sys.modules` and is unaffected.

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
