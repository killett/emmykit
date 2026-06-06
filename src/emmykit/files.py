"""files — extracted from univ_defs.py."""

from __future__ import annotations

import logging
import os
import re
import sys

from emmykit.constants import DEFAULT_ENCODING
from emmykit.extensions import ALL_KNOWN_EXTENSIONS
from emmykit.logging_utils import fallback_logging_config
from emmykit.options import Options
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import ensure_file, safe_exists, safe_is_dir, safe_is_file, safe_size
from emmykit.diff_view import my_diff
from emmykit.humanize import human_bytesize

def download_file(url: str, dest: str | os.PathLike[str], retries: int = 5,
                  chunk_size: int = 1 << 20, timeout: int = 30,
                  headers: dict[str, str] | None = None) -> None:
    """
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
    """
    import time
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    import socket

    fallback_logging_config()
    dest = ensure_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + ".part")

    base_headers = {"Accept-Encoding" : "identity",
                    "User-Agent"      : "python-download/1.0", }
    eff_headers  = {**base_headers, **(headers or {})}

    succeeded = False  # Track if download succeeded

    # Remove any stale partial to avoid skewing free-space checks.
    try:
        if safe_exists(temp):
            temp.unlink()
    except OSError as e:
        # If we can't remove it, we'll truncate on open later; free-space check may be conservative.
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Could not remove stale partial file %s: %s", os.fspath(temp), e)

    # Pre-flight: attempt to learn expected size and check free space.
    expected: int | None = None
    try:
        req_head = Request(url, headers=eff_headers, method="HEAD")
        with urlopen(req_head, timeout=timeout) as r:
            cl = r.headers.get("Content-Length")
            if cl:
                try:
                    expected = int(cl.strip())
                except ValueError:
                    expected = None
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("HEAD probe failed (%s); proceeding without pre-known size.", e)

    if expected is not None:
        # Skip re-download if size matches on disk already.
        if safe_exists(dest):
            try:
                if (dest_size := safe_size(dest)) is not None and dest_size == expected:
                    logging.info("File already present with expected size; skipping: %s", os.fspath(dest))
                    return
                elif dest_size is not None:
                    logging.info("File already present but size mismatch (have %s, need %s); re-downloading: %s",
                                 human_bytesize(dest_size), human_bytesize(expected), os.fspath(dest))
                elif dest_size is None:
                    logging.warning("File size is unknown (permissions?): %s", os.fspath(dest))
                    sys.exit(1)
                else:
                    logging.error(f"File {os.fspath(dest)} exists but has a VERY CONFUSING size mismatch (have {dest_size}, need {expected}).")
            except OSError as e:
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Could not remove stale partial file %s: %s", os.fspath(temp), e)
        free_bytes = query_free_space(dest)
        if free_bytes < expected:
            raise SystemExit(f"Not enough disk space: need {human_bytesize(expected)}, have {human_bytesize(free_bytes)}")

    backoff = 1.0
    last_err: Exception | None = None

    for attempt in range(1, max(1, retries) + 1):
        try:
            logging.info("Downloading %s → %s (attempt %d/%d)", url, dest, attempt, retries)
            req = Request(url, headers=eff_headers)
            with urlopen(req, timeout=timeout) as resp:
                total = resp.headers.get("Content-Length")
                total_i = None
                if total:
                    try:
                        total_i = int(total.strip())
                    except ValueError as e:
                        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Failed to parse Content-Length: %s", e)
                # Re-check space at the moment of download if size is known.
                if total_i is not None:
                    free_bytes = query_free_space(dest)
                    if free_bytes < total_i:
                        raise SystemExit(
                            f"Not enough disk space: need {human_bytesize(total_i)}, have {human_bytesize(free_bytes)}"
                        )

                with temp.open("wb") as f:
                    downloaded = 0
                    last_bucket = -1
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_i:
                            # Lightweight textual progress (kept minimal for logging)
                            pct = int(downloaded * 100 / total_i)
                            bucket = pct // 10
                            # Log just once every ~10% but not at 0%
                            if pct and pct % 10 == 0 and bucket != last_bucket:
                                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("... %d%% (%s out of %s)", pct, human_bytesize(downloaded), human_bytesize(total_i))
                                last_bucket = bucket
                    f.flush()
                    os.fsync(f.fileno())

            # Verify size if Content-Length available
            if total_i is not None:
                if (actual_size := safe_size(temp)) is None:
                    raise IOError(f"Could not determine size of downloaded file {os.fspath(temp)}")
                if actual_size != total_i:
                    raise IOError(f"Incomplete download: expected {total_i} bytes, got {actual_size} bytes")
            temp.replace(dest)
            logging.info("Saved %s (%s)", os.fspath(dest), human_bytesize(safe_size(dest)))
            succeeded = True
            return
        except (HTTPError, URLError, socket.timeout, IOError) as e:
            last_err = e
            logging.warning("Download failed (%s).", e)
            if attempt >= retries:
                break
            sleep_s = backoff
            backoff = min(backoff * 2, 30.0)  # cap backoff
            logging.info("Retrying in %.1f seconds...", sleep_s)
            time.sleep(sleep_s)
        except Exception as e:
            # Unexpected errors: don't loop indefinitely
            last_err = e
            logging.exception("Unexpected error during download.")
            break
        finally:
            try:
                if not succeeded and safe_exists(temp):
                    temp.unlink()
            except OSError as e:
                if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("Failed to remove temporary file %s: %s", os.fspath(temp), e)

    raise SystemExit(f"Failed to download {url} after {retries} attempts. Last error: {last_err}")

def query_free_space(path: str | os.PathLike[str]) -> int:
    """
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
    """
    p = ensure_path(path)

    # Use the path itself if it's an existing directory; otherwise use its parent.
    base = p if safe_is_dir(p) else p.parent

    # Climb up until we find an existing directory.
    while not safe_exists(base):
        if base == base.parent:
            raise FileNotFoundError(f"No existing parent found for {path!r}")
        base = base.parent

    # POSIX: prefer statvfs to get user-available bytes (excludes reserved blocks).
    if hasattr(os, "statvfs"):
        st = os.statvfs(base)
        return st.f_bavail * st.f_frsize

    # Windows / others: fallback to shutil.disk_usage
    import shutil
    return shutil.disk_usage(str(base)).free

def filename_format(text: str, sep: str = "_", max_length: int | None = None) -> str:
    """
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
    """
    fallback_logging_config()  # Ensure logging is configured
    if not text:
        return ""
    # Normalize to ASCII
    try:
        import unidecode
        text = unidecode.unidecode(text)
    except ImportError:
        logging.warning("unidecode package not found, falling back to ASCII encoding.")
        # Fallback: encode to ASCII, ignore errors
        text = text.encode("ascii", "ignore").decode("ascii")

    # List of common extensions to recognize and (temporarily) remove
    removed_ext = ""
    for ext in ALL_KNOWN_EXTENSIONS:
        if text.casefold().endswith(ext):
            text = text[:-len(ext)]
            removed_ext = ext
            break

    # Replace common "word boundaries" with sep
    #    (dots, underscores, whitespace) but keep dashes
    #    e.g. "hello.world--foo_bar" → "hello world--foo bar"
    text = re.sub(r"[._\s]+", sep, text)

    # Remove anything but dashes, A-Z, a–z, 0–9, or our sep
    allowed = f"-A-Za-z0-9{re.escape(sep)}"
    text = re.sub(fr"[^{allowed}]+", "", text)

    # Collapse runs of sep (e.g. "__" → "_")
    text = re.sub(fr"{re.escape(sep)}{{2,}}", sep, text)

    # Strip leading/trailing seps
    text = text.strip(sep)

    # Optionally truncate (try not to cut in middle of a word)
    if max_length is not None and len(text) > max_length:
        # cut at max_length, then drop a partial trailing token if any
        truncated = text[:max_length]
        # if the next char in original isn't sep and our chop landed mid-token, trim back to last sep
        if (len(text) > max_length and not truncated.endswith(sep) and sep in truncated):
            truncated = truncated.rsplit(sep, 1)[0]
        text = truncated

    # If an extension was removed, append it back
    text += removed_ext

    return text

def verify_script(options: Options, thepath: str | os.PathLike[str], thescript: str) -> None:
    """
    Ensure that 'thepath' exists and contains exactly 'thescript'.
    - If 'thepath' does not exist or is not a file, it will be created and populated.
    - If it exists but its contents differ, it will be overwritten.
    - Otherwise, nothing happens.
    """
    # Check if it exists and is a file
    thepath = ensure_path(thepath)
    if not safe_is_file(thepath):
        if safe_is_dir(thepath):
            if not options.rawlog:
                logging.error(f"Expected a file at {os.fspath(thepath)}, but it is a directory.")
            return
        thepath.write_text(thescript, encoding=DEFAULT_ENCODING)
        if not options.rawlog:
            logging.info("Creating %s with the specified script.", os.fspath(thepath))
        return

    # It is a file: read and compare
    existing = thepath.read_text(encoding=DEFAULT_ENCODING)
    # Overwrite if different
    if existing != thescript:
        if not options.rawlog:
            logging.info("Contents of %s differ from the specified script in %s as follows:", os.fspath(thepath), __file__)
            my_diff(existing, thescript, thepath, diff_choice=1)
            logging.info("Overwriting %s with the specified script.", os.fspath(thepath))
        thepath.write_text(thescript, encoding=DEFAULT_ENCODING)

def calculate_checksum(file_path: str | os.PathLike[str]) -> str:
    """Calculate the SHA256 checksum of a file."""
    import hashlib
    file_path   = ensure_file(file_path)
    sha256_hash = hashlib.sha256()
    with file_path.open("rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
