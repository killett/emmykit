# emmykit

Personal Python utilities, formerly the single-file module `univ_defs.py`.

## Install

```bash
pip install emmykit
```

## Use

```python
from emmykit import parse_datetime, human_bytesize, Options, LLMs
```

`emmykit` re-exports every public name that the legacy `univ_defs` exposed via
`from univ_defs import *`. Migration is a single string replacement:
`univ_defs` → `emmykit`.

## Layout

The codebase is split into 32 modules across 9 dependency layers (constants → LLMs).
See [`docs/design.md`](docs/design.md) for the layer map and `__all__` rules.
Underscore-prefixed names are private.
