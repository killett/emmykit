# emmykit

Personal Python utility kit: 181 importable functions, classes, and constants across 32 submodules
in 9 dependency layers (README highlights the user-facing surface — internal punctuation, frozenset
aliases, probe-target lists, and translation tables are referenced by section rather than enumerated).
Base install is stdlib-only; heavier helpers
(datetime parsing via numpy/pandas/dateutil, mojibake fixing via ftfy, lint runners,
LLM wrappers, ffmpeg/VLC controls) are gated behind optional extras so a bare
`import emmykit` is fast and side-effect-free.

## Install

```bash
pip install emmykit                 # base — stdlib only
pip install 'emmykit[all]'          # all optional extras
pip install 'emmykit[datetime]'     # pick a single extra group
```

```bash
uv add emmykit                      # base
uv add 'emmykit[all]'               # all optional extras
uv add 'emmykit[datetime]'          # pick a single extra group
```

Available extras groups: `datetime`, `text`, `lint`, `llm`, `media`, `files`, `inflection`, `html`, `all`.

## Quick start

```python
import emmykit as ek

print(ek.human_bytesize(1024**3))        # "1.0 GiB"
ts = ek.parse_datetime("2026-06-06T12:34:56Z")
print(ek.my_capitalize("hello world"))   # "Hello world"
```

## Teaching the JSON round trip about your own types

`to_jsonable` / `from_jsonable` know a fixed set of types (`Path`, `set`,
`datetime`, `Decimal`, `Enum`, compiled regexes, …). Anything else falls through
to `str(obj)`, which fails *silently*: the file reloads holding a repr string
where an object should be, and membership tests quietly degrade to substring
matching. Register your types instead — `emmykit` never has to import your
package.

```python
import emmykit as ek

class Duration:
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Duration) and other.seconds == self.seconds

ek.register_json_type(
    Duration,
    lambda o: {"seconds": o.seconds},          # -> payload
    tag="duration",                            # -> written as "__type__"
    decode=lambda p: Duration(p["seconds"]),   # payload -> object
)

blob = ek.to_jsonable({"limit": Duration(90)})
# {"limit": {"__type__": "duration", "seconds": 90}}
ek.from_jsonable(blob) == {"limit": Duration(90)}   # True
```

This also reaches `save_options_to_json` / `load_options_from_json`, which call
the converters internally.

- **Dispatch is by `isinstance`**, so subclasses are covered. When two
  registrations match, the more specific class wins; unrelated ties go to the
  most recently registered.
- **Registrations beat the built-ins.** A registered handler is consulted before
  every built-in encoder and before the `str()` fallback.
- **Payloads are converted too.** The mapping your encoder returns is passed back
  through the converter, so it may contain `Path`, `set`, `datetime`, or another
  registered type. The recursion guard stays in effect across that call.
- **`roundtrip=False`** returns the bare payload with no `__type__` key.
- **Encode-only registration** — omit *both* `tag` and `decode` (supplying one
  without the other is an error). The object is serialized through its encoder
  but never tagged, in either `roundtrip` mode, and reloads as a plain `dict`:

  ```python
  ek.register_json_type(LiveIndex, lambda o: {"probed": sorted(o.names), "offline": o.offline})
  ```

  This is the honest choice for an object that can be *described* faithfully but
  not *rebuilt* faithfully — one whose contents came from probing a live
  interpreter or a live HTTP client, where a reconstructed copy would answer
  differently while looking identical. A readable snapshot plus a plain `dict` on
  reload beats a decoder that fabricates a plausible-but-wrong object.
- **Tags are exclusive.** Reusing a registered tag or class raises unless you
  pass `replace=True`; the built-in tags in `BUILTIN_JSON_TAGS` (`path`, `set`,
  `datetime`, `recursion`, …) are rejected outright. `unregister_json_type(cls)`
  or `unregister_json_type("tag")` removes a handler again — useful in test
  teardown.

## Table of contents

- [`constants` — ANSI colors, unicode punctuation, default encoding, ignore-lists](#m-constants)
  - [`DEFAULT_ENCODING`](#default_encoding)
  - [`DEFAULT_EXCLUDE_DIRS`](#default_exclude_dirs)
  - [`ANSI color escapes`](#c-constants-ansi-color-escapes)
  - [`IGNORED_CODES`](#c-constants-ignored-codes)
  - [`IGNORE_THESE_ERRORS`](#c-constants-ignore-these-errors)
- [`extensions` — File-extension lookup tables (audio / video / image / book / text / html / playlist / archive / subtitle)](#m-extensions)
  - [`ALL_KNOWN_EXTENSIONS`](#all_known_extensions)
  - [`ARCHIVE_EXTENSIONS`](#archive_extensions)
  - [`AUDIO_EXTENSIONS`](#audio_extensions)
  - [`BOOK_EXTENSIONS`](#book_extensions)
  - [`HTML_EXTENSIONS`](#html_extensions)
  - [`IMAGE_EXTENSIONS`](#image_extensions)
  - [`PLAYLIST_EXTENSIONS`](#playlist_extensions)
  - [`PYTHON_EXTENSIONS`](#python_extensions)
  - [`SUBTITLE_EXTENSIONS`](#subtitle_extensions)
  - [`TEXT_ENCODINGS`](#text_encodings)
  - [`TEXT_EXTENSIONS`](#text_extensions)
  - [`VIDEO_EXTENSIONS`](#video_extensions)
- [`embedded_scripts` — Pre-packaged helper-script source-strings](#m-embedded_scripts)
  - [`SETUP_CARTOPY_SCRIPT`](#setup_cartopy_script)
- [`palette` — Colourblind-safe figure palettes and WCAG contrast measurement](#m-palette)
  - [`contrast_ratio`](#contrast_ratio)
  - [`MIN_CONTRAST_RATIO`](#min_contrast_ratio)
  - [`Palette`](#palette)
  - [`palette`](#palette)
  - [`palette_names`](#palette_names)
- [`_version` — Package and Python version constants](#m-_version)
  - [`PY_VERSION`](#py_version)
- [`options` — Options dataclasses for configuration](#m-options)
  - [`Options`](#options)
  - [`PlotOptions`](#plotoptions)
- [`inflect_utils` — Grammar + pluralization helpers](#m-inflect_utils)
  - [`InflectEngine`](#inflectengine)
  - [`my_plural`](#my_plural)
- [`logging_utils` — Logging configuration and custom handlers](#m-logging_utils)
  - [`configure_logging`](#configure_logging)
  - [`fallback_logging_config`](#fallback_logging_config)
  - [`FlushingStreamHandler`](#flushingstreamhandler)
  - [`MaxLevelFilter`](#maxlevelfilter)
  - [`MemoryHandler`](#memoryhandler)
  - [`print_all_errors`](#print_all_errors)
  - [`return_method_name`](#return_method_name)
- [`paths_ensure` — Path normalization](#m-paths_ensure)
  - [`ensure_path`](#ensure_path)
- [`safe_paths` — Exception-swallowing filesystem queries](#m-safe_paths)
  - [`ensure_dir`](#ensure_dir)
  - [`ensure_file`](#ensure_file)
  - [`safe_ctime`](#safe_ctime)
  - [`safe_exists`](#safe_exists)
  - [`safe_is_dir`](#safe_is_dir)
  - [`safe_is_file`](#safe_is_file)
  - [`safe_mtime`](#safe_mtime)
  - [`safe_size`](#safe_size)
  - [`safe_stat`](#safe_stat)
- [`file_io` — Atomic file-write helper](#m-file_io)
  - [`my_atomic_write`](#my_atomic_write)
- [`io_subprocess` — Subprocess wrappers + critical-error reporter](#m-io_subprocess)
  - [`my_critical_error`](#my_critical_error)
  - [`my_fopen`](#my_fopen)
  - [`my_popen`](#my_popen)
  - [`MyPopenResult`](#mypopenresult)
- [`prompts` — Interactive Y/N + multi-choice prompts](#m-prompts)
  - [`prompt_then_choose`](#prompt_then_choose)
  - [`prompt_then_confirm`](#prompt_then_confirm)
- [`introspection` — AST + source-code reflection](#m-introspection)
  - [`compile_code`](#compile_code)
  - [`if_filepath_then_read`](#if_filepath_then_read)
  - [`load_ast_var`](#load_ast_var)
  - [`normalize_to_dict`](#normalize_to_dict)
  - [`show_function_source`](#show_function_source)
- [`humanize` — Human-readable number formatting](#m-humanize)
  - [`BYTES`](#bytes)
  - [`choose_prefix`](#choose_prefix)
  - [`GRAMS`](#grams)
  - [`HERTZ`](#hertz)
  - [`human_bytesize`](#human_bytesize)
  - [`human_quantity`](#human_quantity)
  - [`JOULES`](#joules)
  - [`METERS`](#meters)
  - [`round_out`](#round_out)
  - [`sci_exp`](#sci_exp)
  - [`SECONDS`](#seconds)
  - [`Unit`](#unit)
  - [`WATTS`](#watts)
- [`numeric_helpers` — Numeric parsing + unit-to-seconds conversion](#m-numeric_helpers)
  - [`is_float`](#is_float)
  - [`seconds_in_unit`](#seconds_in_unit)
- [`datetime_utils` — Date / time parsing, formatting, timezone handling](#m-datetime_utils)
  - [`adaptive_date_labels`](#adaptive_date_labels)
  - [`AdaptiveDateFormatter`](#adaptivedateformatter)
  - [`AnyDateTimeType`](#anydatetimetype)
  - [`decimal_year_to_datetime`](#decimal_year_to_datetime)
  - [`extract_timestamp`](#extract_timestamp)
  - [`format_date_range`](#format_date_range)
  - [`human_timespan`](#human_timespan)
  - [`parse_datetime`](#parse_datetime)
  - [`parse_timezone`](#parse_timezone)
  - [`Precision`](#precision)
- [`json_io` — JSON serialization + dataclass conversion](#m-json_io)
  - [`BUILTIN_JSON_TAGS`](#builtin_json_tags)
  - [`from_jsonable`](#from_jsonable)
  - [`load_options_from_json`](#load_options_from_json)
  - [`register_json_type`](#register_json_type)
  - [`save_options_to_json`](#save_options_to_json)
  - [`to_jsonable`](#to_jsonable)
  - [`unregister_json_type`](#unregister_json_type)
- [`diff_view` — Diff rendering with visible whitespace](#m-diff_view)
  - [`diff_and_confirm`](#diff_and_confirm)
  - [`highlight_changes`](#highlight_changes)
  - [`is_python_script`](#is_python_script)
  - [`my_diff`](#my_diff)
- [`text` — Mojibake fixing, encoding detection, casing helpers](#m-text)
  - [`contains_mojibake`](#contains_mojibake)
  - [`decode_cp1252`](#decode_cp1252)
  - [`decode_utf8`](#decode_utf8)
  - [`ensure_utf8_meta`](#ensure_utf8_meta)
  - [`fix_mojibake`](#fix_mojibake)
  - [`fix_text`](#fix_text)
  - [`my_capitalize`](#my_capitalize)
  - [`my_title_case`](#my_title_case)
  - [`normalize_for_search`](#normalize_for_search)
- [`hosts` — Hostname + computer-name detection](#m-hosts)
  - [`analyze_computer_name_results`](#analyze_computer_name_results)
  - [`COMPUTER_NAME`](#computer_name)
  - [`get_computer_name`](#get_computer_name)
  - [`get_hostname_os_uname`](#get_hostname_os_uname)
  - [`get_hostname_platform`](#get_hostname_platform)
  - [`get_hostname_socket`](#get_hostname_socket)
  - [`get_hostname_subprocess_hostname`](#get_hostname_subprocess_hostname)
  - [`get_hostname_subprocess_scutil`](#get_hostname_subprocess_scutil)
  - [`IS_NASA_COMPUTER`](#is_nasa_computer)
  - [`NASA computer-name prefixes`](#c-hosts-nasa-computer-name-prefixes)
- [`network` — Internet-connectivity probes](#m-network)
  - [`CheckResult`](#checkresult)
  - [`is_internet_available`](#is_internet_available)
- [`python_env` — Python interpreter discovery](#m-python_env)
  - [`check_python_version`](#check_python_version)
  - [`find_preferred_python_version`](#find_preferred_python_version)
- [`files` — Checksums, downloads, filename formatting, free-space queries](#m-files)
  - [`calculate_checksum`](#calculate_checksum)
  - [`download_file`](#download_file)
  - [`filename_format`](#filename_format)
  - [`query_free_space`](#query_free_space)
  - [`verify_script`](#verify_script)
- [`lint` — flake8 / autopep8 / mypy interactive runners + multireplace](#m-lint)
  - [`ask_and_autopep8`](#ask_and_autopep8)
  - [`ask_and_replace`](#ask_and_replace)
  - [`check_python_formatting`](#check_python_formatting)
  - [`FormatChecker`](#formatchecker)
  - [`get_autopep8_fixable_codes`](#get_autopep8_fixable_codes)
  - [`interactive_flake8`](#interactive_flake8)
  - [`multireplace`](#multireplace)
  - [`run_flake8`](#run_flake8)
  - [`run_mypy`](#run_mypy)
- [`treeview` — Directory tree with new-file highlighting](#m-treeview)
  - [`treeview_new_files`](#treeview_new_files)
- [`docker_utils` — Docker daemon + image lifecycle helpers](#m-docker_utils)
  - [`ensure_daemon_running`](#ensure_daemon_running)
  - [`ensure_docker_installed`](#ensure_docker_installed)
  - [`ensure_image_built`](#ensure_image_built)
  - [`run_with_docker_fixes`](#run_with_docker_fixes)
- [`system` — OS-level process + resource helpers](#m-system)
  - [`check_if_command_exists`](#check_if_command_exists)
  - [`detect_country`](#detect_country)
  - [`get_effective_free_memory`](#get_effective_free_memory)
  - [`is_process_running`](#is_process_running)
  - [`kill_process`](#kill_process)
  - [`open_filemanager_with_dirs`](#open_filemanager_with_dirs)
  - [`open_terminal_and_run_command`](#open_terminal_and_run_command)
  - [`start_only_one_instance`](#start_only_one_instance)
- [`media` — Video / audio helpers (ffmpeg, VLC, system volume)](#m-media)
  - [`ensure_even_dimensions`](#ensure_even_dimensions)
  - [`extract_and_concatenate_segments`](#extract_and_concatenate_segments)
  - [`find_ffmpeg`](#find_ffmpeg)
  - [`get_video_duration_seconds`](#get_video_duration_seconds)
  - [`open_dir_in_VLC`](#open_dir_in_vlc)
  - [`open_in_vlc`](#open_in_vlc)
  - [`open_playlist_in_VLC`](#open_playlist_in_vlc)
  - [`set_system_volume`](#set_system_volume)
- [`html_files` — HTML filename munging + multi-file combination](#m-html_files)
  - [`combine_html_files`](#combine_html_files)
  - [`remove_prefix_from_filename`](#remove_prefix_from_filename)
  - [`remove_prefix_from_html_title`](#remove_prefix_from_html_title)
- [`llm` — LLM wrapper, config dataclasses, model selection](#m-llm)
  - [`LLMConfig`](#llmconfig)
  - [`LLMs`](#llms)
  - [`ModelInfo`](#modelinfo)
  - [`SelectionContext`](#selectioncontext)
  - [`SelectionStrategy`](#selectionstrategy)
  - [`StrategyFn`](#strategyfn)

## API reference

<a id="m-constants"></a>
### `constants` — ANSI colors, unicode punctuation, default encoding, ignore-lists

_Layer 0._  `from emmykit.constants import …`

Terminal escape codes, curly quotes, the em-dash, the package's UTF-8 default, the set of errno codes treated as benign by `safe_*`, and the flake8/autopep8 codes Emmy deliberately ignores.

<a id="default_encoding"></a>
<details>
<summary><code>DEFAULT_ENCODING</code> — str = 'utf-8'</summary>

```python
DEFAULT_ENCODING: str = 'utf-8'
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/constants.py#L8)

</details>

<a id="default_exclude_dirs"></a>
<details>
<summary><code>DEFAULT_EXCLUDE_DIRS</code> — set[str] (6 items)</summary>

```python
DEFAULT_EXCLUDE_DIRS: set[str] = {'.git', '.venv', '__pycache__', 'build', 'dist', 'venv'}
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/constants.py#L65)

</details>

<a id="c-constants-ansi-color-escapes"></a>
<details>
<summary><code>ANSI color escapes</code> — 5 terminal-escape strings: ANSI_CYAN / GREEN / RED / RESET / YELLOW.</summary>

**Includes:** `ANSI_CYAN`, `ANSI_GREEN`, `ANSI_RED`, `ANSI_RESET`, `ANSI_YELLOW`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/constants.py#L16)

</details>

<a id="c-constants-ignored-codes"></a>
<details>
<summary><code>IGNORED_CODES</code> — flake8 + autopep8 codes Emmy deliberately ignores.</summary>

**Includes:** `IGNORED_CODES`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/constants.py#L20)

</details>

<a id="c-constants-ignore-these-errors"></a>
<details>
<summary><code>IGNORE_THESE_ERRORS</code> — errno codes treated as benign by safe_* helpers.</summary>

**Includes:** `IGNORE_THESE_ERRORS`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/constants.py#L58)

</details>

<a id="m-extensions"></a>
### `extensions` — File-extension lookup tables (audio / video / image / book / text / html / playlist / archive / subtitle)

_Layer 0._  `from emmykit.extensions import …`

Lists and frozensets of common file extensions per media kind, plus an `ALL_KNOWN_EXTENSIONS` umbrella and the canonical `TEXT_ENCODINGS` ordering used by `my_fopen` when sniffing.

Each `*_EXTENSIONS` list has a `*_EXTENSIONS_SET` frozenset alias for fast membership tests.

<a id="all_known_extensions"></a>
<details>
<summary><code>ALL_KNOWN_EXTENSIONS</code> — Final[tuple[str, ...]] (979 items)</summary>

```python
ALL_KNOWN_EXTENSIONS: Final[tuple[str, ...]] = ('.py', '.pyw', '.html', '.htm', '.xhtml', '.txt', '.csv', '.json', '.xml', '.adoc',
 '.asciidoc', '.bib', '.cfg', '.conf', '.ini', '.log', '.md', '.markdown',
 '.properties', '.rtf', '.rst', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L319)

</details>

<a id="archive_extensions"></a>
<details>
<summary><code>ARCHIVE_EXTENSIONS</code> — Final[tuple[str, ...]] (376 items)</summary>

```python
ARCHIVE_EXTENSIONS: Final[tuple[str, ...]] = ('.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.tbz2', '.tz2', '.lzma',
 '.lz', '.xpi', '.crx', '.zst', '.cab', '.arj', '.ace', '.uue', '.zoo', '.jar', '.war',
 '.ear', '.iso', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L308)

</details>

<a id="audio_extensions"></a>
<details>
<summary><code>AUDIO_EXTENSIONS</code> — Final[tuple[str, ...]] (112 items)</summary>

```python
AUDIO_EXTENSIONS: Final[tuple[str, ...]] = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a', '.alac', '.aiff', '.opus',
 '.amr', '.pcm', '.au', '.raw', '.dts', '.ac3', '.mka', '.mpc', '.vqf', '.ape', '.shn',
 '.ra', '.rm', '.oga', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L206)

</details>

<a id="book_extensions"></a>
<details>
<summary><code>BOOK_EXTENSIONS</code> — Final[tuple[str, ...]] (63 items)</summary>

```python
BOOK_EXTENSIONS: Final[tuple[str, ...]] = ('.epub', '.pdf', '.txt', '.rtf', '.html', '.htm', '.xhtml', '.doc', '.docx', '.odt',
 '.azw', '.azw1', '.azw3', '.azw4', '.azw6', '.kfx', '.mobi', '.prc', '.tpz', '.ibooks',
 '.fb2', '.fbz', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L80)

</details>

<a id="html_extensions"></a>
<details>
<summary><code>HTML_EXTENSIONS</code> — Final[tuple[str, ...]] (3 items)</summary>

```python
HTML_EXTENSIONS: Final[tuple[str, ...]] = ('.html', '.htm', '.xhtml')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L47)

</details>

<a id="image_extensions"></a>
<details>
<summary><code>IMAGE_EXTENSIONS</code> — Final[tuple[str, ...]] (127 items)</summary>

```python
IMAGE_EXTENSIONS: Final[tuple[str, ...]] = ('.bmp', '.dib', '.gif', '.jpeg', '.jpg', '.jpe', '.jfif', '.pjpeg', '.pjp', '.png',
 '.pbm', '.pgm', '.ppm', '.pnm', '.pam', '.tif', '.tiff', '.sgi', '.rgb', '.tga',
 '.hdr', '.exr', '.webp', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L243)

</details>

<a id="playlist_extensions"></a>
<details>
<summary><code>PLAYLIST_EXTENSIONS</code> — Final[tuple[str, ...]] (28 items)</summary>

```python
PLAYLIST_EXTENSIONS: Final[tuple[str, ...]] = ('.m3u', '.m3u8', '.pls', '.xspf', '.asx', '.wpl', '.zpl', '.b4s', '.cue', '.smil',
 '.smi', '.ram', '.wax', '.wmx', '.wvx', '.fpl', '.mpcpl', '.dpl', '.aimppl',
 '.aimppl4', '.pla', '.xml', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L270)

</details>

<a id="python_extensions"></a>
<details>
<summary><code>PYTHON_EXTENSIONS</code> — Final[tuple[str, ...]] (2 items)</summary>

```python
PYTHON_EXTENSIONS: Final[tuple[str, ...]] = ('.py', '.pyw')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L43)

</details>

<a id="subtitle_extensions"></a>
<details>
<summary><code>SUBTITLE_EXTENSIONS</code> — Final[tuple[str, ...]] (47 items)</summary>

```python
SUBTITLE_EXTENSIONS: Final[tuple[str, ...]] = ('.srt', '.sub', '.idx', '.ass', '.ssa', '.vtt', '.ttml', '.dfxp', '.smi', '.smil',
 '.usf', '.psb', '.mks', '.lrc', '.stl', '.pjs', '.rt', '.aqt', '.gsub', '.jss', '.dks',
 '.mpl2', '.sbt', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L230)

</details>

<a id="text_encodings"></a>
<details>
<summary><code>TEXT_ENCODINGS</code> — Final[tuple[str, ...]] (146 items)</summary>

```python
TEXT_ENCODINGS: Final[tuple[str, ...]] = ('utf-8', 'latin-1', 'ascii', 'iso-8859-1', 'big5', 'utf-8-sig', 'utf-16', 'utf-16-be',
 'utf-16-le', 'utf-32', 'utf-32-be', 'utf-32-le', 'cp1252', 'cp1251', 'cp1250',
 'cp1253', 'cp1254', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L8)

</details>

<a id="text_extensions"></a>
<details>
<summary><code>TEXT_EXTENSIONS</code> — Final[tuple[str, ...]] (143 items)</summary>

```python
TEXT_EXTENSIONS: Final[tuple[str, ...]] = ('.txt', '.html', '.htm', '.csv', '.json', '.xml', '.adoc', '.asciidoc', '.bib', '.cfg',
 '.conf', '.ini', '.log', '.md', '.markdown', '.properties', '.rtf', '.rst', '.sgm',
 '.sgml', '.tex', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L51)

</details>

<a id="video_extensions"></a>
<details>
<summary><code>VIDEO_EXTENSIONS</code> — Final[tuple[str, ...]] (133 items)</summary>

```python
VIDEO_EXTENSIONS: Final[tuple[str, ...]] = ('.mp4', '.mkv', '.mov', '.avi', '.mpg', '.mpeg', '.wmv', '.m4v', '.flv', '.divx',
 '.vob', '.iso', '.3gp', '.webm', '.mts', '.m2ts', '.ts', '.ogv', '.rm', '.rmvb',
 '.asf', '.f4v', '.mxf', ...)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/extensions.py#L177)

</details>

<a id="m-embedded_scripts"></a>
### `embedded_scripts` — Pre-packaged helper-script source-strings

_Layer 0._  `from emmykit.embedded_scripts import …`

Python script literals shipped as importable strings — used by Emmy's external automation to drop drop-in helpers into other projects.

The five standalone command-line programs that used to live here (`PRINTALL_SCRIPT`, `MYDIFF_SCRIPT`, `MYAUDIT_SCRIPT`, `MULTIREPLACE_SCRIPT`, `TREEVIEW_SCRIPT`) moved to [killett/utilities](https://github.com/killett/utilities) in 0.4.0; `UNIV_DEFS_SYS_PATH_SCRIPT` was deleted.

<a id="setup_cartopy_script"></a>
<details>
<summary><code>SETUP_CARTOPY_SCRIPT</code> — str (532 chars)</summary>

```python
SETUP_CARTOPY_SCRIPT: str = '<532-char Python script source, 16 lines>'
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/embedded_scripts.py#L12)

</details>

<a id="m-palette"></a>
### `palette` — Colourblind-safe figure palettes and WCAG contrast measurement

_Layer 0._  `from emmykit.palette import …`

Frozen `Palette` value objects — an Okabe-Ito-derived qualitative series plus background / foreground / grid roles, every colour an explicit hex string — looked up by name and handed to matplotlib as an rcParams mapping. Stdlib-only except for `Palette.rc_params`.

<a id="contrast_ratio"></a>
<details>
<summary><code>contrast_ratio</code> — Return the WCAG contrast ratio between two colours.</summary>

```python
contrast_ratio(color: 'str', background: 'str') -> 'float'
```

```text
Return the WCAG contrast ratio between two colours.

The ratio is symmetric and ranges from ``1.0`` (identical colours) to
``21.0`` (black against white). WCAG 2.1 AA asks for at least ``4.5`` for
normal text; `MIN_CONTRAST_RATIO` carries that threshold.

Args:
    color: Foreground colour as a ``#RGB`` or ``#RRGGBB`` string.
    background: Background colour, same format.

Returns:
    The contrast ratio, ``(lighter + 0.05) / (darker + 0.05)``.

Raises:
    ValueError: If either argument is not a hex colour string.

Example:
    >>> round(contrast_ratio("#FFFFFF", "#000000"), 1)
    21.0
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/palette.py#L128)

</details>

<a id="min_contrast_ratio"></a>
<details>
<summary><code>MIN_CONTRAST_RATIO</code> — Final[float]</summary>

```python
MIN_CONTRAST_RATIO: Final[float] = 4.5
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/palette.py#L36)

</details>

<a id="palette"></a>
<details>
<summary><code>Palette</code> — An immutable figure theme: qualitative series colours plus semantic roles.</summary>

```python
Palette(name: 'str', series: 'tuple[str, ...]', background: 'str', foreground: 'str', grid: 'str') -> None
```

```text
An immutable figure theme: qualitative series colours plus semantic roles.

Attributes:
    name: The key this palette is registered under.
    series: Ordered qualitative colours for successive data series, as
        uppercase ``#RRGGBB`` strings. Every one of them clears
        `MIN_CONTRAST_RATIO` against `background`.
    background: Figure and axes face colour.
    foreground: Text, tick, label and spine colour.
    grid: Grid-line colour — decoration, deliberately lower contrast than
        `foreground`.
```

**Fields:** `name`, `series`, `background`, `foreground`, `grid`.

**Public methods:** `rc_params`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/palette.py#L210)

</details>

<a id="palette"></a>
<details>
<summary><code>palette</code> — Look up a registered palette by name.</summary>

```python
palette(name: 'str') -> 'Palette'
```

```text
Look up a registered palette by name.

Args:
    name: A registered palette name — see `palette_names`.

Returns:
    The shared, frozen `Palette` for that name. Repeated lookups return
    the same instance; it cannot be mutated, so sharing is safe.

Raises:
    ValueError: If `name` is not registered. The message lists the names
        that are.

Example:
    >>> palette("dark").background
    '#000000'
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/palette.py#L308)

</details>

<a id="palette_names"></a>
<details>
<summary><code>palette_names</code> — Return the names of every registered palette, in registration order.</summary>

```python
palette_names() -> 'tuple[str, ...]'
```

```text
Return the names of every registered palette, in registration order.

Returns:
    The registry keys, suitable for offering to a user as choices.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/palette.py#L299)

</details>

<a id="m-_version"></a>
### `_version` — Package and Python version constants

_Layer 1._  `from emmykit._version import …`

Single source of truth for `emmykit.__version__` (read by hatchling at build-time) and the supported `PY_VERSION` floor.

<a id="py_version"></a>
<details>
<summary><code>PY_VERSION</code> — Final[float]</summary>

```python
PY_VERSION: Final[float] = 3.12
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/_version.py#L13)

</details>

<a id="m-options"></a>
### `options` — Options dataclasses for configuration

_Layer 1._  `from emmykit.options import …`

Aggregated runtime/plot-time settings passed through downstream APIs as a single object.

<a id="options"></a>
<details>
<summary><code>Options</code> — Class that has all global options in one place.</summary>

```python
Options() -> 'None'
```

```text
Class that has all global options in one place.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/options.py#L19)

</details>

<a id="plotoptions"></a>
<details>
<summary><code>PlotOptions</code> — Global figure options.</summary>

```python
PlotOptions() -> 'None'
```

```text
Global figure options.

Colour lives in `emmykit.palette` and is reached through the `palette`
attribute; the `colors` / `lightcolors` / `background_color` / `text_color`
attributes remain as read-only views onto it, so existing callers are
unaffected. Figure geometry (`myfigsize`, `fsize`, `dpi_choice`) and the
marker/linestyle cycles stay here — they are not colour.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/options.py#L31)

</details>

<a id="m-inflect_utils"></a>
### `inflect_utils` — Grammar + pluralization helpers

_Layer 1._  `from emmykit.inflect_utils import …`

Lazy wrapper over the `inflect` package with a stdlib-only fallback table for common nouns when the extra isn't installed.

<a id="inflectengine"></a>
<details>
<summary><code>InflectEngine</code> — Protocol for the 'inflect' library's engine interface.</summary>

```python
InflectEngine(*args, **kwargs)
```

```text
Protocol for the 'inflect' library's engine interface.
```

**Public methods:** `plural`, `plural_noun`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/inflect_utils.py#L8)

</details>

<a id="my_plural"></a>
<details>
<summary><code>my_plural</code> — Return a pluralized version of 'word' preceded by 'n'.</summary>

```python
my_plural(n: 'int', word: 'str') -> 'str'
```

```text
Return a pluralized version of 'word' preceded by 'n'.

Behavior:
- If the open-source 'inflect' library is available, use it for pluralization.
- Otherwise, fall back to a casefold()-based irregulars table, some uncountables,
  and a small set of morphological rules.

Examples (fallback behavior):
    1 millennium -> "1 millennium"
    2 millennium -> "2 millennia"
    2 millenium  -> "2 millennia"   # (handles the common misspelling too)

Args:
    n:    The quantity of the item.
    word: The singular form of the item.

Returns:
    A string in the format "{n} {pluralized_word}".

Raises:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/inflect_utils.py#L42)

</details>

<a id="m-logging_utils"></a>
### `logging_utils` — Logging configuration and custom handlers

_Layer 1._  `from emmykit.logging_utils import …`

Drop-in `configure_logging`, level-filtering handlers, an in-memory ring-buffer handler, and an introspection helper (`return_method_name`) used throughout the package for self-naming log messages.

<a id="configure_logging"></a>
<details>
<summary><code>configure_logging</code> — Configure logging to write to files and stdout/stderr, and return a MemoryHandler to capture ERROR logs for later (dupl…</summary>

```python
configure_logging(basename: 'str', log_level: 'int | str' = 20, rawlog: 'bool' = False, logdir: 'str | os.PathLike[str]' = '') -> 'MemoryHandler | None'
```

```text
Configure logging to write to files and stdout/stderr, and return a MemoryHandler to capture ERROR logs for later (duplicate) printing.

Args:
    basename : Base name for the log files.
    log_level: Logging level (default: logging.INFO).
    rawlog   : If True, use a simple log format without timestamps or levels.
    logdir   : Directory to store log files. Defaults to './logs'.

Returns:
    MemoryHandler instance capturing ERROR logs, or None if log files couldn't be created.

Raises:
    None (file creation errors are caught and logged to stdout).
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L63)

</details>

<a id="fallback_logging_config"></a>
<details>
<summary><code>fallback_logging_config</code> — Configure the root logger with a basic configuration if no handlers are set.</summary>

```python
fallback_logging_config(log_level: 'int | str' = 20, rawlog: 'bool' = False) -> 'None'
```

```text
Configure the root logger with a basic configuration if no handlers are set.
Run this at the start of functions which might be run without first configuring logging.

Args:
    level  : The logging level to set. Defaults to logging.INFO.
    rawlog : If True, use a simple log format without timestamps or levels.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L46)

</details>

<a id="flushingstreamhandler"></a>
<details>
<summary><code>FlushingStreamHandler</code> — A logging handler that flushes the stream after emitting each log so the logs are immediately visible.</summary>

```python
FlushingStreamHandler(stream=None)
```

```text
A logging handler that flushes the stream after emitting each log so the logs are immediately visible.
```

**Public methods:** `acquire`, `addFilter`, `close`, `createLock`, `emit`, `filter`, `flush`, `format`, `get_name`, `handle`, `handleError`, `release`, `removeFilter`, `setFormatter`, `setLevel`, `setStream`, `set_name`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L25)

</details>

<a id="maxlevelfilter"></a>
<details>
<summary><code>MaxLevelFilter</code> — A logging filter that only allows logs up to a certain level to pass through, so that error messages aren't printed mul…</summary>

```python
MaxLevelFilter(max_level: 'int') -> 'None'
```

```text
A logging filter that only allows logs up to a certain level to pass through, so that error messages aren't printed multiple times.
```

**Public methods:** `filter`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L35)

</details>

<a id="memoryhandler"></a>
<details>
<summary><code>MemoryHandler</code> — A logging handler that stores logs in memory so the errors can be printed at the end.</summary>

```python
MemoryHandler(level: 'int' = 40) -> 'None'
```

```text
A logging handler that stores logs in memory so the errors can be printed at the end.
```

**Public methods:** `acquire`, `addFilter`, `close`, `createLock`, `emit`, `filter`, `flush`, `format`, `get_name`, `handle`, `handleError`, `release`, `removeFilter`, `setFormatter`, `setLevel`, `set_name`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L12)

</details>

<a id="print_all_errors"></a>
<details>
<summary><code>print_all_errors</code> — Print all the captured error messages.</summary>

```python
print_all_errors(memory_handler: 'MemoryHandler', rawlog: 'bool' = False) -> 'None'
```

```text
Print all the captured error messages.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L147)

</details>

<a id="return_method_name"></a>
<details>
<summary><code>return_method_name</code> — Return the caller's qualified method/function name.</summary>

```python
return_method_name(levels_up: 'int' = 1) -> 'str'
```

```text
Return the caller's qualified method/function name.

- For instance methods: ClassName.method
- For classmethods:     ClassName.method
- For staticmethods:    ClassName.method on Python >= 3.11 (via co_qualname),
                        otherwise just 'method' (class is not recoverable without heuristics)
- For functions:        function

Args:
    levels_up: How many frames up to inspect (1 = caller). If greater than
               the stack depth, the highest available frame is used.

Returns:
    The current method name as a string, formatted as 'ClassName.method' or 'function'.

Raises:
    None: This function does not raise exceptions, but it may log warnings
          if sys._getframe or inspect fails.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/logging_utils.py#L157)

</details>

<a id="m-paths_ensure"></a>
### `paths_ensure` — Path normalization

_Layer 1._  `from emmykit.paths_ensure import …`

Leaf helper that coerces `os.PathLike` / `str` arguments into resolved `Path` objects.

<a id="ensure_path"></a>
<details>
<summary><code>ensure_path</code> — Ensure that the path is a Path. If not, make it a Path.</summary>

```python
ensure_path(path: 'str | os.PathLike[str]', absolute: 'bool' = True) -> 'Path'
```

```text
Ensure that the path is a Path. If not, make it a Path.

Args:
    path:     The path to ensure is a Path object.
    absolute: If True (default), return an absolute path without resolving symlinks.

Returns:
    A Path object (expanded for "~"). If absolute=True, it's absolute; otherwise it may be relative.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/paths_ensure.py#L10)

</details>

<a id="m-safe_paths"></a>
### `safe_paths` — Exception-swallowing filesystem queries

_Layer 2._  `from emmykit.safe_paths import …`

`safe_*` wrappers around `os.stat`/`Path.exists`/`is_file`/`is_dir` that never raise, plus `ensure_file`/`ensure_dir` builders that compose on top of them.

<a id="ensure_dir"></a>
<details>
<summary><code>ensure_dir</code> — Ensure that the given path is an existing directory and return it as a Path object.</summary>

```python
ensure_dir(path: 'str | os.PathLike[str]', allow_symlink: 'bool' = True, follow_symlinks: 'bool' = True) -> 'Path'
```

```text
Ensure that the given path is an existing directory and return it as a Path object.

Args:
    path:            The path to check.
    allow_symlink:   If False, raise an exception if the path is a symlink.
    follow_symlinks: If False, do not follow symlinks when checking if it's a directory.
                     If False, symlinks aren't considered directories (even if allow_symlink=True).
                     With follow_symlinks=False, attribute reads (size/mtime/etc.) also don't
                     follow symlinks.

Returns:
    A Path object representing the directory.

Raises:
    FileNotFoundError:  If the directory does not exist.
    NotADirectoryError: If the path exists but is not a directory.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L63)

</details>

<a id="ensure_file"></a>
<details>
<summary><code>ensure_file</code> — Ensure that the given path is an existing file and return it as a Path object.</summary>

```python
ensure_file(path: 'str | os.PathLike[str]', raise_on_empty: 'bool' = False, allow_symlink: 'bool' = True, follow_symlinks: 'bool' = True, verbose: 'bool' = True) -> 'Path'
```

```text
Ensure that the given path is an existing file and return it as a Path object.

Args:
    path:            The path to check.
    raise_on_empty:  If True,  raise an exception if the file is empty.
    allow_symlink:   If False, raise an exception if the path is a symlink.
    follow_symlinks: If False, do not follow symlinks when checking if it's a file.
                     If False, symlinks aren't considered files (even if allow_symlink=True).
                     With follow_symlinks=False, attribute reads (size/mtime/etc.) also don't
                     follow symlinks.
    verbose:         If True (default), log a warning if the file is empty or size is unknown.

Returns:
    A Path object representing the file.

Raises:
    FileNotFoundError: If the file does not exist.
    IsADirectoryError: If the path exists but is a directory.
    ValueError:        If the path exists but is not a regular file, or if symlinks are not allowed.
    ValueError:        If raise_on_empty is True and the file is empty (or bad permissions, etc.)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L14)

</details>

<a id="safe_ctime"></a>
<details>
<summary><code>safe_ctime</code> — Return ctime (seconds float or ns int) or None on errors.</summary>

```python
safe_ctime(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True, ns: 'bool' = False) -> 'int | float | None'
```

```text
Return ctime (seconds float or ns int) or None on errors.
Note: On POSIX, ctime == inode *change* time, not creation time.
      On Windows, ctime is the file *creation* time.

Args:
    path:            The file or directory path to stat().st_ctime
    follow_symlinks: Whether to follow symlinks (default: True).
                     If true, uses Path.stat() else Path.lstat().
    ns:              Whether to return the result in nanoseconds (default: False).

Returns:
    The ctime of the file in seconds or nanoseconds, or None if an error occurred.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L296)

</details>

<a id="safe_exists"></a>
<details>
<summary><code>safe_exists</code> — Like Path.exists()/os.path.lexists(), but doesn't raise on permission/loop errors.</summary>

```python
safe_exists(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True) -> 'bool'
```

```text
Like Path.exists()/os.path.lexists(), but doesn't raise on permission/loop errors.

Args:
    path:            The path to check.
    follow_symlinks: If False, do not follow symlinks when checking if it exists.

Returns:
    True if the path appears to exist (respecting follow_symlinks), False if it doesn't.
    For certain access/loop issues, returns True to avoid misclassifying as 'missing'.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L122)

</details>

<a id="safe_is_dir"></a>
<details>
<summary><code>safe_is_dir</code> — Like Path.is_dir(), but returns False on permission errors instead of raising.</summary>

```python
safe_is_dir(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True) -> 'bool'
```

```text
Like Path.is_dir(), but returns False on permission errors instead of raising.
Uses _is_dir() for pre-3.13 compatibility and no-follow mode.

Args:
    path:            The file or directory path to check.
    follow_symlinks: Whether to follow symlinks (default: True).

Returns:
    True if the path is a directory, False otherwise.

Raises:
    Intentionally designed to catch PermissionError, FileNotFoundError,
    some OSError variations. But not all.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L194)

</details>

<a id="safe_is_file"></a>
<details>
<summary><code>safe_is_file</code> — Like Path.is_file(), but returns False on permission errors instead of raising.</summary>

```python
safe_is_file(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True) -> 'bool'
```

```text
Like Path.is_file(), but returns False on permission errors instead of raising.
Uses _is_file() for pre-3.13 compatibility and no-follow mode.

Args:
    path:            The file or directory path to check.
    follow_symlinks: Whether to follow symlinks (default: True).

Returns:
    True if the path is a file, False otherwise.

Raises:
    Intentionally designed to catch PermissionError, FileNotFoundError,
    some OSError variations. But not all.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L162)

</details>

<a id="safe_mtime"></a>
<details>
<summary><code>safe_mtime</code> — Return mtime (seconds float or ns int) or None on errors.</summary>

```python
safe_mtime(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True, ns: 'bool' = False) -> 'int | float | None'
```

```text
Return mtime (seconds float or ns int) or None on errors.

Args:
    path:            The file or directory path to stat().st_mtime
    follow_symlinks: Whether to follow symlinks (default: True).
                     If true, uses Path.stat() else Path.lstat().
    ns:              Whether to return the result in nanoseconds (default: False).

Returns:
    The mtime of the file in seconds or nanoseconds, or None if an error occurred.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L276)

</details>

<a id="safe_size"></a>
<details>
<summary><code>safe_size</code> — Like Path.stat().st_size, but returns None on permission/missing/loop errors.</summary>

```python
safe_size(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True) -> 'int | None'
```

```text
Like Path.stat().st_size, but returns None on permission/missing/loop errors.

Args:
    path:            The file or directory path to stat().st_size
    follow_symlinks: Whether to follow symlinks (default: True).
                     If true, uses Path.stat() else Path.lstat().

Returns:
    The size of the file in bytes or None if an error occurred.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L260)

</details>

<a id="safe_stat"></a>
<details>
<summary><code>safe_stat</code> — Like Path.stat()/lstat(), but returns None on permission/missing/loop errors.</summary>

```python
safe_stat(path: 'str | os.PathLike[str]', follow_symlinks: 'bool' = True) -> 'os.stat_result | None'
```

```text
Like Path.stat()/lstat(), but returns None on permission/missing/loop errors.

Args:
    path:            The file or directory path to stat.
    follow_symlinks: Whether to follow symlinks (default: True).
                     If true, uses Path.stat() else Path.lstat().

Returns:
    An os.stat_result object or None if an error occurred.

Raises:
    Intentionally designed to catch PermissionError, FileNotFoundError,
    some OSError variations. But not all.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/safe_paths.py#L226)

</details>

<a id="m-file_io"></a>
### `file_io` — Atomic file-write helper

_Layer 2._  `from emmykit.file_io import …`

`my_atomic_write` — lazy `atomicwrites` + `filelock` wrapper that lets you write text to a path with cross-process safety.

<a id="my_atomic_write"></a>
<details>
<summary><code>my_atomic_write</code> — Atomically write 'data' to 'filepath' with an advisory lock.</summary>

```python
my_atomic_write(filepath: 'str | Path | os.PathLike[str]', data: 'str | bytes | bytearray', write_mode: "Literal['w', 'a']", encoding: 'str' = 'utf-8', lock_timeout: 'float | None' = None) -> 'None'
```

```text
Atomically write 'data' to 'filepath' with an advisory lock.

- If write_mode="a" and file exists, data is appended.
- If write_mode="a" and file does *not* exist, file is created.
- A '.lock' file beside 'filepath' prevents concurrent writers.

Args:
    filepath:     Path to the file to write.
    data:         Data to write (str or bytes).
    write_mode:   "w" for overwrite, "a" for append.
    encoding:     Encoding to use for text data (default: DEFAULT_ENCODING).
    lock_timeout: Maximum time to wait for the lock (default: None, meaning wait indefinitely).

Returns:
    None: The file is written atomically.

Raises:
    RuntimeError: If the lock cannot be acquired within the specified timeout.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/file_io.py#L13)

</details>

<a id="m-io_subprocess"></a>
### `io_subprocess` — Subprocess wrappers + critical-error reporter

_Layer 3._  `from emmykit.io_subprocess import …`

`my_fopen` (smart-encoding text-file opener), `my_popen` (subprocess with timeout + capture), `my_critical_error` (logging + traceback + raise pattern), and the `MyPopenResult` data carrier.

<a id="my_critical_error"></a>
<details>
<summary><code>my_critical_error</code> — Log a critical error message and either exit the program or enter a breakpoint.</summary>

```python
my_critical_error(message: 'str' = 'A critical error occurred.', choose_breakpoint: 'bool' = False, exit_code: 'int' = 1) -> 'None'
```

```text
Log a critical error message and either exit the program or enter a breakpoint.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/io_subprocess.py#L20)

</details>

<a id="my_fopen"></a>
<details>
<summary><code>my_fopen</code> — Attempt to read a text file with various encodings and return the file content if successful. Optionally, specify numli…</summary>

```python
my_fopen(file_path: 'str | os.PathLike[str]', suppress_errors: 'bool' = False, rawlog: 'bool' = False, numlines: 'int | None' = None, verbose: 'bool' = True) -> 'str | None'
```

```text
Attempt to read a text file with various encodings and return the file content if successful. Optionally, specify numlines to limit the number of lines read.

Args:
    file_path:       Path to the file to read.
    suppress_errors: If True, suppress error messages by logging them as info instead of as error.
    rawlog:          If True, use a simple log format without timestamps or levels.
    numlines:        If specified, read only this many lines from the file and return them as a string.
    verbose:         If True, log messages about the file reading process (default: True).

Returns:
    The content of the file as a string, or:
    Returns None:
     - if the file does not exist
     - is empty
     - is a non-text file (video, audio, image, archive)
     - cannot be read with any of the specified encodings
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/io_subprocess.py#L124)

</details>

<a id="my_popen"></a>
<details>
<summary><code>my_popen</code> — Execute a command using subprocess.Popen and capture the output line by line using threads.</summary>

```python
my_popen(command_list: 'list', suppress_info: 'bool' = False, suppress_error: 'bool' = False) -> 'MyPopenResult'
```

```text
Execute a command using subprocess.Popen and capture the output line by line using threads.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/io_subprocess.py#L49)

</details>

<a id="mypopenresult"></a>
<details>
<summary><code>MyPopenResult</code> — A class to store the results of a customized subprocess.Popen call.</summary>

```python
MyPopenResult(stdout: 'str', stderr: 'str', returncode: 'int') -> 'None'
```

```text
A class to store the results of a customized subprocess.Popen call.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/io_subprocess.py#L39)

</details>

<a id="m-prompts"></a>
### `prompts` — Interactive Y/N + multi-choice prompts

_Layer 4._  `from emmykit.prompts import …`

Two small helpers that funnel through `input()` with consistent retry behavior.

<a id="prompt_then_choose"></a>
<details>
<summary><code>prompt_then_choose</code> — Show a numbered list of choices and prompt the user to select one.</summary>

```python
prompt_then_choose(prompt: 'str', choices: 'list[str]', default: 'str | None' = None) -> 'str'
```

```text
Show a numbered list of choices and prompt the user to select one.

Args:
    prompt:  The message to display before the choices.
    choices: A list of choices to present to the user.
    default: The default choice to return if the user presses Enter without inputting a choice.

Returns:
    str : The selected choice from the list (or the default if provided).

Raises:
    None: If the user input is invalid, it will keep prompting until a valid choice is made.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/prompts.py#L15)

</details>

<a id="prompt_then_confirm"></a>
<details>
<summary><code>prompt_then_confirm</code> — Prompt the user with the given message and return True if the user enters 'yes', False otherwise.</summary>

```python
prompt_then_confirm(prompt: 'str') -> 'bool'
```

```text
Prompt the user with the given message and return True if the user enters 'yes', False otherwise.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/prompts.py#L10)

</details>

<a id="m-introspection"></a>
### `introspection` — AST + source-code reflection

_Layer 4._  `from emmykit.introspection import …`

Render a function's source with original whitespace, parse module-level constants out of a file, normalize objects into dicts, compile source snippets in-memory, and conditionally read-and-eval embedded scripts.

<a id="compile_code"></a>
<details>
<summary><code>compile_code</code> — Attempt to compile the given source code in 'exec' mode.</summary>

```python
compile_code(source_or_filepath: 'str | os.PathLike[str]', force_source: 'bool' = False) -> 'bool'
```

```text
Attempt to compile the given source code in 'exec' mode.
If 'source_or_filepath' is a file path, read its contents first.

Args:
    source_or_filepath: The source code string or file path to compile.
    force_source:       If True, treat 'source_or_filepath' as a source code string even if it looks like a file path.

Returns:
    True if compilation succeeds, False if it fails with a SyntaxError or other exception

Raises:
    SyntaxError: If the source code has a syntax error, it will be logged and False is returned.
    TypeError:   If 'source_or_filepath' is not a string or a file path.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/introspection.py#L427)

</details>

<a id="if_filepath_then_read"></a>
<details>
<summary><code>if_filepath_then_read</code> — If given a path, return the file's text; otherwise return the string itself.</summary>

```python
if_filepath_then_read(input_string_or_filepath: 'str | os.PathLike[str]', force_string: 'bool' = False) -> 'str'
```

```text
If given a path, return the file's text; otherwise return the string itself.

Behavior:
- If a real PathLike is passed and 'force_string' is False:
    * If the path does not exist → raise FileNotFoundError.
    * If the path exists but is not a regular file → raise IsADirectoryError.
    * If it is a file → return its contents. On permission or decoding errors,
      log and return "".
    * A race after the existence check may still raise FileNotFoundError (re-raised).
- If a string is passed:
    * If it contains a newline or is longer than 4096 chars → treat as literal and return as-is.
    * Else, if it names an existing file and 'force_string' is False → read and return
      contents; on read errors (not found/permission/decoding), log and return "".
    * Else → return the string as-is.
- If 'force_string' is True and a PathLike is passed → TypeError.

Args:
    input_string_or_filepath: A string to return as-is, or a path to read.
    force_string:             If True, always treat the input as a string literal (PathLike
                              inputs are rejected with TypeError).

Returns:
    The file contents (when reading a file) or the input string/literal path.

Raises:
    TypeError:         If a PathLike is given with 'force_string=True', or if the input
                       is neither str nor PathLike.
    FileNotFoundError: When a PathLike is given and the path does not exist.
    IsADirectoryError: When a PathLike is given and the path is not a regular file.

Notes:
    For string inputs that look like paths, missing files do not raise; the
    string is returned unchanged. Permission/decoding errors are logged and
    result in an empty string.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/introspection.py#L321)

</details>

<a id="load_ast_var"></a>
<details>
<summary><code>load_ast_var</code> — Load a top-level literal Python variable from a module without executing it.</summary>

```python
load_ast_var(var_name: 'str', script_path: 'str | os.PathLike[str]', rawlog: 'bool' = False) -> 'Any | None'
```

```text
Load a top-level literal Python variable from a module without executing it.

Args:
    var_name:    The name of the global variable to extract from the script.
    script_path: The path to the Python script file from which to extract the variable.
    rawlog:      If True, use a simple log format without timestamps or levels.

Returns:
    The value of the variable if found, or None.

Raises:
    FileNotFoundError: If the script file does not exist.
    AttributeError:    If the variable is not found at the top level of the script.
    ValueError:        If the value of the variable cannot be evaluated as a literal expression.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/introspection.py#L20)

</details>

<a id="normalize_to_dict"></a>
<details>
<summary><code>normalize_to_dict</code> — Ensure that 'value' is a dict. If it's a JSON-style string, try to parse it. Otherwise, log a warning and return an emp…</summary>

```python
normalize_to_dict(value: 'Any', var_name: 'str', script_path: 'str | os.PathLike[str]') -> 'dict'
```

```text
Ensure that 'value' is a dict. If it's a JSON-style string, try to parse it. Otherwise, log a warning and return an empty dict.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/introspection.py#L300)

</details>

<a id="show_function_source"></a>
<details>
<summary><code>show_function_source</code> — Print the full source text of a Python function (including comments,</summary>

```python
show_function_source(target: 'object | str', *, unwrap: 'bool' = True, output: 'str | os.PathLike[str] | TextIO | None' = None) -> 'str'
```

```text
Print the full source text of a Python function (including comments,
docstrings, decorators, and type hints).

Args:
    target: A function *name* (string) or a function object.
            If a string is given, it's resolved in the caller's scope, then
            in builtins, then as a dotted path via pydoc.locate (e.g. 'pkg.mod.func').
    unwrap: If True, attempt to unwrap decorated functions to show
            the original implementation. Defaults to True.
    output: A file-like object to write to (optional, defaults to sys.stdout). More details:

Details on the "output" argument:
- None -> sys.stdout
- TextIO (e.g., sys.stdout, an open text file, StringIO) -> used as-is
         (must be opened in *text* mode; binary streams are rejected)
- str | os.PathLike[str] -> treated as a path:
         * '~' is expanded
         * parent directories are created (parents=True, exist_ok=True)
         * file is opened in append mode ('a', UTF-8)
         * a one-line note is written indicating whether we created or appended
Notes:
- A trailing newline is added if the source text doesn't already end with one.
- If you pass the string "-" as the output path, it is treated as stdout.
- If the given path is an existing directory, an IsADirectoryError is raised.
- If you pass a binary stream, a TypeError is raised.

Returns:
    str: The source text that was printed.

Raises:
    NameError: If a string cannot be resolved to an object.
    OSError:   If source is unavailable (e.g., built-in/C extension or optimized away).
    TypeError: If the resolved object isn't suitable for source extraction.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/introspection.py#L133)

</details>

<a id="m-humanize"></a>
### `humanize` — Human-readable number formatting

_Layer 4._  `from emmykit.humanize import …`

Any quantity with an SI or IEC prefix (`3.2 ZJ`, `2.0 cm`, `1.0 GiB`), one shared prefix for a whole set of values (`choose_prefix`, for axis and colorbar labels), scientific-notation exponents, and away-from-zero rounding (lazy numpy).

<a id="bytes"></a>
<details>
<summary><code>BYTES</code> — Unit</summary>

```python
BYTES = Unit(symbol='B', singular='byte', plural='bytes')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L29)

</details>

<a id="choose_prefix"></a>
<details>
<summary><code>choose_prefix</code> — Pick one prefix for a whole set of values, e.g. every tick on one axis.</summary>

```python
choose_prefix(values: 'Iterable[float | int]', unit: 'Unit | None' = None, *, system: 'str' = 'si', mode: 'str' = 'engineering', ascii_micro: 'bool' = False) -> 'tuple[str, float]'
```

```text
Pick one prefix for a whole set of values, e.g. every tick on one axis.

Formatting axis ticks one at a time gives "1 mm", "2 mm", "1 cm" — three
scales on one axis. Instead, label the axis once with `<symbol><unit>` and
divide every tick by the returned factor.

The choice is driven by the largest finite magnitude in `values`; NaN and
infinity are ignored, and an empty or all-zero set yields the unprefixed
scale.

Args:
    values:      Iterable of values, consumed once. May contain NaN/inf.
    unit:        The unit the values are expressed in. It does not affect
                 the chosen prefix — it is accepted so call sites read as
                 `choose_prefix(ticks, METERS)`, and so passing something
                 that is not a `Unit` fails immediately.
    system:      "si" for powers of 1000, "iec" for powers of 1024.
    mode:        "engineering" for powers of 1000 only, or "full_si" to
                 additionally allow deci, centi, deka and hecto.
    ascii_micro: Emit "u" instead of "µ" for micro.

Returns:
    A (prefix symbol, divisor) pair. The unprefixed scale is ("", 1.0).

Raises:
    TypeError:  If `unit` is neither None nor a `Unit`.
    ValueError: If `system` or `mode` is unknown, or submultiples are
        requested for the binary system.

Example:
    >>> choose_prefix([0.001, 0.002, 0.011], METERS, mode="full_si")
    ('c', 0.01)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L180)

</details>

<a id="grams"></a>
<details>
<summary><code>GRAMS</code> — Unit</summary>

```python
GRAMS = Unit(symbol='g', singular='gram', plural='grams')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L31)

</details>

<a id="hertz"></a>
<details>
<summary><code>HERTZ</code> — Unit</summary>

```python
HERTZ = Unit(symbol='Hz', singular='hertz', plural='hertz')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L35)

</details>

<a id="human_bytesize"></a>
<details>
<summary><code>human_bytesize</code> — Formats a byte count into a human-readable string.</summary>

```python
human_bytesize(num: 'float | int | None', *, suffix: 'str' = 'B', si: 'bool' = False, precision: 'int' = 1, space: 'bool' = True, trim_trailing_zeros: 'bool' = False, long_units: 'bool' = False) -> 'str'
```

```text
Formats a byte count into a human-readable string.

Args:
    num:                 Size in bytes. Negative values are preserved with a leading minus.
                         If None, returns "None".
    suffix:              Unit suffix appended after the prefix (defaults to "B"). If long_units is True and
                         suffix is "B", "bytes" is appended in the output. Otherwise, the suffix is appended to the long name.
    si:                  If True, use powers of 1000 with SI prefixes (k, M, G, ... up to R, Q).
                         If False, use powers of 1024 with IEC prefixes (Ki, Mi, Gi, ... up to Ri, Qi).
    precision:           If >= 0, digits to show after the decimal point.
                         If < 0, constrains the total returned string length to `-precision`
                         (width-constrained mode; `long_units` is forced False).
    space:               If True, inserts a space between the number and the unit (ignored when long_units is True).
    trim_trailing_zeros: If True, removes trailing zeros and any dangling decimal point.
    long_units:          If True, spell out unit names ("bytes", "kibibytes", ... "quebibytes"/"quettabytes").

Returns:
    A concise string such as "1.5KiB", "1.5 kB", or "1.5 megabytes" depending on options.
    If num is None, returns "None".
    Handles negative values with a leading minus sign and units up to "quebibytes" (2^100 = 1024^10 bytes) for IEC,
    or "quettabytes" (10^30 bytes) for SI.

Raises:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L415)

</details>

<a id="human_quantity"></a>
<details>
<summary><code>human_quantity</code> — Format one value with the prefix that scales it into [1, step).</summary>

```python
human_quantity(num: 'float | int | None', unit: 'Unit', *, system: 'str' = 'si', mode: 'str' = 'engineering', precision: 'int' = 1, space: 'bool' = True, trim_trailing_zeros: 'bool' = False, long_units: 'bool' = False, ascii_micro: 'bool' = False) -> 'str'
```

```text
Format one value with the prefix that scales it into [1, step).

Args:
    num:                 The value. Negative values keep a leading minus.
                         If None, returns "None". NaN and infinity are
                         rendered unprefixed ("nan m", "-inf m").
    unit:                Unit to append, e.g. `METERS` or `JOULES`.
    system:              "si" for powers of 1000 with SI prefixes, or "iec"
                         for powers of 1024 with binary prefixes. The binary
                         system has no submultiples, so values below 1 stay
                         unprefixed there.
    mode:                "engineering" (default) restricts prefixes to powers
                         of 1000, so 0.02 m is "20.0 mm". "full_si" also
                         allows deci, centi, deka and hecto, so 0.02 m is
                         "2.0 cm".
    precision:           If >= 0, digits after the decimal point.
                         If < 0, constrains the total returned string length
                         to `-precision` (width-constrained mode;
                         `long_units` is ignored).
    space:               Insert a space between number and unit (ignored when
                         `long_units` is True, which always uses one space).
    trim_trailing_zeros: Remove trailing zeros and any dangling decimal point.
    long_units:          Spell prefix and unit out ("1.5 kilometers",
                         "1.5 kibibytes"). The unit's singular form is used
                         when the formatted number reads exactly "1".
    ascii_micro:         Emit "u" instead of "µ" for micro.

Returns:
    A string such as "3.2 ZJ", "2.0 cm", "1.5 KiB" or "1.5 kilometers".

Raises:
    TypeError:  If `unit` is not a `Unit`.
    ValueError: If `system` or `mode` is unknown, if submultiples are
        requested for the binary system, or if a width-constrained request
        cannot fit.

Example:
    >>> human_quantity(3.2e21, JOULES)
    '3.2 ZJ'
    >>> human_quantity(0.02, METERS, mode="full_si")
    '2.0 cm'
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L358)

</details>

<a id="joules"></a>
<details>
<summary><code>JOULES</code> — Unit</summary>

```python
JOULES = Unit(symbol='J', singular='joule', plural='joules')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L33)

</details>

<a id="meters"></a>
<details>
<summary><code>METERS</code> — Unit</summary>

```python
METERS = Unit(symbol='m', singular='meter', plural='meters')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L30)

</details>

<a id="round_out"></a>
<details>
<summary><code>round_out</code> — Round a number away from zero (i.e. rounds up for x>0 and down for x<0) to</summary>

```python
round_out(x: 'float', round_digits: 'int' = 3, max_digits: 'int' = 15) -> 'float'
```

```text
Round a number away from zero (i.e. rounds up for x>0 and down for x<0) to
the specified number of significant figures (defaults to 3).
If the number is smaller than 10^(-max_digits), it will be returned as is.
The max_digits parameter defaults to 15, but can be changed to a different value if needed.

Args:
    x:             The number to round.
    round_digits:  The number of significant figures to round to (default is 3).
    max_digits:    The maximum number of digits to consider for very small numbers (default is 15).

Returns:
    float: The rounded number, or the original number if it is smaller than 10^(-max_digits).
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L481)

</details>

<a id="sci_exp"></a>
<details>
<summary><code>sci_exp</code> — Return floor(log10(|x|)), clamped to -max_digits for very small |x|.</summary>

```python
sci_exp(x: 'float | int', max_digits: 'int' = 15) -> 'int'
```

```text
Return floor(log10(|x|)), clamped to -max_digits for very small |x|.
For x == 0, returns -max_digits.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L467)

</details>

<a id="seconds"></a>
<details>
<summary><code>SECONDS</code> — Unit</summary>

```python
SECONDS = Unit(symbol='s', singular='second', plural='seconds')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L32)

</details>

<a id="unit"></a>
<details>
<summary><code>Unit</code> — A unit of measurement, in the three spellings a formatter needs.</summary>

```python
Unit(symbol: 'str', singular: 'str', plural: 'str') -> None
```

```text
A unit of measurement, in the three spellings a formatter needs.

Long names cannot be derived from the symbol ("m" -> "meter"/"meters",
"Hz" -> "hertz"/"hertz"), so all three are carried explicitly.

Attributes:
    symbol:   Short symbol, appended after the prefix symbol ("m", "B", "Hz").
    singular: Long name used when the formatted number reads exactly "1".
    plural:   Long name used otherwise; equal to `singular` for units such as
              hertz that have no plural "s".
```

**Fields:** `symbol`, `singular`, `plural`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L11)

</details>

<a id="watts"></a>
<details>
<summary><code>WATTS</code> — Unit</summary>

```python
WATTS = Unit(symbol='W', singular='watt', plural='watts')
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/humanize.py#L34)

</details>

<a id="m-numeric_helpers"></a>
### `numeric_helpers` — Numeric parsing + unit-to-seconds conversion

_Layer 1._  `from emmykit.numeric_helpers import …`

Tiny helpers shared by `humanize` and `datetime_utils` so neither has to pull in the other.

<a id="is_float"></a>
<details>
<summary><code>is_float</code> — Check if a string can be parsed as a float.</summary>

```python
is_float(s: 'str') -> 'bool'
```

```text
Check if a string can be parsed as a float.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/numeric_helpers.py#L56)

</details>

<a id="seconds_in_unit"></a>
<details>
<summary><code>seconds_in_unit</code> — Return the number of seconds in a given time unit.</summary>

```python
seconds_in_unit(unit: 'str') -> 'float'
```

```text
Return the number of seconds in a given time unit.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/numeric_helpers.py#L49)

</details>

<a id="m-datetime_utils"></a>
### `datetime_utils` — Date / time parsing, formatting, timezone handling

_Layer 4._  `from emmykit.datetime_utils import …`

`parse_datetime` is the load-bearing dispatcher (handles ISO, JD/MJD, decimal years, dateutil fallbacks); supplemented by `AdaptiveDateFormatter` for matplotlib, `human_timespan` for durations, and a small zoo of tz/JD helpers.

<a id="adaptive_date_labels"></a>
<details>
<summary><code>adaptive_date_labels</code> — Format dates at the coarsest precision that produces unique labels.</summary>

```python
adaptive_date_labels(dates: "'Sequence[AnyDateTimeType]'", *, min_precision: 'int' = 0, max_precision: 'int' = 4, format_levels: "'list[str] | None'" = None) -> 'list[str]'
```

```text
Format dates at the coarsest precision that produces unique labels.

Given a sequence of dates, starts formatting at the coarsest level and
refines until all labels are unique or max_precision is reached.

Args:
    dates: Sequence of date values (datetime.datetime, numpy.datetime64,
        or matplotlib date floats).
    min_precision: Minimum precision level (default: Precision.YEAR).
        The formatter will never produce labels coarser than this.
    max_precision: Maximum precision level (default: Precision.SECOND).
        The formatter stops refining at this level even if labels collide.
    format_levels: Custom format strings for each level. Must have length
        >= max_precision + 1. Defaults to ADAPTIVE_FORMAT_LEVELS.

Returns:
    List of formatted date strings, one per input date. Empty strings
    for NaT/NaN values.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L667)

</details>

<a id="adaptivedateformatter"></a>
<details>
<summary><code>AdaptiveDateFormatter</code> — Matplotlib Formatter that auto-selects date label precision.</summary>

```python
AdaptiveDateFormatter(*, min_precision: 'int' = 0, max_precision: 'int' = 4, format_levels: "'list[str] | None'" = None) -> 'None'
```

```text
Matplotlib Formatter that auto-selects date label precision.

Uses adaptive disambiguation: labels start at the coarsest level and
refine until all tick labels are unique. Drop-in replacement for any
matplotlib axis formatter or colorbar formatter.

Args:
    min_precision: Minimum precision level (default: Precision.YEAR).
    max_precision: Maximum precision level (default: Precision.SECOND).
    format_levels: Custom format strings per level.

Example:
    >>> ax.xaxis.set_major_formatter(AdaptiveDateFormatter())
    >>> cbar.ax.yaxis.set_major_formatter(AdaptiveDateFormatter())
```

**Public methods:** `format_ticks`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L723)

</details>

<a id="anydatetimetype"></a>
<details>
<summary><code>AnyDateTimeType</code> — TypeAlias (62 chars)</summary>

```python
AnyDateTimeType: TypeAlias = 'str | float | int | np.datetime64 | pd.Timestamp | dt.datetime'
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L324)

</details>

<a id="decimal_year_to_datetime"></a>
<details>
<summary><code>decimal_year_to_datetime</code> — Convert a decimal year to a datetime object.</summary>

```python
decimal_year_to_datetime(dec: 'float', use_astropy: 'bool' = False) -> 'dt.datetime'
```

```text
Convert a decimal year to a datetime object.
If use_astropy is True, astropy.time is used for sub-second and leap-second–aware conversion.
Usage: new_datetime_datetime_object = decimal_year_to_datetime(2002.291)
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L282)

</details>

<a id="extract_timestamp"></a>
<details>
<summary><code>extract_timestamp</code> — Extract timestamp string (in format YYYYMMDD-HHMMSS) from the_string, or None if not found.</summary>

```python
extract_timestamp(the_string: 'str') -> 'str | None'
```

```text
Extract timestamp string (in format YYYYMMDD-HHMMSS) from the_string, or None if not found.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L122)

</details>

<a id="format_date_range"></a>
<details>
<summary><code>format_date_range</code> — Process a pair of datetime.datetime dates and produce a formatted date range string</summary>

```python
format_date_range(date1: 'dt.datetime', date2: 'dt.datetime | None' = None) -> 'str'
```

```text
Process a pair of datetime.datetime dates and produce a formatted date range string
where each date looks like 'Jan  7, 2025'. If date2 is not provided, it is set to date1.

Args:
    date1: The first date as a datetime.datetime object.
    date2: The second date as a datetime.datetime object. If None, defaults to date1.

Returns:
    A formatted string representing the date range, such as 'Jan  7, 2025' or 'Jan  7 - Feb  3, 2025' or 'Jan  7 - 15, 2025'.
    If both dates and times are the same, it returns just one date like 'Jan  7, 2025'.
    If both dates are the same but times are different, it returns a string like '06:04:02 - 19:05:39 on Jan  7, 2025'

Raises:
    ValueError: If either date1 or date2 is not a datetime.datetime object.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L64)

</details>

<a id="human_timespan"></a>
<details>
<summary><code>human_timespan</code> — Format a time span in seconds into a human-readable string.</summary>

```python
human_timespan(timespan: 'int | float') -> 'str'
```

```text
Format a time span in seconds into a human-readable string.
Negative values are treated as absolute.

Args:
    timespan: A float or int representing the time span in seconds.

Returns:
    A human-readable string describing the time span, such as
    "1 year, 2 weeks, 3 days, 4 hours, 5 minutes and 6.789 seconds".
    If the timespan is zero, returns "0 seconds".

Raises:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L15)

</details>

<a id="parse_datetime"></a>
<details>
<summary><code>parse_datetime</code> — Try parsing the given_date string or number into a datetime.datetime object in the specified timezone.</summary>

```python
parse_datetime(given_date: 'AnyDateTimeType', timezone: 'str | dt.tzinfo | None' = None, format_str: 'str | None' = None, should_convert: 'bool | None' = None) -> 'dt.datetime'
```

```text
Try parsing the given_date string or number into a datetime.datetime object in the specified timezone.

If "format_str" is provided, it will be used to parse the date string. These format types are accepted:
 - "seconds" or "milliseconds" indicating the number of seconds or milliseconds since an epoch (Unix epoch by default).
 - "YYYY-MM-DD" or similar ISO8601 formats such as "YYYY-MM-DDTHH:MM:SS", "MM/DD/YYYY", etc.
 - A custom string following this pattern: "units (optional: since/after epoch)", where "units" can be anything that the function seconds_in_unit() accepts (e.g. "days", "weeks", "months", etc.). The optional epoch time can be a string, float, int, numpy.datetime64, pandas.Timestamp, or datetime.datetime object. Example: "days since 1990", "milliseconds after J2000", "sidereal days since 2000-01-01", etc. If the epoch is not specified, it defaults to the Unix epoch (1970-01-01T00:00:00Z)

If a boolean "should_convert" is provided, it will override the default behavior of whether to convert the datetime to the specified timezone by shifting the clock or just attaching the timezone without shifting. If None, the function will determine this based on the type of given_date and format_str.

If a given_date starts with "JD" or "MJD", it will be treated as a Julian Date or Modified Julian Date, respectively.

Otherwise, if given_date is a float or int, treat it as a decimal year by default if format_str is not provided.

Any call that doesn't provide a timezone argument will default to UTC.
The timezone can be a datetime.tzinfo object or a string that can be converted to a ZoneInfo object (e.g. 'America/New_York').
If the given_date is an "aware" datetime.datetime object which already has a timezone attached, it will be converted to the specified timezone (which may involve changing its date and time if the specified timezone is different).
The timezone can also be a fixed‐offset like "+05:30" or "-04:00", or the string "Naive" to indicate that the datetime should be treated as a naive datetime (i.e. without any timezone information).

Accepts:
    'NOW' (case-insensitive) → current datetime
    strings in YYYY, YYYY-MM, YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, or other ISO8601 formats (e.g. '2002-10-18T07:00:00Z', '2002-10-18 07:00:00+00:00').
    If YYYY is provided, it will default to January 1st of that year at midnight.
    If YYYY-MM is provided, it will default to the first day of that month at midnight.
    If YYYY-MM-DD is provided, it will default to midnight on that day.
    fallback to dateutil.parser.parse for free-form strings ("18 Oct 2002", "March 5th, 2020", etc.)
    floats (e.g. 2002.29178082191777) or integer (e.g. 2002) → decimal year
    numpy.datetime64 objects (e.g. np.datetime64('2002-10-18T07:00:00'))
    pandas.Timestamp objects (e.g. pd.Timestamp('2002-10-18 07:00:00'))
    datetime.datetime objects (e.g. datetime.datetime(2002, 10, 18, 7, 0, 0))

Args:
    given_date:     The date to parse, which can be a string, float, int, numpy.datetime64,
                    pandas.Timestamp, or datetime.datetime object.
    timezone:       A string or datetime.tzinfo object representing the timezone to convert
                    the datetime to. If None, defaults to UTC.
    format_str:     A string indicating the format of the date. If None, the function will
                    try to infer the format from the given_date.
    should_convert: A boolean indicating whether to convert the datetime to the specified
                    timezone by shifting the clock (True) or just attaching the timezone
                    without shifting (False). If None, the function will determine this
                    based on the type of given_date and format_str.

Returns:
    datetime.datetime object in the specified timezone.
    Note that datetime.datetime objects cannot represent dates before 1 January 1, 0001 or after 31 December 9999.
    So dates outside this range will raise a ValueError. Future versions of this code may support a wider range of dates (like 44 BC, 44 BCE, etc.) using libraries like 'astropy.time': https://chatgpt.com/share/685c5157-5cac-8006-b68c-4a0731927a50
    However, this will require the function to return an 'astropy.time.Time' object instead of a 'datetime.datetime' object.

Raises:
    ValueError:  If the given_date cannot be parsed into a datetime object, or if the timezone is invalid.
    TypeError:   If the given_date is not a string, float, int, numpy.datetime64, pandas.Timestamp, or datetime.datetime object.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L393)

</details>

<a id="parse_timezone"></a>
<details>
<summary><code>parse_timezone</code> — Parse the given timezone string or tzinfo object into a datetime.tzinfo object.</summary>

```python
parse_timezone(tz_arg: 'str | dt.tzinfo | None' = None) -> 'dt.tzinfo | str'
```

```text
Parse the given timezone string or tzinfo object into a datetime.tzinfo object.
If tz_arg is None, return UTC timezone.
If tz_arg is a string, it can be in one of the following formats:
  - A fixed‐offset like: "+HH:MM", "+HHMM", "+H", "+Hh", "+HhMMm" (or minus variants).
     Examples: "+05:30", "-0530", "+5h", "-5h30m".
  - A string that can be converted to a ZoneInfo object (e.g. 'America/New_York').
  - A timezone abbreviation that maps to a known IANA zone name (e.g. 'EST', 'CET').
  - "Z", "UTC", or "GMT" (case‐insensitive) to represent UTC.
  - A string "Naive" to represent a naive datetime (no timezone).
If tz_arg is already a tzinfo object, return it as is.

Args:
    tz_arg : A timezone string, a datetime.tzinfo object, or None.

Returns:
    A datetime.tzinfo object representing the parsed timezone, or a string "Naive"
    if the input was "Naive".

Raises:
    ValueError if the string cannot be converted to a valid timezone.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L185)

</details>

<a id="precision"></a>
<details>
<summary><code>Precision</code> — Integer constants representing date-formatting precision levels.</summary>

```python
Precision()
```

```text
Integer constants representing date-formatting precision levels.

Levels are ordered from coarsest (YEAR=0) to finest (SECOND=4).
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/datetime_utils.py#L617)

</details>

<a id="m-json_io"></a>
### `json_io` — JSON serialization + dataclass conversion

_Layer 4._  `from emmykit.json_io import …`

`to_jsonable`/`from_jsonable` round-trip recursively-typed structures including `Path`, `datetime`, and dataclasses, with paired `save_options_to_json`/`load_options_from_json` helpers for `Options` objects.

<a id="builtin_json_tags"></a>
<details>
<summary><code>BUILTIN_JSON_TAGS</code> — Final[frozenset[str]] (16 items)</summary>

```python
BUILTIN_JSON_TAGS: Final[frozenset[str]] = frozenset({'bytearray', 'bytes', 'date', 'datetime', 'decimal', 'enum', 'frozenset', 'memoryview', 'namespace', 'object', 'path', 're_pattern', 'recursion', 'set', 'time', 'tuple'})
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L21)

</details>

<a id="from_jsonable"></a>
<details>
<summary><code>from_jsonable</code> — Reconstruct objects encoded with to_jsonable(..., roundtrip=True).</summary>

```python
from_jsonable(obj: 'Any') -> 'Any'
```

```text
Reconstruct objects encoded with to_jsonable(..., roundtrip=True).
If input was produced with roundtrip=False, this mostly passes values through.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L372)

</details>

<a id="load_options_from_json"></a>
<details>
<summary><code>load_options_from_json</code> — Load the options object from a JSON file.</summary>

```python
load_options_from_json(options: 'Options', json_file: 'str | os.PathLike[str]') -> 'Options | None'
```

```text
Load the options object from a JSON file.

Args:
    options:    An existing Options object (used for logging purposes).
    json_file:  Path to the JSON file to load.

Returns:
    Options object loaded from the JSON file, or None if the file does not exist or cannot be read.

Raises:
    IOError:    If there is an error reading the file.
    ValueError: If the JSON file is invalid or cannot be parsed.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L534)

</details>

<a id="register_json_type"></a>
<details>
<summary><code>register_json_type</code> — Teach `to_jsonable` / `from_jsonable` about a type `emmykit` does not know.</summary>

```python
register_json_type(cls: 'type', encode: 'Callable[[Any], Mapping[str, Any]]', *, tag: 'str | None' = None, decode: 'Callable[[dict[str, Any]], Any] | None' = None, replace: 'bool' = False) -> 'None'
```

```text
Teach `to_jsonable` / `from_jsonable` about a type `emmykit` does not know.

Without this, an unrecognized object falls through to `str(obj)` and a
reloaded file holds a repr string where a real object should be — a silent
failure, not a loud one.

Dispatch is by `isinstance`, so subclasses of `cls` are handled too. When
two registrations both match, the more specific class wins; when neither is
a subclass of the other, the most recently registered one wins. A registered
handler takes precedence over every built-in handler.

`tag` and `decode` are optional *together*. Supplying one without the other
is an error. Supplying neither registers an **encode-only** type: it is
serialized through `encode` but never tagged, in either `roundtrip` mode,
and therefore reloads as a plain `dict`. That is the honest choice for an
object that can be *described* faithfully but not *rebuilt* faithfully —
e.g. a lookup table populated by probing a live interpreter, where a
reconstructed copy would answer differently while looking identical.

Args:
    cls:     The class to register. Dispatch is by `isinstance`.
    encode:  Callable taking an instance and returning a mapping of
             JSON-ish values. The mapping's values are themselves passed
             through the converter, so they may contain `Path`, `set`,
             `datetime`, or another registered type. The recursion guard
             stays in effect across that call.
    tag:     Type tag written as `__type__` when `roundtrip=True`. Must not
             collide with a built-in tag (see `BUILTIN_JSON_TAGS`) or with
             an already-registered tag.
    decode:  Callable taking the decoded payload (the `__type__` key
             removed, every value already reconstructed) and returning an
             instance.
    replace: Retire any existing registration for `cls` or for `tag` instead
             of raising.

Returns:
    None - mutates the process-wide registry.

Raises:
    TypeError:  If `cls` is not a class, or `encode` is not callable.
    ValueError: If exactly one of `tag` / `decode` is given; if `tag` is
                empty or collides with a built-in tag; or if `cls` or `tag`
                is already registered and `replace` is False.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L58)

</details>

<a id="save_options_to_json"></a>
<details>
<summary><code>save_options_to_json</code> — Save the options object to a JSON file.</summary>

```python
save_options_to_json(options: 'Options') -> 'None'
```

```text
Save the options object to a JSON file.

Args:
    options: Options object containing:
        - script_dir:    Directory where the JSON file will be saved.
        - python_script: Name of the Python script (used in the JSON filename).
        - my_name:       Name of the current script (used in the JSON filename).
        - timestamp:     Current timestamp (used in the JSON filename).

Returns:
    None - writes the options to a JSON file.

Raises:
    IOError:    If there is an error writing to the file.
    ValueError: If the options object is invalid.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L502)

</details>

<a id="to_jsonable"></a>
<details>
<summary><code>to_jsonable</code> — Convert arbitrary Python objects into JSON-serializable primitives.</summary>

```python
to_jsonable(obj: 'Any', *, roundtrip: 'bool' = True) -> 'Any'
```

```text
Convert arbitrary Python objects into JSON-serializable primitives.
If roundtrip=True, non-JSON types are wrapped with a small type tag so they can be reconstructed.
Types registered via register_json_type() are handled ahead of the built-ins.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L236)

</details>

<a id="unregister_json_type"></a>
<details>
<summary><code>unregister_json_type</code> — Remove a registration made by `register_json_type`.</summary>

```python
unregister_json_type(cls_or_tag: 'type | str') -> 'None'
```

```text
Remove a registration made by `register_json_type`.

The type falls back to whatever `to_jsonable` did before it was registered.

Args:
    cls_or_tag: The registered class, or its `tag` string.

Returns:
    None - mutates the process-wide registry.

Raises:
    KeyError:  If nothing is registered under that class or tag.
    TypeError: If `cls_or_tag` is neither a class nor a string.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/json_io.py#L154)

</details>

<a id="m-diff_view"></a>
### `diff_view` — Diff rendering with visible whitespace

_Layer 4._  `from emmykit.diff_view import …`

`my_diff` (color unified diff), `diff_and_confirm` (interactive accept/reject loop), `highlight_changes` (per-line intra-word emphasis), and `is_python_script` (the heuristic that decides whether a path holds Python source).

<a id="diff_and_confirm"></a>
<details>
<summary><code>diff_and_confirm</code> — Show a unified diff of orig_text → changed_text with a number of context lines</summary>

```python
diff_and_confirm(orig_text: 'str', changed_text: 'str', path: 'str | os.PathLike[str]', label: 'str' = '', skip_compile: 'bool' = False, diff_choice: 'int' = 1, changed_color: 'str' = '\x1b[94m', deleted_color: 'str' = '\x1b[91m', added_color: 'str' = '\x1b[93m', the_fix: 'str' = '', description: 'str' = '') -> 'bool'
```

```text
Show a unified diff of orig_text → changed_text with a number of context lines
(determined by 'diff_choice') around each hunk, log using 'label' and 'description', then prompt.
If the user confirms, overwrite 'path' with changed_text and return True.
If the user chooses to quit, log a message and return False.

Args:
    orig_text:     Original text to compare against.
    changed_text:  Proposed changes to the original text.
    path:          Path to the file being modified.
    label:         A short label for the issue being fixed (default "").
    skip_compile:  If True, do not try to compile the changed text before writing (default False).
    diff_choice:   How many context lines to show in the diff (0 = old-style diff, 1 = unified diff with 0 context lines, 2+ = unified diff with 'diff_choice - 1' context lines) (default 1).
    changed_color: Color to use for unchanged characters in the changed lines in the diff (default ANSI_CYAN).
    deleted_color: Color to use for the deleted characters in orig lines (default ANSI_YELLOW).
    added_color:   Color to use for the added characters in changed lines (default ANSI_GREEN).
    the_fix:       A string describing the fix being applied (e.g. "autopep8", "manual edit") (default "").
    description:   A longer description of the issue being fixed (default "").

Returns:
    False if the user chose to quit; True otherwise.

Raises:
    FileNotFoundError: If the specified file does not exist.
    ValueError: If the specified path is not a file. The function which raises this exception is my_fopen().
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/diff_view.py#L300)

</details>

<a id="highlight_changes"></a>
<details>
<summary><code>highlight_changes</code> — Compare 'orig' and 'new' strings and return a tuple</summary>

```python
highlight_changes(orig: 'str', new: 'str', unchanged_color: 'str', added_color: 'str', deleted_color: 'str') -> 'tuple[str, str]'
```

```text
Compare 'orig' and 'new' strings and return a tuple
(old_highlighted, new_highlighted), where:
- old_highlighted has parts present only in 'orig' wrapped in deleted_color.
- new_highlighted has parts present only in 'new' wrapped in added_color
  and unchanged parts in unchanged_color.

Args:
    orig:            The original string.
    new:             The modified string.
    unchanged_color: The color to use for unchanged parts.
    added_color:     The color to use for added parts.
    deleted_color:   The color to use for deleted parts.

Returns:
    A tuple of (old_highlighted, new_highlighted) strings.

Raises:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/diff_view.py#L36)

</details>

<a id="is_python_script"></a>
<details>
<summary><code>is_python_script</code> — Return True if 'path' looks like a Python script:</summary>

```python
is_python_script(path: 'str | os.PathLike[str]') -> 'bool'
```

```text
Return True if 'path' looks like a Python script:
  1. It's a file which ends in .py or .pyw
  2. Or it is executable AND its first line is a python shebang

Args:
    path: The file path to check.

Returns:
    True if the path is a Python script, False otherwise.

Raises:
    IsADirectoryError: If the path is a directory.
    FileNotFoundError: If the file is not found.
    PermissionError:   If the file is not accessible due to permission issues.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/diff_view.py#L255)

</details>

<a id="my_diff"></a>
<details>
<summary><code>my_diff</code> — Show a diff between 'orig_text' and 'changed_text' in the console,</summary>

```python
my_diff(orig_text: 'str', changed_text: 'str', orig_path: 'str | os.PathLike[str]', changed_path: 'str | os.PathLike[str] | None' = None, diff_choice: 'int' = 1, changed_color: 'str' = '\x1b[94m', deleted_color: 'str' = '\x1b[91m', added_color: 'str' = '\x1b[93m') -> 'None'
```

```text
Show a diff between 'orig_text' and 'changed_text' in the console,
highlighting character-level changes within changed lines.

Args:
    orig_text:      Original text to compare against.
    changed_text:   Proposed changes to the original text.
    orig_path:      Path to the original file.
    changed_path:   Optional path to the changed file (if different).
    diff_choice:    How many context lines to show in the diff ( 0 = old-style diff, 1 = unified diff with 0 context lines,
                                                                2+ = unified diff with 'diff_choice - 1' context lines).
    changed_color:  Color to use for unchanged characters in the changed lines in the diff (default ANSI_CYAN).
    deleted_color:  Color to use for the deleted characters in orig lines (default ANSI_YELLOW).
    added_color:    Color to use for the added characters in changed lines (default ANSI_RED).

Returns:
    None: Prints the diff to the console.

Raises:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/diff_view.py#L82)

</details>

<a id="m-text"></a>
### `text` — Mojibake fixing, encoding detection, casing helpers

_Layer 5._  `from emmykit.text import …`

ftfy-based `fix_text`/`fix_mojibake` (with an atomic write-back), explicit UTF-8 / CP-1252 decoders, sentence-aware `my_capitalize`/`my_title_case`, and `normalize_for_search` for diacritic-folded comparisons.

Translation tables live in `emmykit.text_constants` (`CHARACTERS_TO_SPACE` / `QUOTES_TO_DELETE` / `REPLACE_WITH_SPACE` / `TRANSLATION_TABLE`) and feed `normalize_for_search`.

<a id="contains_mojibake"></a>
<details>
<summary><code>contains_mojibake</code> — Use ftfy.badness.is_bad() to detect any likely mojibake in the text.</summary>

```python
contains_mojibake(text: 'str') -> 'bool'
```

```text
Use ftfy.badness.is_bad() to detect any likely mojibake in the text.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L63)

</details>

<a id="decode_cp1252"></a>
<details>
<summary><code>decode_cp1252</code> — Attempt to decode CP1252 bytes and return as a string.</summary>

```python
decode_cp1252(raw_bytes: 'bytes', path_str: 'str' = 'input string') -> 'str | None'
```

```text
Attempt to decode CP1252 bytes and return as a string.
If it fails, return None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L48)

</details>

<a id="decode_utf8"></a>
<details>
<summary><code>decode_utf8</code> — If the file at 'path' is valid UTF-8 without lone C1 controls,</summary>

```python
decode_utf8(raw_bytes: 'bytes', path_str: 'str' = 'input string') -> 'str | None'
```

```text
If the file at 'path' is valid UTF-8 without lone C1 controls,
return the decoded string. Otherwise, return None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L31)

</details>

<a id="ensure_utf8_meta"></a>
<details>
<summary><code>ensure_utf8_meta</code> — Ensure the HTML text has a <meta charset="utf-8"> tag.</summary>

```python
ensure_utf8_meta(html: 'str') -> 'str'
```

```text
Ensure the HTML text has a <meta charset="utf-8"> tag.
If one already exists—either as a charset attribute or
as an http-equiv Content-Type declaration—normalize it to
<meta charset="utf-8">. Otherwise, insert that tag right
after the opening <head> tag.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L103)

</details>

<a id="fix_mojibake"></a>
<details>
<summary><code>fix_mojibake</code> — Fix mojibake in a text file, recoding from CP1252 to UTF-8 if necessary.</summary>

```python
fix_mojibake(filepath: 'str | os.PathLike[str]', make_backup: 'bool' = True, dry_run: 'bool' = False) -> 'None'
```

```text
Fix mojibake in a text file, recoding from CP1252 to UTF-8 if necessary.
If the file is already valid UTF-8, it will only fix mojibake.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L141)

</details>

<a id="fix_text"></a>
<details>
<summary><code>fix_text</code> — Fix mojibake in a string using ftfy.fix_encoding().</summary>

```python
fix_text(current_text: 'str', path: 'str | os.PathLike[str]', raw_bytes: 'bytes') -> 'str | None'
```

```text
Fix mojibake in a string using ftfy.fix_encoding().
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L77)

</details>

<a id="my_capitalize"></a>
<details>
<summary><code>my_capitalize</code> — Capitalize ONLY the first letter of a string and DON'T modify the rest of it.</summary>

```python
my_capitalize(string_to_capitalize: 'str') -> 'str'
```

```text
Capitalize ONLY the first letter of a string and DON'T modify the rest of it.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L18)

</details>

<a id="my_title_case"></a>
<details>
<summary><code>my_title_case</code> — Capitalize the first letter of each word, but if a word already has ANY uppercase letters, leave it as is. This way, wo…</summary>

```python
my_title_case(the_title: 'str') -> 'str'
```

```text
Capitalize the first letter of each word, but if a word already has ANY uppercase letters, leave it as is. This way, words like "WW2" or "iZombie" won't be modified.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L24)

</details>

<a id="normalize_for_search"></a>
<details>
<summary><code>normalize_for_search</code> — Convert text to ASCII and lowercase for case- and diacritic-insensitive comparison. Also treat some characters such as …</summary>

```python
normalize_for_search(text: 'str') -> 'str'
```

```text
Convert text to ASCII and lowercase for case- and diacritic-insensitive comparison. Also treat some characters such as ._- the same as spaces. Remove quotes (', ", ' and their unicode variants).
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/text.py#L196)

</details>

<a id="m-hosts"></a>
### `hosts` — Hostname + computer-name detection

_Layer 5._  `from emmykit.hosts import …`

Five strategies for retrieving a hostname (socket / platform / uname / `hostname` / scutil), aggregated by `get_computer_name` with a NASA-prefix detector.

<a id="analyze_computer_name_results"></a>
<details>
<summary><code>analyze_computer_name_results</code> — Analyzes the retrieved computer names.</summary>

```python
analyze_computer_name_results(results: 'dict[str, str]', rawlog: 'bool' = False) -> 'str'
```

```text
Analyzes the retrieved computer names.

Args:
    results: Dictionary with method names as keys and computer names as values.
    rawlog:  If True, print statements are disabled.

Returns:
    A string representing the most common computer name obtained from the methods.
    If no names were retrieved, returns "ERROR-NO-NAME".

Raises:
    None: This function does not raise exceptions, but it may log errors or warnings if
          no names (or differing names) are retrieved.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L100)

</details>

<a id="computer_name"></a>
<details>
<summary><code>COMPUTER_NAME</code> — str = 'b5ac839dd662'</summary>

```python
COMPUTER_NAME: str = 'b5ac839dd662'
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L146)

</details>

<a id="get_computer_name"></a>
<details>
<summary><code>get_computer_name</code> — Attempts multiple methods to retrieve the computer's name and returns the most common one.</summary>

```python
get_computer_name(rawlog: 'bool' = False) -> 'str'
```

```text
Attempts multiple methods to retrieve the computer's name and returns the most common one.

Args:
    rawlog: If True, print statements are disabled.

Returns:
    A string representing the most common computer name obtained from the methods.
    If no names were retrieved, returns "ERROR-NO-NAME".

Raises:
    None: This function does not raise exceptions, but it may log warnings if no names are retrieved.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L61)

</details>

<a id="get_hostname_os_uname"></a>
<details>
<summary><code>get_hostname_os_uname</code> — Retrieves the hostname using os.uname().nodename.</summary>

```python
get_hostname_os_uname(rawlog: 'bool' = False) -> 'str | None'
```

```text
Retrieves the hostname using os.uname().nodename.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L31)

</details>

<a id="get_hostname_platform"></a>
<details>
<summary><code>get_hostname_platform</code> — Retrieves the hostname using platform.node().</summary>

```python
get_hostname_platform(rawlog: 'bool' = False) -> 'str | None'
```

```text
Retrieves the hostname using platform.node().
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L22)

</details>

<a id="get_hostname_socket"></a>
<details>
<summary><code>get_hostname_socket</code> — Retrieves the hostname using socket.gethostname().</summary>

```python
get_hostname_socket(rawlog: 'bool' = False) -> 'str | None'
```

```text
Retrieves the hostname using socket.gethostname().
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L13)

</details>

<a id="get_hostname_subprocess_hostname"></a>
<details>
<summary><code>get_hostname_subprocess_hostname</code> — Retrieves the hostname using the 'hostname' system command via subprocess.</summary>

```python
get_hostname_subprocess_hostname(rawlog: 'bool' = False) -> 'str | None'
```

```text
Retrieves the hostname using the 'hostname' system command via subprocess.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L39)

</details>

<a id="get_hostname_subprocess_scutil"></a>
<details>
<summary><code>get_hostname_subprocess_scutil</code> — Retrieves the hostname using the 'scutil --get ComputerName' command on macOS via subprocess.</summary>

```python
get_hostname_subprocess_scutil(rawlog: 'bool' = False) -> 'str | None'
```

```text
Retrieves the hostname using the 'scutil --get ComputerName' command on macOS via subprocess.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L49)

</details>

<a id="is_nasa_computer"></a>
<details>
<summary><code>IS_NASA_COMPUTER</code> — bool = False</summary>

```python
IS_NASA_COMPUTER: bool = False
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L153)

</details>

<a id="c-hosts-nasa-computer-name-prefixes"></a>
<details>
<summary><code>NASA computer-name prefixes</code> — Prefix lists feeding `IS_NASA_COMPUTER` detection.</summary>

**Includes:** `NASA_CASEFOLDED_COMPUTER_NAME_PREFIXES`, `NASA_COMPUTER_NAME_PREFIXES`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/hosts.py#L150)

</details>

<a id="m-network"></a>
### `network` — Internet-connectivity probes

_Layer 5._  `from emmykit.network import …`

`is_internet_available` runs a multi-strategy DNS + HTTP + TCP check against `net_targets` with a captive-portal sniff and a shared `ThreadPoolExecutor`.

Probe targets live in `emmykit.net_targets` (`IPV4_TARGETS` / `IPV6_TARGETS` / `HTTP_PROBES` / `DNS_TEST_NAMES`) and feed `is_internet_available`.

<a id="checkresult"></a>
<details>
<summary><code>CheckResult</code> — Aggregate results from the multi-strategy connectivity check.</summary>

```python
CheckResult(tcp_ok: 'bool', dns_ok: 'bool', http_ok: 'bool', captive_detected: 'bool') -> None
```

```text
Aggregate results from the multi-strategy connectivity check.
```

**Fields:** `tcp_ok`, `dns_ok`, `http_ok`, `captive_detected`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/network.py#L425)

</details>

<a id="is_internet_available"></a>
<details>
<summary><code>is_internet_available</code> — Determine if the internet is available using multiple methods.</summary>

```python
is_internet_available(timeout_per_step: 'float' = 2.5, retries: 'int' = 1, workers: 'int' = 6, include_ipv6: 'bool' = False, strict: 'bool' = False, ignore_proxies: 'bool' = False) -> 'bool'
```

```text
Determine if the internet is available using multiple methods.

Strategy (per attempt):
    1) TCP to multiple well-known numeric IPs (no DNS).
    2) DNS resolution of common hostnames.
    3) HTTP(S) probes with expectations and captive-portal detection.

Aggregation logic:
    - If captive portal is detected -> return False immediately.
    - If any HTTP probe passes expectations -> return True.
    - Else if TCP OK and DNS OK -> return True.
    - Else:
        * If strict is False and TCP OK alone -> return False
          (raw TCP alone is not considered sufficient for "internet usable").
        * If strict is True -> still False.

Args:
    timeout_per_step: Timeout (seconds) per individual network attempt.
    retries:          Number of times to repeat the full check if the result is False.
    workers:          Thread pool size for TCP checks.
    include_ipv6:     Whether to include IPv6 targets.
    strict:           Require stronger evidence of connectivity.
    ignore_proxies:   Disable env proxies for HTTP probes.

Returns:
    True if the internet appears reachable and usable, else False.

Raises:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/network.py#L509)

</details>

<a id="m-python_env"></a>
### `python_env` — Python interpreter discovery

_Layer 2._  `from emmykit.python_env import …`

`find_preferred_python_version` locates the preferred interpreter on PATH; `check_python_version` confirms a given python command meets the minimum version.

<a id="check_python_version"></a>
<details>
<summary><code>check_python_version</code> — Check if the given Python command is available and has a version of PY_VERSION or higher.</summary>

```python
check_python_version(command: 'str') -> 'bool'
```

```text
Check if the given Python command is available and has a version of PY_VERSION or higher.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/python_env.py#L9)

</details>

<a id="find_preferred_python_version"></a>
<details>
<summary><code>find_preferred_python_version</code> — Find the command for the preferred version of python (stored here as PY_VERSION).</summary>

```python
find_preferred_python_version() -> 'str | None'
```

```text
Find the command for the preferred version of python (stored here as PY_VERSION).
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/python_env.py#L22)

</details>

<a id="m-files"></a>
### `files` — Checksums, downloads, filename formatting, free-space queries

_Layer 5._  `from emmykit.files import …`

`download_file` with progress, `calculate_checksum`, `query_free_space` via shutil, `filename_format` for legal-on-most-OSes name munging, and `verify_script` to confirm a shell script is well-formed.

<a id="calculate_checksum"></a>
<details>
<summary><code>calculate_checksum</code> — Calculate the SHA256 checksum of a file.</summary>

```python
calculate_checksum(file_path: 'str | os.PathLike[str]') -> 'str'
```

```text
Calculate the SHA256 checksum of a file.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/files.py#L321)

</details>

<a id="download_file"></a>
<details>
<summary><code>download_file</code> — Download a file to 'dest' with retry + exponential backoff.</summary>

```python
download_file(url: 'str', dest: 'str | os.PathLike[str]', retries: 'int' = 5, chunk_size: 'int' = 1048576, timeout: 'int' = 30, headers: 'dict[str, str] | None' = None) -> 'None'
```

```text
Download a file to 'dest' with retry + exponential backoff.
Writes to a temporary .part file and renames atomically on success.
Verifies Content-Length if provided.
Logs progress by bytes (rough).
Also checks free disk space (if size is known) before downloading.

Args:
    url:        The source URL to download from.
    dest:       Destination file path.
    retries:    Number of attempts (default 5 is a good balance for transient errors).
    chunk_size: Bytes per read chunk (default 1MiB).
    timeout:    Per-attempt socket timeout (seconds).
    headers:    Optional dict of HTTP headers to include in the request.

Returns:
    None. Writes the file to 'dest'.

Raises:
    SystemExit on failure after retries or if insufficient free space is detected.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/files.py#L19)

</details>

<a id="filename_format"></a>
<details>
<summary><code>filename_format</code> — Turn arbitrary text into an ASCII-only, filesystem‐safe base filename.</summary>

```python
filename_format(text: 'str', sep: 'str' = '_', max_length: 'int | None' = None) -> 'str'
```

```text
Turn arbitrary text into an ASCII-only, filesystem‐safe base filename.
WARNING: Do not include an extension in the text, because this function
might remove the dot which separates the filename from the extension.
It attempts to recognize and remove extensions listed in ALL_KNOWN_EXTENSIONS
but this list (actually, ordered tuple) is not exhaustive.

Steps:
  1. Unicode → ASCII
  2. Recognize & remove common extensions (e.g. .txt, .fits, .tar.gz)
  3. Treat dots, underscores & whitespace as word separators
  4. Remove any character that isn't A-z, a–z, 0–9, dashes, or the separator
  5. Collapse runs of separators into a single one
  6. Trim separators from ends
  7. Optionally truncate to max_length (preserving word boundaries)
  8. If an extension was removed, append it back as the last step.

Args:
    text:       Original filename or title
    sep:        Single-character separator (default: "_")
    max_length: If set, strongest‐effort truncate to this many chars

Returns:
    A clean, filename-safe string.

Raises:
    None: If the input text is None, it will return an empty string.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/files.py#L214)

</details>

<a id="query_free_space"></a>
<details>
<summary><code>query_free_space</code> — Return the free space (in bytes) available to the current user on the</summary>

```python
query_free_space(path: 'str | os.PathLike[str]') -> 'int'
```

```text
Return the free space (in bytes) available to the current user on the
filesystem that contains 'path'. Works for files or directories, and
for paths that don't yet exist (it climbs to the nearest existing parent).

Args:
    path: A file or directory path.

Returns:
    Free space in bytes available to the current user on the filesystem.

Raises:
    FileNotFoundError: If no existing parent directory is found.
    OSError:           If the filesystem information cannot be retrieved.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/files.py#L178)

</details>

<a id="verify_script"></a>
<details>
<summary><code>verify_script</code> — Ensure that 'thepath' exists and contains exactly 'thescript'.</summary>

```python
verify_script(options: 'Options', thepath: 'str | os.PathLike[str]', thescript: 'str') -> 'None'
```

```text
Ensure that 'thepath' exists and contains exactly 'thescript'.
- If 'thepath' does not exist or is not a file, it will be created and populated.
- If it exists but its contents differ, it will be overwritten.
- Otherwise, nothing happens.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/files.py#L292)

</details>

<a id="m-lint"></a>
### `lint` — flake8 / autopep8 / mypy interactive runners + multireplace

_Layer 6._  `from emmykit.lint import …`

Run linters, gather + display findings with color, prompt-and-apply autopep8 fixes, and the `multireplace` regex-driven search-and-replace tool that shares lint internals.

<a id="ask_and_autopep8"></a>
<details>
<summary><code>ask_and_autopep8</code> — Prompt the user about fixing ALL occurrences of 'code' in 'path',</summary>

```python
ask_and_autopep8(path: 'str | os.PathLike[str]', code: 'str', description: 'str' = '', diff_choice: 'int' = 1, changed_color: 'str' = '\x1b[94m', deleted_color: 'str' = '\x1b[91m', added_color: 'str' = '\x1b[93m') -> 'bool'
```

```text
Prompt the user about fixing ALL occurrences of 'code' in 'path',
and if yes, apply autopep8.fix_file with --select=code.
The fix will be applied without saving, and the user will be shown a diff
of the changes before saving to the file.

Args:
    path:          The path to the file to modify.
    code:          The specific PEP 8 violation code to fix.
    description:   A description of the issue being fixed (default "").
    diff_choice:   How many context lines to show in the diff (0 = old-style diff, 1 = unified diff with 0 context lines, 2+ = unified diff with 'diff_choice - 1' context lines) (default 1).
    changed_color: Color to use for unchanged characters in the changed lines in the diff (default ANSI_CYAN).
    deleted_color: Color to use for the deleted characters in orig lines (default ANSI_YELLOW).
    added_color:   Color to use for the added characters in changed lines (default ANSI_GREEN).

Returns:
    True if the user wants to continue, False if they want to quit.

Raises:
    FileNotFoundError: If the specified file does not exist.
    ValueError: If the specified path is not a file. The function which raises this exception is autopep8.fix_file().
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L520)

</details>

<a id="ask_and_replace"></a>
<details>
<summary><code>ask_and_replace</code> — Read 'path', do orig.replace(old, new), then show a diff and ask to confirm.</summary>

```python
ask_and_replace(old_str: 'str', new_str: 'str', path: 'str | os.PathLike[str]', label: 'str' = '', diff_choice: 'int' = 1, description: 'str' = '', changed_color: 'str' = '\x1b[94m', deleted_color: 'str' = '\x1b[91m', added_color: 'str' = '\x1b[93m', skip_compile: 'bool' = False, verbose: 'bool' = True) -> 'bool'
```

```text
Read 'path', do orig.replace(old, new), then show a diff and ask to confirm.

Args:
    old_str:       Old string to search for.
    new_str:       New string to replace the old string.
    path:          Path to the file being modified.
    label:         A short label for the issue being fixed (default "").
    skip_compile:  If True, do not try to compile the changed text before writing (default False).
    diff_choice:   How many context lines to show in the diff (0 = old-style diff, 1 = unified diff with 0 context lines, 2+ = unified diff with 'diff_choice - 1' context lines) (default 1).
    changed_color: Color to use for unchanged characters in the changed lines in the diff (default ANSI_CYAN).
    deleted_color: Color to use for the deleted characters in orig lines (default ANSI_YELLOW).
    added_color:   Color to use for the added characters in changed lines (default ANSI_GREEN).
    the_fix:       A string describing the fix being applied (e.g. "autopep8", "manual edit") (default "").
    description:   A longer description of the issue being fixed (default "").

Returns:
    False if the user chose to quit; True otherwise.

Raises:
    IsADirectoryError: If the path is a directory.
    FileNotFoundError: If the file is not found.
    PermissionError: If the file is not accessible due to permission issues.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L587)

</details>

<a id="check_python_formatting"></a>
<details>
<summary><code>check_python_formatting</code> — Reads a .py file at 'path' via my_fopen, makes sure it compiles, parses it with AST,</summary>

```python
check_python_formatting(path: 'str | os.PathLike[str]', diff_choice: 'int' = 1) -> 'bool'
```

```text
Reads a .py file at 'path' via my_fopen, makes sure it compiles, parses it with AST,
prints any custom formatting violations to stdout,
and asks the user to fix any backticks or curly quotes in the file. If the user quits, it returns False.

Args:
    path:        The path to the Python file to check.
    diff_choice: How many context lines to show in the diff (0 = old-style diff, 1 = unified diff with 0 context lines, 2+ = unified diff with 'diff_choice - 1' context lines).

Returns:
    False if the user chose to quit during any replacement prompts or if there was an error,
    True otherwise.

Raises:
    FileNotFoundError: If the specified file does not exist.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L252)

</details>

<a id="formatchecker"></a>
<details>
<summary><code>FormatChecker</code> — Walks a module AST and collects formatting violations:</summary>

```python
FormatChecker(source: 'str', doc_style: 'str' = 'None') -> 'None'
```

```text
Walks a module AST and collects formatting violations:
- missing type hints on params / return
- missing docstring or incorrect docstring quote style
```

**Public methods:** `generic_visit`, `visit`, `visit_AsyncFunctionDef`, `visit_ClassDef`, `visit_Constant`, `visit_FunctionDef`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L250)

</details>

<a id="get_autopep8_fixable_codes"></a>
<details>
<summary><code>get_autopep8_fixable_codes</code> — Run 'autopep8 --list-fixes' (via subprocess) to discover exactly</summary>

```python
get_autopep8_fixable_codes() -> 'set[str]'
```

```text
Run 'autopep8 --list-fixes' (via subprocess) to discover exactly
which Flake8 error‐codes autopep8 knows how to fix.
Returns a set like {"E101","E111", ...}.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L492)

</details>

<a id="interactive_flake8"></a>
<details>
<summary><code>interactive_flake8</code> — 1) Run the flake8 API for summary counts.</summary>

```python
interactive_flake8(options: 'Options', path: 'str | os.PathLike[str]', ignore_codes: 'list[str] | None' = None, diff_choice: 'int' = 1, max_line_length: 'int' = 100, changed_color: 'str' = '\x1b[94m', deleted_color: 'str' = '\x1b[91m', added_color: 'str' = '\x1b[93m') -> 'bool'
```

```text
1) Run the flake8 API for summary counts.
2) Shell out to flake8 CLI once to harvest one description per code.
3) For each code, ask the user; on "yes", call autopep8 to fix only that code.

Args:
    options:         The parsed command-line options. Contains:
                         - bugbear_choice: Whether to include flake8-bugbear checks.
    path:            Path to the Python file to check.
    diff_choice:     How many context lines to show in the diff (0 = old-style diff,
                     1  = unified diff with 0 context lines,
                     2+ = unified diff with 'diff_choice - 1' context lines).
    ignore_codes:    List of Flake8 codes to ignore (default: empty list).
    max_line_length: Maximum line length for E501 (default: 100).
    changed_color:   Color for unchanged characters in changed lines (default: ANSI_CYAN).
    deleted_color:   Color for deleted characters in original lines (default: ANSI_RED).
    added_color:     Color for added characters in changed lines (default: ANSI_YELLOW).

Returns:
    False if the user chose to quit during any replacement prompts, True otherwise.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L734)

</details>

<a id="multireplace"></a>
<details>
<summary><code>multireplace</code> — Perform a multi-file replace operation.</summary>

```python
multireplace(options: 'Options', verbose: 'bool' = True) -> 'None'
```

```text
Perform a multi-file replace operation.

Args:
    options: The parsed command-line options. Contains:
        - old_str: The text to be replaced in the files.
        - new_str: The text to replace the old_str.
        - glob_pattern: Glob pattern of files to edit.
        - dir: Directory to search in.
        - recursive: Whether to search recursively in subdirectories.
    verbose: If True, log messages about files with no occurrences found (default: True).

Returns:
    None. Modifies files in place if the user confirms the changes.

Raises:
    ValueError:         If the glob pattern is invalid.
    FileNotFoundError:  If the specified directory does not exist.
    NotADirectoryError: If the specified path is not a directory.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L667)

</details>

<a id="run_flake8"></a>
<details>
<summary><code>run_flake8</code> — Run Flake8 on 'path', but:</summary>

```python
run_flake8(options: 'Options', path: 'str | os.PathLike[str]', ignore_codes: 'list[str] | None' = None, max_line_length: 'int' = 100) -> 'flake8.Report'
```

```text
Run Flake8 on 'path', but:
  - only flag E501 if a line exceeds 'max_line_length',
  - ignore whatever codes are in 'ignore_codes'.

Args:
    options:         Options instance containing various settings.
    path:            The path to the Python file to check.
    ignore_codes:    A list of Flake8 error/warning codes to ignore.
    max_line_length: The (custom) maximum allowed line length for E501 checks.

Returns:
    flake8.Report:   The Flake8 report object containing the results.

Raises:
    FileNotFoundError: If the specified file does not exist.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L335)

</details>

<a id="run_mypy"></a>
<details>
<summary><code>run_mypy</code> — Run basic mypy static analysis on the specified file.</summary>

```python
run_mypy(options: 'Options', path: 'str | os.PathLike[str]') -> 'None'
```

```text
Run basic mypy static analysis on the specified file.

Args:
    options: The parsed command-line options. (Currently unused but included for consistency.)
    path:    Path to the Python file to analyze.

Returns:
    None.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/lint.py#L791)

</details>

<a id="m-treeview"></a>
### `treeview` — Directory tree with new-file highlighting

_Layer 7._  `from emmykit.treeview import …`

Renders a colored ASCII tree starting at a directory, marking files newer than a cutoff.

<a id="treeview_new_files"></a>
<details>
<summary><code>treeview_new_files</code> — Recursively scan the directory, print the contents of files newer than last_file_path (if provided- if so store its mod…</summary>

```python
treeview_new_files(directory: 'str | os.PathLike[str]', last_file_path: 'str | os.PathLike[str] | None' = None, last_mtime: 'float | None' = None, maxlines: 'int' = 0, use_colors: 'bool' = True, print_root: 'bool' = True, prefix: 'str' = '', is_last: 'bool' = True, level: 'int' = 0, state: 'dict[str, Any] | None' = None, probe_only: 'bool' = False) -> 'bool'
```

```text
Recursively scan the directory, print the contents of files newer than last_file_path (if provided- if so store its modification date in last_mtime). Return True if any relevant files are found.

Args:
    directory:      The directory to scan.
    last_file_path: The optional path to a chosen file. Only files newer than this will be printed.
    last_mtime:     The modification time of the last_file_path. If None, all files will be
                    considered.
    maxlines:       The maximum number of lines to read from each file. 0 means don't read at all,
                    -1 means read all lines, otherwise read up to maxlines (default 0).
    use_colors:     Whether to use ANSI color codes in the output (default True).
    print_root:     If True, print the root directory name (default True).
    prefix:         The prefix to use for logging output (default '').
    is_last:        Whether this is the last item in the current level (default True).
    level:          The current recursion level (default 0).
    state:          A dictionary to maintain state across recursive calls (default None).
    probe_only:     If True, do not print file contents, just check for existence of relevant
                    files (default False).

Returns:
    True if any relevant files are found or the directory itself is newer than last_mtime,
    False otherwise.

Raises:
    None: Catches exceptions, logs an error and returns False if the directory is not a valid
          directory or does not exist.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/treeview.py#L14)

</details>

<a id="m-docker_utils"></a>
### `docker_utils` — Docker daemon + image lifecycle helpers

_Layer 7._  `from emmykit.docker_utils import …`

Ensure the docker daemon is running, the requested image is built, and rerun a command with auto-fixes when daemon or image is missing.

<a id="ensure_daemon_running"></a>
<details>
<summary><code>ensure_daemon_running</code> — Check if the Docker daemon is running; if not, attempt to start it.</summary>

```python
ensure_daemon_running() -> 'None'
```

```text
Check if the Docker daemon is running; if not, attempt to start it.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/docker_utils.py#L20)

</details>

<a id="ensure_docker_installed"></a>
<details>
<summary><code>ensure_docker_installed</code> — Check if the Docker CLI is installed; if not, raise an error.</summary>

```python
ensure_docker_installed() -> 'None'
```

```text
Check if the Docker CLI is installed; if not, raise an error.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/docker_utils.py#L13)

</details>

<a id="ensure_image_built"></a>
<details>
<summary><code>ensure_image_built</code> — Ensure that a Docker image with the given name exists; if not, build it.</summary>

```python
ensure_image_built(image: 'str', *, dockerfile: 'Path | None' = None, build_dir: 'Path | None' = None, build_cmd: 'str | None' = None) -> 'None'
```

```text
Ensure that a Docker image with the given name exists; if not, build it.
You can specify either a dockerfile (whose first line is a comment with the build command)
or a build_cmd (and optionally a build_dir). If both dockerfile and build_cmd are None,
the function will raise an error.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/docker_utils.py#L48)

</details>

<a id="run_with_docker_fixes"></a>
<details>
<summary><code>run_with_docker_fixes</code> — Run a command (typically 'docker run ...') and if it fails, attempt to fix</summary>

```python
run_with_docker_fixes(base_args: 'list[str]', *, ensure_build: 'Callable[[], None] | None' = None, extra_fixes: 'Iterable[Callable[[], None]] | None' = None) -> 'MyPopenResult'
```

```text
Run a command (typically 'docker run ...') and if it fails, attempt to fix
common Docker issues (like Docker not installed or daemon not running) and retry.

Args:
    base_args:    The command and its arguments to run (e.g., ['docker', 'run', ...]).
    ensure_build: An optional function to ensure a Docker image is built.
                  If provided, it will be called if the initial command fails.
    extra_fixes:  An optional iterable of additional fix functions to try if the command fails.

Returns:
    The result of the successful command, or None if all fixes fail.

Raises:
    RuntimeError: If all fixes fail and the command still does not succeed.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/docker_utils.py#L82)

</details>

<a id="m-system"></a>
### `system` — OS-level process + resource helpers

_Layer 7._  `from emmykit.system import …`

`kill_process`, `is_process_running`, `start_only_one_instance` (PID-lock idempotency), `detect_country` (IP geoloc), and file-manager / terminal-launcher entry points.

<a id="check_if_command_exists"></a>
<details>
<summary><code>check_if_command_exists</code> — Check if a command exists on the system.</summary>

```python
check_if_command_exists(command: 'str') -> 'bool'
```

```text
Check if a command exists on the system.

Args:
    command: The command to check.

Returns:
    True if the command exists, False otherwise.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L14)

</details>

<a id="detect_country"></a>
<details>
<summary><code>detect_country</code> — Detect the country of the IP address using ipinfo.io service.</summary>

```python
detect_country(force_wtfismyip: 'bool' = False) -> 'str | None'
```

```text
Detect the country of the IP address using ipinfo.io service.
If the request fails, it falls back to wtfismyip.com service.

Args:
    force_wtfismyip: If True, always use wtfismyip.com

Returns:
    The country name as a string, or None if detection fails.

Raises:
    ValueError: If the IPINFO_API_TOKEN environment variable is not set.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L163)

</details>

<a id="get_effective_free_memory"></a>
<details>
<summary><code>get_effective_free_memory</code> — Return the "effective" free memory in bytes: free memory plus buffers plus cache.</summary>

```python
get_effective_free_memory() -> 'float'
```

```text
Return the "effective" free memory in bytes: free memory plus buffers plus cache.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L50)

</details>

<a id="is_process_running"></a>
<details>
<summary><code>is_process_running</code> — Check if a process with the given name is running.</summary>

```python
is_process_running(process_name: 'str') -> 'bool'
```

```text
Check if a process with the given name is running.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L108)

</details>

<a id="kill_process"></a>
<details>
<summary><code>kill_process</code> — Kill a process by its name, then check if it is still running and retry if needed. Make sure the process name is unique…</summary>

```python
kill_process(pname: 'str') -> 'None'
```

```text
Kill a process by its name, then check if it is still running and retry if needed. Make sure the process name is unique to avoid killing unintended processes.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L72)

</details>

<a id="open_filemanager_with_dirs"></a>
<details>
<summary><code>open_filemanager_with_dirs</code> — Open the file manager with the specified directories.</summary>

```python
open_filemanager_with_dirs(directories: 'list[str | os.PathLike[str]]') -> 'None'
```

```text
Open the file manager with the specified directories.
Note: Most file managers don't support multiple tabs via command line, so open separate windows.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L135)

</details>

<a id="open_terminal_and_run_command"></a>
<details>
<summary><code>open_terminal_and_run_command</code> — Open a GNOME terminal, source ~/.bashrc (via bash -i), run the_command,</summary>

```python
open_terminal_and_run_command(the_command: 'str', close_after: 'bool' = False, maximize_window: 'bool' = False) -> 'None'
```

```text
Open a GNOME terminal, source ~/.bashrc (via bash -i), run the_command,
and optionally close or keep the window open. Optionally, maximize it.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L27)

</details>

<a id="start_only_one_instance"></a>
<details>
<summary><code>start_only_one_instance</code> — Start a process, but only if it's not already running.</summary>

```python
start_only_one_instance(process_name: 'str') -> 'None'
```

```text
Start a process, but only if it's not already running.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/system.py#L122)

</details>

<a id="m-media"></a>
### `media` — Video / audio helpers (ffmpeg, VLC, system volume)

_Layer 7._  `from emmykit.media import …`

Open paths in VLC, find the bundled ffmpeg, query video duration, slice + concatenate video segments, and set the system volume via pulsectl.

<a id="ensure_even_dimensions"></a>
<details>
<summary><code>ensure_even_dimensions</code> — Ensure the image at 'image_path' has dimensions divisible by 2, by resizing if necessary.</summary>

```python
ensure_even_dimensions(image_path: 'str | os.PathLike[str]') -> 'None'
```

```text
Ensure the image at 'image_path' has dimensions divisible by 2, by resizing if necessary.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L21)

</details>

<a id="extract_and_concatenate_segments"></a>
<details>
<summary><code>extract_and_concatenate_segments</code> — Extracts segments from a video file and concatenates them into a new file.</summary>

```python
extract_and_concatenate_segments(input_file: 'str | os.PathLike[str]', timestamps: 'list', output_name_or_path: 'str | os.PathLike[str]', subtitle_file: 'str | os.PathLike[str]') -> 'None'
```

```text
Extracts segments from a video file and concatenates them into a new file.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L474)

</details>

<a id="find_ffmpeg"></a>
<details>
<summary><code>find_ffmpeg</code> — Return a full path string to an ffmpeg executable if found, else None.</summary>

```python
find_ffmpeg() -> 'str | None'
```

```text
Return a full path string to an ffmpeg executable if found, else None.
Tries: env vars, PATH, common Conda and Windows/Cygwin/MSYS installs,
and (optionally) imageio-ffmpeg if available.

Args:
    None

Returns:
    A string containing the path to the ffmpeg executable or None if not found.

Raises:
    None
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L41)

</details>

<a id="get_video_duration_seconds"></a>
<details>
<summary><code>get_video_duration_seconds</code> — Return the duration of a video file in seconds, using fast and reliable probes.</summary>

```python
get_video_duration_seconds(path: 'str | os.PathLike[str]', timeout: 'float' = 10.0) -> 'float'
```

```text
Return the duration of a video file in seconds, using fast and reliable probes.

The function prefers `ffprobe` (from FFmpeg) for speed and accuracy, falls back to
`mediainfo` if available, and finally attempts an OpenCV-based estimate if neither
CLI is present. All filesystem paths are handled via `pathlib.Path`.

Args:
    path:    Path to the video file (string path or os.PathLike). Converted to Path.
    timeout: Per-process timeout (in seconds) for external probes.

Returns:
    The duration of the video in seconds as a float.

Raises:
    FileNotFoundError: If the given path does not exist or is not a file.
    RuntimeError:      If duration could not be determined by any available method.
    ValueError:        If a probe returns an invalid or non-positive duration.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L315)

</details>

<a id="open_dir_in_vlc"></a>
<details>
<summary><code>open_dir_in_VLC</code> — Create a playlist of the files in the specified directory, then play that playlist in VLC. By default, don't search the…</summary>

```python
open_dir_in_VLC(the_dir: 'str | os.PathLike[str]', sort_choice: 'str' = 'sort_by_name', recursive: 'bool' = False, no_start: 'bool' = False) -> 'None'
```

```text
Create a playlist of the files in the specified directory, then play that playlist in VLC. By default, don't search the directory recursively and sort the files by name. Optional arguments allow recursive loading or sorting by modification time. If no_start is True, don't start playback in VLC.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L245)

</details>

<a id="open_in_vlc"></a>
<details>
<summary><code>open_in_vlc</code> — Open a file or directory in VLC. If it's a directory, create a playlist of its contents first. If no_start is True, don…</summary>

```python
open_in_vlc(path: 'str | os.PathLike[str]', no_start: 'bool' = False) -> 'None'
```

```text
Open a file or directory in VLC. If it's a directory, create a playlist of its contents first. If no_start is True, don't start playback in VLC.

Args:
    path:     The file or directory path to open in VLC.
    no_start: If True, VLC will open the file or playlist but not start playback automatically
                (default: False).

Returns:
    None: The function performs the action of opening VLC and does not return any value.

Raises:
    FileNotFoundError: If the specified path does not exist.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L292)

</details>

<a id="open_playlist_in_vlc"></a>
<details>
<summary><code>open_playlist_in_VLC</code> — Open a playlist in VLC. If no_start is True, don't start playback in VLC.</summary>

```python
open_playlist_in_VLC(playlist: 'str | os.PathLike[str]', no_start: 'bool' = False) -> 'None'
```

```text
Open a playlist in VLC. If no_start is True, don't start playback in VLC.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L237)

</details>

<a id="set_system_volume"></a>
<details>
<summary><code>set_system_volume</code> — Set the system volume to a specific level.</summary>

```python
set_system_volume(percent: 'int', tolerance: 'int' = 1, change_mute: "Literal['mute', 'unmute'] | None" = None, force_pactl: 'bool' = False) -> 'None'
```

```text
Set the system volume to a specific level.
On Linux, this function will:
Try to set the PulseAudio default sink volume to 'percent'% via pulsectl,
verify it, and if that fails, fall back to pactl.

Args:
    percent:     Desired volume level (0–100).
    tolerance:   Allowed percent difference when verifying (default: 1%).
    change_mute: If set to "mute", the function will mute the audio instead of
                 setting a specific volume. If set to "unmute", it will unmute
                 the audio. If None, it will not change the mute state.
    force_pactl: If True, always use pactl even if pulsectl is available (default: False).

Returns:
    None

Raises:
    RuntimeError: If the volume could not be set or verified.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/media.py#L111)

</details>

<a id="m-html_files"></a>
### `html_files` — HTML filename munging + multi-file combination

_Layer 7._  `from emmykit.html_files import …`

Strip a leading prefix from filenames or `<title>` tags, and concatenate multiple HTML files into one.

<a id="combine_html_files"></a>
<details>
<summary><code>combine_html_files</code> — Combine multiple HTML files into a single HTML file.</summary>

```python
combine_html_files(file_paths: 'list[str | os.PathLike[str]]', output_file_path: 'str | os.PathLike[str]') -> 'None'
```

```text
Combine multiple HTML files into a single HTML file.
The first file's <head> is preserved, and all <body> contents are concatenated.

Args:
    file_paths:       List of (presorted) file paths to the HTML files to combine.
    output_file_path: Path to save the combined HTML file.

Returns:
    None: the combined HTML is saved to the specified output file path.

Raises:
    Exception:         If there is an error reading any of the HTML files or writing the output file.
    FileNotFoundError: If any of the input files do not exist.
    ValueError:        If the output file path is not valid.
    ImportError:       If BeautifulSoup is not installed.
    RuntimeError:      If the output file cannot be written.
    OSError:           If there is an error during file operations.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/html_files.py#L88)

</details>

<a id="remove_prefix_from_filename"></a>
<details>
<summary><code>remove_prefix_from_filename</code> — If the given filepath's base filename starts with the given prefix:</summary>

```python
remove_prefix_from_filename(filepath: 'str | os.PathLike[str]', prefix: 'str') -> 'bool'
```

```text
If the given filepath's base filename starts with the given prefix:
  1. Remove the prefix (and any " _-" immediately following it).
  2. Move the file (but only if that doesn't cause errors).

Args:
    filepath: The path to the file whose name may need to be changed.
    prefix:   The prefix to remove from the filename.

Returns:
    True:  If the file was successfully renamed, or if it didn't need renaming.
    False: If the file was not renamed because it didn't start with the prefix,
           or if the new filename already exists.

Raises:
    OSError: If the rename operation fails due to an OS error (e.g., permission denied).
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/html_files.py#L15)

</details>

<a id="remove_prefix_from_html_title"></a>
<details>
<summary><code>remove_prefix_from_html_title</code> — If the given filepath is an HTML file and its title starts with the given prefix, remove the prefix from the title and …</summary>

```python
remove_prefix_from_html_title(filepath: 'str | os.PathLike[str]', prefix: 'str') -> 'bool'
```

```text
If the given filepath is an HTML file and its title starts with the given prefix, remove the prefix from the title and save the file, then return True. Otherwise, return False.
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/html_files.py#L59)

</details>

<a id="m-llm"></a>
### `llm` — LLM wrapper, config dataclasses, model selection

_Layer 8._  `from emmykit.llm import …`

The 2 000-LOC `LLMs` class wraps `litellm`/`tiktoken` with `LLMConfig`/`ModelInfo` dataclasses, a `SelectionStrategy` enum, and lazy backoff via tenacity.

<a id="llmconfig"></a>
<details>
<summary><code>LLMConfig</code> — Configuration for LLM selection and usage. Data only.</summary>


```text
Configuration for LLM selection and usage. Data only.
```

**Fields:** `only_cleared_models`, `only_local_models`, `allow_local_models`, `ollama_base_url`, `vllm_base_url`, `rate_throttle`, `rate_headroom`, `rate_retry_max_attempts`, `rate_retry_max_wait`, `rate_db_path`, `availability_probe`, `availability_probe_ttl_sec`, `availability_probe_timeout`, `availability_probe_allow_costly`, `selection_strategy`, `min_context_tokens`, `assumed_prompt_tokens`, `assumed_output_tokens`, `candidate_models`, `default_temperature`, `max_tokens`, `model_scores`, `prefer_code`, `prefer_low_TTFT`, `prefer_local`, `max_estimated_cost`, `speed_floor`, `model_filter`, `provider_filter`, `weight_price`, `weight_code_skill`, `weight_general_skill`, `weight_TTFT`, `weight_speed`, `weight_nonlocal_penalty`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/llm.py#L31)

</details>

<a id="llms"></a>
<details>
<summary><code>LLMs</code> — - Routes via LiteLLM</summary>

```python
LLMs() -> 'None'
```

```text
- Routes via LiteLLM
- Builds ModelInfo list, filters by availability/context
- Applies registered/built-in selection strategy
- Exposes stable send_prompt(...)
```

**Public methods:** `alternative_model`, `apply_config`, `describe_selection`, `get_config`, `list_candidates`, `refresh_selection`, `register_strategy`, `send_prompt`, `tokenize`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/llm.py#L143)

</details>

<a id="modelinfo"></a>
<details>
<summary><code>ModelInfo</code> — Information about a candidate Large Language Model (LLM).</summary>


```text
Information about a candidate Large Language Model (LLM).
```

**Fields:** `name`, `provider`, `context_window`, `input_cost_per_token`, `output_cost_per_token`, `available`, `is_local`, `cleared`, `runtime`, `parameters`, `code_skill`, `general_skill`, `TTFT`, `speed`, `meta`.

**Public methods:** `estimate_cost`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/llm.py#L102)

</details>

<a id="selectioncontext"></a>
<details>
<summary><code>SelectionContext</code> — Context passed to strategy functions.</summary>

```python
SelectionContext(tokens_in: 'int', tokens_out: 'int', min_context_tokens: 'int', require_local: 'bool' = False, require_cleared: 'bool' = False, extras: 'dict[str, Any]' = <factory>) -> None
```

```text
Context passed to strategy functions.
```

**Fields:** `tokens_in`, `tokens_out`, `min_context_tokens`, `require_local`, `require_cleared`, `extras`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/llm.py#L132)

</details>

<a id="selectionstrategy"></a>
<details>
<summary><code>SelectionStrategy</code> — Enumeration of selection strategies for model selection.</summary>

```python
SelectionStrategy(*values)
```

```text
Enumeration of selection strategies for model selection.
```

**Public methods:** `capitalize`, `casefold`, `center`, `count`, `encode`, `endswith`, `expandtabs`, `find`, `format`, `format_map`, `index`, `isalnum`, `isalpha`, `isascii`, `isdecimal`, `isdigit`, `isidentifier`, `islower`, `isnumeric`, `isprintable`, `isspace`, `istitle`, `isupper`, `join`, `ljust`, `lower`, `lstrip`, `maketrans`, `partition`, `removeprefix`, `removesuffix`, `replace`, `rfind`, `rindex`, `rjust`, `rpartition`, `rsplit`, `rstrip`, `split`, `splitlines`, `startswith`, `strip`, `swapcase`, `title`, `translate`, `upper`, `zfill`.

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/llm.py#L20)

</details>

<a id="strategyfn"></a>
<details>
<summary><code>StrategyFn</code> — TypeAlias</summary>

```python
StrategyFn: TypeAlias = collections.abc.Callable[[collections.abc.Sequence[emmykit.llm.ModelInfo], emmykit.llm.SelectionContext], emmykit.llm.ModelInfo]
```

[source ↗](https://github.com/killett/emmykit/blob/main/src/emmykit/llm.py#L141)

</details>

## License

Apache 2.0 — see [LICENSE](LICENSE). Changelog at [CHANGELOG.md](CHANGELOG.md).
