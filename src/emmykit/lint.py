"""lint — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Type

from emmykit.constants import (
    ANSI_CYAN, ANSI_GREEN, ANSI_RED, ANSI_RESET, ANSI_YELLOW,
    BACKTICK, HORIZONTAL_ELLIPSIS, LDQUOTE, LSQUOTE, RDQUOTE, RSQUOTE,
)
from emmykit.logging_utils import fallback_logging_config, return_method_name
from emmykit.options import Options
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import ensure_file, safe_exists, safe_is_dir, safe_is_file
from emmykit.io_subprocess import my_fopen
from emmykit.diff_view import diff_and_confirm
from emmykit.humanize import sci_exp
from emmykit.introspection import compile_code


def _make_format_checker() -> Type[Any]:
    """Factory function to create the FormatChecker class with the necessary imports."""
    import ast

    class FormatChecker(ast.NodeVisitor):
        """
        Walks a module AST and collects formatting violations:
        - missing type hints on params / return
        - missing docstring or incorrect docstring quote style
        """

        _DocNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef

        def __init__(self, source: str, doc_style: str = "None") -> None:
            """Initialize the FormatChecker with the source code string."""
            self.source = source
            self.doc_style = doc_style  # "None", "NumPy", "Google", "reStructuredText"
            self.errors: list[tuple[str, str, str, int]] = []
            self._seen_funcs: set[int] = set()  # keep track of which FunctionDef/AsyncFunctionDef nodes we've already checked

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            """Visit a FunctionDef node and check for formatting violations."""
            self._check_function(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            """Visit an AsyncFunctionDef node and check for formatting violations."""
            self._check_function(node)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            """Visit a ClassDef node and check for formatting violations."""
            self._check_docstring(node, f'class "{node.name}"')
            init = self._find_init(node)
            if init:
                self._check_function(init, in_method=True, container=f'class "{node.name}"')
            self.generic_visit(node)

        def _find_init(self, node: ast.ClassDef) -> ast.FunctionDef | None:
            """Find the __init__ method in a class definition."""
            for elt in node.body:
                if isinstance(elt, (ast.FunctionDef, ast.AsyncFunctionDef)) and elt.name == "__init__":
                    return elt  # type: ignore
            return None

        def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *,
                            in_method: bool = False, container: str | None = None) -> None:
            """Check a function or method node for formatting violations.
            If 'in_method' is True, it indicates that this is a method (e.g. inside a class).
            If 'container' is provided, it indicates the context (e.g. class name)."""
            if id(node) in self._seen_funcs:  # ←─ skip if we've already run this exact node
                return
            self._seen_funcs.add(id(node))
            who = (f'function "{node.name}"' if container is None else f'{container} → method "{node.name}"')
            self._check_docstring(node, who)

            missing: list[str] = []
            args = [a for a in node.args.args if a.arg != "self"]
            for a in args + node.args.kwonlyargs:
                if a.annotation is None:
                    missing.append(f'param "{a.arg}"')
            if node.args.vararg and node.args.vararg.annotation is None:
                missing.append(f'param "*{node.args.vararg.arg}"')
            if node.args.kwarg and node.args.kwarg.annotation is None:
                missing.append(f'param "**{node.args.kwarg.arg}"')
            if node.returns is None:
                missing.append("return")
            if missing:
                self.errors.append(("function", node.name,
                                    "missing type hints for " + ", ".join(missing),
                                    node.lineno))

        def _check_docstring(self, node: _DocNode, who: str) -> None:
            """
            Check a node for a docstring and its formatting.
            An error is added to self.errors if:
              - The node has no docstring
              - The docstring is not formatted correctly
              - There is more than one docstring
            The 'who' parameter is a string describing the context (e.g. function or class name).
            """
            if not node.body or not isinstance(node.body[0], ast.Expr):
                self.errors.append((node.__class__.__name__.casefold(), who, "no docstring",
                                    node.lineno))
                return

            expr = node.body[0]
            if not (isinstance(expr.value, ast.Constant) and isinstance(expr.value.value, str)):
                self.errors.append((node.__class__.__name__.casefold(), who, "no docstring",
                                    node.lineno))
                return

            # Recover the exact literal to verify triple-double-quote
            literal = ast.get_source_segment(self.source, expr.value) or ""
            first_line = literal.strip().splitlines()[0]
            if first_line.startswith("'''"):
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    'docstring should use triple double quotes ("""...""")',
                                    node.lineno))

            # Now scan for any extra standalone triple‐quoted strings
            for extra in node.body[1:]:
                # Only look at Exprs, i.e. un‐assigned string literals
                if  isinstance(extra, ast.Expr) \
                and isinstance(extra.value, ast.Constant) \
                and isinstance(extra.value.value, str):
                    literal = ast.get_source_segment(self.source, extra.value) or ""
                    first = literal.strip().splitlines()[0]
                    # If it starts with triple quotes, it's an extra docstring
                    if first.startswith(('"""', "'''")):
                        self.errors.append((node.__class__.__name__.casefold(),
                                            who, "extra docstring", extra.lineno))

            # Check the docstring style
            self._check_docstring_style(node, who)

        def _check_docstring_style(self, node: _DocNode, who: str) -> None:
            """Dispatch to the style‑specific docstring checker."""
            if not self.doc_style or self.doc_style.casefold() == "none":
                return
            checker = {
                "Google"           : self._check_google_docstring,
                # "NumPy"              : self._check_numpy_docstring,
                # "reStructuredText" : self._check_rst_docstring,
            }.get(self.doc_style)
            logging.warning("Consider adding an exception to the docstring checker: if the function is less than 5(?) lines, allow a single line docstring without the required sections. Also, if there are no args or no return value or it doesn't raise exceptions.")
            if checker is not None:
                checker(node, who)

        def _check_google_docstring(self, node: _DocNode, who: str) -> None:
            """
            Very basic Google‑style docstring validator:
            - must have a 'Args:' and 'Returns:' section header
            - every non‑self arg must be listed under Parameters
            """
            doctype = "Google"
            # Get the cleaned docstring
            doc = ast.get_docstring(node)
            if not doc:
                return  # already flagged as missing

            lines = doc.splitlines()
            # Locate the section headers
            try:
                args_idx = next(i for i, L in enumerate(lines) if L.strip() == "Args:")
            except StopIteration:
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    f"{doctype} docstring missing 'Args' section",
                                    node.lineno))
                return

            if not any(L.strip() == "Returns:" for L in lines):
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    f"{doctype} docstring missing 'Returns' section",
                                    node.lineno))

            # Collect documented params: lines immediately under 'Parameters'
            documented = set()
            for line in lines[args_idx+1:]:
                if not line.strip():
                    break
                m = re.match(r'^(\w+)\s*:\s*(.+)$', line)
                if m:
                    documented.add(m.group(1))

            # Get function args (excluding self)
            sig_args = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig_args = [a.arg for a in node.args.args if a.arg != "self"]

            missing = [a for a in sig_args if a not in documented]
            if missing:
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    f"{doctype} docstring missing parameter(s): " + ", ".join(missing), node.lineno))

        def _check_numpy_docstring(self, node: _DocNode, who: str) -> None:
            """
            Very basic NumPy‑style docstring validator:
            - must have a 'Parameters' and 'Returns' section header
            - every non‑self arg must be listed under Parameters
            """
            doctype = "NumPy"
            # Get the cleaned docstring
            doc = ast.get_docstring(node)
            if not doc:
                return  # already flagged as missing

            lines = doc.splitlines()
            # Locate the section headers
            try:
                params_idx = next(i for i, L in enumerate(lines) if L.strip() == "Parameters")
            except StopIteration:
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    f"{doctype} docstring missing 'Parameters' section",
                                    node.lineno))
                return

            if not any(L.strip() == "Returns:" for L in lines):
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    f"{doctype} docstring missing 'Returns' section",
                                    node.lineno))

            # Collect documented params: lines immediately under 'Parameters'
            documented = set()
            for line in lines[params_idx+1:]:
                if not line.strip():
                    break
                m = re.match(r'^(\w+)\s*:\s*(.+)$', line)
                if m:
                    documented.add(m.group(1))

            # Get function args (excluding self)
            sig_args = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig_args = [a.arg for a in node.args.args if a.arg != "self"]

            missing = [a for a in sig_args if a not in documented]
            if missing:
                self.errors.append((node.__class__.__name__.casefold(), who,
                                    f"{doctype} docstring missing parameter(s): " + ", ".join(missing), node.lineno))

    return FormatChecker

FormatChecker = _make_format_checker()

def check_python_formatting(path: str | os.PathLike[str], diff_choice: int = 1) -> bool:
    """
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
    """
    import ast
    fallback_logging_config()
    path = ensure_file(path)
    src  = my_fopen(   path)
    if not src:
        logging.error("❌ Failed to open file: %s", os.fspath(path))
        return False

    if compile_code(src):
        logging.info("✅ %s compiled successfully.", os.fspath(path))

    logging.warning("LOOK FOR logging.debug STATEMENTS THAT USE F-STRINGS OR THAT DON'T HAVE GUARDS!!")

    if BACKTICK in src:
        logging.warning("File %s contains the backtick character (%r). Use straight quotation marks (') instead.", os.fspath(path), BACKTICK)
        if not ask_and_replace(old_str=BACKTICK, new_str="'", path=path, label="backtick",
                               diff_choice=diff_choice,
                               description=f"Replace backtick ({BACKTICK}) with straight apostrophe (')"):
            return False
    if LSQUOTE in src or RSQUOTE in src:
        logging.warning("File %s contains curly single quotation marks (%r or %r). Use straight apostrophes (') instead.", os.fspath(path), LSQUOTE, RSQUOTE)
        if not ask_and_replace(old_str=LSQUOTE, new_str="'", path=path, label="left-curly-apostrophe",
                               diff_choice=diff_choice,
                               description=f"Replace left curly apostrophe ({LSQUOTE}) with straight apostrophe (')"):
            return False
        if not ask_and_replace(old_str=RSQUOTE, new_str="'", path=path, label="right-curly-apostrophe",
                               diff_choice=diff_choice,
                               description=f"Replace right curly apostrophe ({RSQUOTE}) with straight apostrophe (')"):
            return False
    if LDQUOTE in src or RDQUOTE in src:
        logging.warning("File %s contains curly double quotation marks (%r or %r). Use straight quotation marks (\") instead.", os.fspath(path), LDQUOTE, RDQUOTE)
        if not ask_and_replace(old_str=LDQUOTE, new_str='"', path=path,
                               label="left-curly-quotation-mark",
                               diff_choice=diff_choice,
                               description=f'Replace left curly double quotation mark ({LDQUOTE}) with straight double quotation mark (")'):
            return False
        if not ask_and_replace(old_str=RDQUOTE, new_str='"', path=path, label="right-curly-quotation-mark",
                               diff_choice=diff_choice,
                               description=f'Replace right curly double quotation mark ({RDQUOTE}) with straight double quotation mark (")'):
            return False
    if HORIZONTAL_ELLIPSIS in src:
        logging.warning("File %s contains the horizontal ellipsis character (%r). Use three periods (...) instead.", os.fspath(path), HORIZONTAL_ELLIPSIS)
        if not ask_and_replace(old_str=HORIZONTAL_ELLIPSIS, new_str="...", path=path,
                               label="horizontal-ellipsis", diff_choice=diff_choice,
                               description=f"Replace horizontal ellipsis ({HORIZONTAL_ELLIPSIS}) with three periods (...)"):
            return False

    try:
        tree = ast.parse(src, path)
    except SyntaxError:
        logging.exception("❌ %s contains a syntax error.", os.fspath(path))
        return False

    checker = FormatChecker(src)
    checker.visit(tree)

    if not checker.errors:
        logging.info("🎉 All functions and classes conform to the custom formatting rules.")
    else:
        max_lineno = max(err[3] for err in checker.errors)
        the_digits = sci_exp(max_lineno) + 1
        for kind, name, msg, lineno in checker.errors:
            logging.error(f"{lineno:>{the_digits}} – {kind.capitalize()} {name}: {msg}")

    return True

def run_flake8(options: Options, path: str | os.PathLike[str],
               ignore_codes: list[str] | None = None,
               max_line_length: int = 100) -> flake8.Report:
    """
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
    """
    from flake8.api import legacy as flake8
    # Ensures our env manager installs the plugin; no runtime effect on Flake8.
    try:  # Flake8: "no quality assurance": F401 = Pyflakes code for "module imported but unused"
        import bugbear  # noqa: F401
        # "B" = All standard Bugbear rules (B001...B8xx). "B9" = All optional/opinionated B9xx rules.
        options.bugbear_choice = "B,B9"
        logging.info("Using flake8-bugbear checks.")
    except ImportError:
        logging.error("flake8-bugbear is not installed, so no Bugbear checks will be performed.")
        options.bugbear_choice = None
    fallback_logging_config()
    if ignore_codes is None:
        ignore_codes = []
    if not isinstance(ignore_codes, list):
        raise TypeError("'ignore_codes' must be a list of strings.")
    if not all(isinstance(code, str) for code in ignore_codes):
        raise TypeError("All elements in 'ignore_codes' must be strings.")
    path        = ensure_file(path)
    kwargs = dict(max_line_length=max_line_length, ignore=ignore_codes)
    if options.bugbear_choice:
        codes  = tuple(c.strip() for c in options.bugbear_choice.split(",") if c.strip())
        kwargs["extend_select"] = codes
        if any(c in {"B9", "B950"} for c in codes):
            kwargs["extend_ignore"] = ("E501",)  # E501 is redundant if B9xx rules are enabled
    style_guide = flake8.get_style_guide(**kwargs)
    report      = style_guide.check_files([path])
    if report.total_errors == 0:
        logging.info("✅ No Flake8 violations found in %s.", os.fspath(path))
        return report
    logging.error("Found %d total violations in %s:", report.total_errors, os.fspath(path))
    for stat in report.get_statistics(""):
        logging.error("  %s", stat)
    return report

def _gather_flake8_issues(options: Options, path: str | os.PathLike[str],
                          ignore_codes: list[str] | None = None,
                          max_line_length: int = 100) -> dict[str, str]:
    """
    Returns a dict mapping each Flake8 error code to its first-seen description
    in the file at 'path'.
    Tries the 'flake8' CLI (fast), but if it's not on PATH, falls back
    to an in-process Application/API solution.

    Args:
        options:         Options instance containing various settings. Contains:
                             - bugbear_choice: Whether to include flake8-bugbear checks (and if so, which ones?)
        path:            The path to the Python file to check.
        ignore_codes:    A list of Flake8 error/warning codes to ignore.
        max_line_length: The (custom) maximum allowed line length for E501 checks.

    Returns:
        A dictionary mapping Flake8 error codes to their descriptions.

    Raises:
        FileNotFoundError: If the specified file does not exist.
    """
    ignores = list(ignore_codes) if ignore_codes else []
    try:
        return _gather_via_cli(options, path, max_line_length, ignores)
    except FileNotFoundError:
        return _gather_via_app(options, path, max_line_length, ignores)

def _gather_via_cli(options: Options, path: str | os.PathLike[str],
                    max_line_length: int, ignore_codes: list[str]) -> dict[str, str]:
    """Use the flake8 CLI to gather codes and descriptions."""
    import subprocess
    path = ensure_file(path)
    fmt = "%(row)d:%(col)d: %(code)s %(text)s"
    args = [  # sys.executable ensures we use the same Python interpreter (probably in a venv)
        sys.executable, "-m", "flake8",
        f"--max-line-length={max_line_length}",
        f"--ignore={','.join(ignore_codes)}",
        f"--format={fmt}",
        os.fspath(path),
    ]
    if options.bugbear_choice:
        args.insert(-1, f"--extend-select={options.bugbear_choice}")
        selected = {c.strip() for c in options.bugbear_choice.split(",") if c.strip()}
        if selected & {"B9", "B950"}:
            args.insert(-1, "--extend-ignore=E501")  # E501 is redundant if B9xx rules are enabled
    proc = subprocess.run(args, capture_output=True, text=True)
    codes: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        # e.g. "12:5: E302 expected 2 blank lines, found 1"
        parts = line.split(": ", 1)
        if len(parts) != 2:
            continue
        _, rest = parts
        code, desc = rest.split(" ", 1)
        codes.setdefault(code, desc)
    return codes

def _gather_via_app(options: Options, path: str | os.PathLike[str],
                    max_line_length: int, ignore_codes: list[str]) -> dict[str, str]:
    """Use the flake8 Application API to gather codes and descriptions."""
    from flake8.main.application import Application
    from flake8.formatting.base  import BaseFormatter
    from flake8.violation        import Violation
    path = ensure_file(path)

    class CodeDictFormatter(BaseFormatter):
        """Custom formatter that collects codes and their first descriptions."""

        def __init__(self, options: dict[str, str]) -> None:
            """Initialize the formatter with options."""
            super().__init__(options)
            self.codes: dict[str, str] = {}

        def format(self, error: Violation) -> str:
            """Format a single error, capturing its code and description."""
            # capture the first description we see for each code
            self.codes.setdefault(error.code, error.text)
            # suppress any actual stdout
            return ""

    class CodeDictApp(Application):
        """Custom Application subclass to use our CodeDictFormatter."""

        def make_formatter(self) -> BaseFormatter:
            """Create a custom formatter that collects codes and descriptions."""
            # force our custom formatter
            self.formatter = CodeDictFormatter(self.options)
            return self.formatter

    app = CodeDictApp()
    # supply exactly the same CLI settings in-process
    cli_args = [f"--max-line-length={max_line_length}", f"--ignore={','.join(ignore_codes)}", os.fspath(path)]
    if options.bugbear_choice:
        cli_args.insert(-1, f"--extend-select={options.bugbear_choice}")
        selected = {c.strip() for c in options.bugbear_choice.split(",") if c.strip()}
        if selected & {"B9", "B950"}:
            cli_args.insert(-1, "--extend-ignore=E501")  # E501 is redundant if B9xx rules are enabled
    # this will parse, run checks, and invoke our formatter behind the scenes
    app.run(cli_args)
    # the formatter collected everything into .codes
    return app.formatter.codes

def get_autopep8_fixable_codes() -> set[str]:
    """
    Run 'autopep8 --list-fixes' (via subprocess) to discover exactly
    which Flake8 error‐codes autopep8 knows how to fix.
    Returns a set like {"E101","E111", ...}.
    """
    import subprocess
    fallback_logging_config()
    try:  # sys.executable ensures we use the same Python interpreter (probably in a venv)
        proc = subprocess.run([sys.executable, "-m", "autopep8", "--list-fixes"],
                              capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logging.warning("autopep8 not found or failed.", exc_info=True)
        # autopep8 not on PATH or error—assume nothing fixable
        return set()

    fixable: set[str] = set()
    for line in proc.stdout.splitlines():
        # the output looks like:
        #   E101 - indentation not consistent
        #   E111 - indent does not match any outer indentation level
        # so take the code before the colon
        if " - " in line:
            code = line.split(" - ", 1)[0].strip()
            if code:
                fixable.add(code)
    return fixable

def ask_and_autopep8(path: str | os.PathLike[str], code: str,
                     description:   str = "", diff_choice: int = 1,
                     changed_color: str = ANSI_CYAN,
                     deleted_color: str = ANSI_RED,
                     added_color:   str = ANSI_YELLOW) -> bool:
    """
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
    """
    import autopep8
    fallback_logging_config()
    path = ensure_file(path)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("At the top of the function %s(), diff_choice=%s", return_method_name(), diff_choice)
    # The number of blank lines expected in various contexts.
    blank_line_overrides = {
        "E301" : 1,  # expected 1 blank line, found 0
        "E302" : 2,  # expected 2 blank lines, found 1
        "E303" : 5,  # too many blank lines (give a lot of context to see what is around the blank lines)
        "E305" : 2,  # expected 2 blank lines after class/method
    }
    orig_text = my_fopen(path)
    if not orig_text:
        raise ValueError("Empty file: %s", os.fspath(path))
    changed_text = orig_text
    for level in (0, 1, 2):  # try with 0, 1, then 2 "-a" flags
        flags = ["-a"] * level
        the_fix = f"autopep8 {' '.join(flags)} --select={code}"
        args = [f"--select={code}", "--in-place"] + flags + [os.fspath(path)]
        opts      = autopep8.parse_args(args)
        candidate = autopep8.fix_code(orig_text, options=opts)
        if candidate != orig_text:
            changed_text = candidate
            break
    if changed_text == orig_text:
        logging.info("No changes for %s in %s using %s.", code, os.fspath(path), the_fix)
        return True
    if not isinstance(diff_choice, int) or diff_choice < 0:
        logging.error("Invalid diff_choice=%d. Must be a non-negative integer.", diff_choice)
        return False
    # If this is a blank‑line code, force unified with the number of context lines specified in blank_line_overrides.
    if code in blank_line_overrides:
        # +1 so that unified_diff(n=override‑1) gives you exactly override context
        effective = blank_line_overrides[code] + 1
    else:
        effective = diff_choice
    return diff_and_confirm(orig_text, changed_text, path, label=code, diff_choice=effective,
                            changed_color=changed_color, deleted_color=deleted_color, added_color=added_color,
                            the_fix=the_fix, description=description)

def ask_and_replace(old_str: str, new_str: str,
                    path: str | os.PathLike[str],  label: str = "",
                    diff_choice:   int = 1, description: str = "",
                    changed_color: str = ANSI_CYAN,
                    deleted_color: str = ANSI_RED,
                    added_color:   str = ANSI_YELLOW,
                    skip_compile: bool = False,
                    verbose:      bool = True) -> bool:
    """
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
    """
    fallback_logging_config()
    path         = ensure_file(path, verbose=verbose)
    orig_text    = my_fopen(path, verbose=verbose)
    if not orig_text:
        if verbose:
            logging.info("Skipping empty file: %s", os.fspath(path))
        return True  # skip empty files silently. continue processing other files by returning True.
    changed_text = orig_text.replace(old_str, new_str)
    if changed_text == orig_text:
        if verbose:
            if label:
                logging.info("No occurrences of %s in %s.", label, os.fspath(path))
            else:
                logging.info("No occurrences of '%s' in %s.", old_str, os.fspath(path))
        return True
    the_fix = f"replace '{old_str}' with '{new_str}'"
    return diff_and_confirm(orig_text, changed_text, path, label=label, diff_choice=diff_choice,
                            changed_color=changed_color, deleted_color=deleted_color, added_color=added_color,
                            skip_compile=skip_compile, the_fix=the_fix, description=description)

def _validate_glob_pattern(pattern: str) -> None:
    """Basic validation for glob pattern (non-empty string)."""
    if not isinstance(pattern, str) or not pattern.strip():
        raise ValueError("glob_pattern must be a non-empty string.")

def _resolve_dir(dir_arg: str | None) -> Path:
    """Resolve the directory from the command line argument."""
    if dir_arg:
        p = ensure_path(dir_arg)
    else:
        p = Path.cwd().expanduser().resolve(strict=True)
    if not safe_exists(p):
        raise FileNotFoundError(f"Directory does not exist: {os.fspath(p)}")
    if not safe_is_dir(p):
        raise NotADirectoryError(f"Path is not a directory: {os.fspath(p)}")
    return p

def _collect_files(root: Path, pattern: str, recursive: bool) -> list[Path]:
    """Collect files matching the glob pattern from root."""
    search_iter: Iterable[Path]
    if recursive:
        search_iter = root.rglob(pattern)
    else:
        search_iter = root.glob(pattern)

    files = [p for p in search_iter if safe_is_file(p)]
    return files

def multireplace(options: Options, verbose: bool = True) -> None:
    """
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
    """
    fallback_logging_config()
    try:
        _validate_glob_pattern(options.args.glob_pattern)
    except Exception as e:
        logging.error(f"Invalid glob pattern: {e}")
        sys.exit(2)

    try:
        dir = _resolve_dir(options.args.dir)
    except Exception as e:
        logging.error(str(e))
        sys.exit(2)

    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Directory: %s", dir)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Glob pattern: %s", options.args.glob_pattern)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Recursive: %s", options.args.recursive)

    files = _collect_files(dir, options.args.glob_pattern, options.args.recursive)

    if not files:
        if verbose: logging.warning("No files matched the given pattern.")
        return

    if verbose:
        logging.info("Found %d file(s) to process:", len(files))
        num_files  = len(files)
        max_digits = len(str(num_files))
        for i, f in enumerate(files, start=1):
            logging.info(f"{i:>{max_digits}}/{num_files}: {f}")
        logging.info("==========================================")

    for f in files:
        try:
            if not ask_and_replace(old_str=options.args.old_str,
                                   new_str=options.args.new_str,
                                   path=str(f), verbose=verbose):
                break
        except KeyboardInterrupt:
            logging.warning("Interrupted by user.")
            sys.exit(130)
        except Exception as e:
            if verbose:
                logging.error(f"Error processing {f}: {e}")

    if verbose: logging.info("Done.")

def interactive_flake8(options: Options,
                       path: str | os.PathLike[str],
                       ignore_codes: list[str] | None = None,
                       diff_choice:     int =   1,
                       max_line_length: int = 100,
                       changed_color:   str = ANSI_CYAN,
                       deleted_color:   str = ANSI_RED,
                       added_color:     str = ANSI_YELLOW) -> bool:
    """
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
    """
    fallback_logging_config()
    path = ensure_file(path)
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("At the top of the function %s(), diff_choice=%s", return_method_name(), diff_choice)
    if ignore_codes is None:
        ignore_codes = []
    if not run_flake8(options, path, ignore_codes=ignore_codes, max_line_length=max_line_length):
        logging.info("No flake8 errors—nothing to do.")
        return True
    codes = _gather_flake8_issues(options, path, ignore_codes=ignore_codes, max_line_length=max_line_length)
    fixable_codes = get_autopep8_fixable_codes()
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Autopep8 can fix these codes: %s", fixable_codes)
    touched_code = False
    for code, desc in codes.items():
        if code not in fixable_codes:
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Skipping %s: no autopep8 fixer", code)
            continue
        logging.info("\n→ %s: %s", ANSI_RED + code + ANSI_RESET, ANSI_YELLOW + desc + ANSI_RESET)
        if not ask_and_autopep8(path, code, desc, diff_choice=diff_choice,
                                changed_color=changed_color, deleted_color=deleted_color, added_color=added_color):
            return False
        touched_code = True
    if touched_code:
        logging.info("%sDone. Re-running flake8 to confirm fixes...%s", ANSI_GREEN, ANSI_RESET)
        run_flake8(options, path, ignore_codes=ignore_codes, max_line_length=max_line_length)
    else:
        logging.info("No fixable flake8 codes found or no changes made.")
    return True

def run_mypy(options: Options,
             path: str | os.PathLike[str]) -> None:
    """
    Run basic mypy static analysis on the specified file.

    Args:
        options: The parsed command-line options. (Currently unused but included for consistency.)
        path:    Path to the Python file to analyze.

    Returns:
        None.
    """
    try:
        from importlib import import_module
        mypy_api = import_module("mypy.api")
    except ModuleNotFoundError:
        logging.error("mypy is not installed.")
        return

    # Note: mypy analyzes files (not raw strings), so we pass the path.
    # This is the most basic run with default settings.
    mypy_stdout, mypy_stderr, mypy_exit = mypy_api.run([str(path)])

    # You can inspect these variables or integrate them with your own logging/handling:
    #   - mypy_stdout: str with human-readable diagnostics
    #   - mypy_stderr: str with internal mypy errors (if any)
    #   - mypy_exit:   int exit code (0 = success, 1 = type issues found, 2 = mypy failure)
    if mypy_stdout:
        logging.info("mypy output:\n%s", mypy_stdout)
    if mypy_stderr:
        logging.error("mypy internal errors:\n%s", mypy_stderr)
    if mypy_exit == 0:
        logging.info("mypy completed successfully with no type issues.")
    elif mypy_exit == 1:
        logging.warning("mypy completed with type issues found.")
    else:
        logging.error("mypy failed with exit code %d.", mypy_exit)
