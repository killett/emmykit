"""media — extracted from univ_defs.py."""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from emmykit.constants import DEFAULT_ENCODING
from emmykit.extensions import VIDEO_EXTENSIONS_SET
from emmykit.logging_utils import fallback_logging_config
from emmykit.paths_ensure import ensure_path
from emmykit.safe_paths import (
    ensure_dir, ensure_file, safe_exists, safe_is_dir, safe_is_file, safe_mtime,
)
from emmykit.files import filename_format


def ensure_even_dimensions(image_path: str | os.PathLike[str]) -> None:
    """Ensure the image at 'image_path' has dimensions divisible by 2, by resizing if necessary."""
    from PIL import Image
    fallback_logging_config()
    image_path = ensure_file(image_path)
    with Image.open(image_path) as img:
        width, height = img.size
        new_width  = width  if width  % 2 == 0 else width  - 1
        new_height = height if height % 2 == 0 else height - 1

        if new_width != width or new_height != height:
            try:
                img = img.resize((new_width, new_height), Image.LANCZOS)
                img.save(image_path)
                logging.info("Resized image to even dimensions: width = %d, height = %d", new_width, new_height)
            except OSError as e:
                raise ValueError(f"Could not resize image {os.fspath(image_path)} to even dimensions: {e}") from e
        else:
            logging.info("Image already has even dimensions: width = %d, height = %d", width, height)

def find_ffmpeg() -> str | None:
    """
    Return a full path string to an ffmpeg executable if found, else None.
    Tries: env vars, PATH, common Conda and Windows/Cygwin/MSYS installs,
    and (optionally) imageio-ffmpeg if available.

    Args:
        None

    Returns:
        A string containing the path to the ffmpeg executable or None if not found.

    Raises:
        None
    """
    import shutil
    # 1) Explicit env vars (user can set one of these)
    for env_key in ("FFMPEG", "FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
        p = os.environ.get(env_key)
        if p:
            path_p = ensure_file(p)
            return os.fspath(path_p)

    # 2) On PATH (handles .exe on Windows automatically)
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            path_p = ensure_file(p)
            return os.fspath(path_p)

    # 3) Typical Conda/Miniconda/Mambaforge locations
    sp = Path(sys.prefix)  # current Python env prefix
    candidates = [
        sp / "bin"     / "ffmpeg",              # Unix-like
        sp / "Library" / "bin" / "ffmpeg.exe",  # Windows (Conda)
        sp / "Scripts" / "ffmpeg.exe",          # Windows (alt)
    ]

    # 4) Common Windows installs (adjust or extend as you like)
    candidates += [
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\cygwin64\bin\ffmpeg.exe"),
        Path(r"C:\msys64\usr\bin\ffmpeg.exe"),
    ]

    # 5) Optional: imageio-ffmpeg packaged binary if user has it
    try:
        import imageio_ffmpeg  # type: ignore
        p_str: str | None = imageio_ffmpeg.get_ffmpeg_exe()
        if p_str:
            p_path = ensure_path(p_str)
            if safe_is_file(p_path) and os.access(os.fspath(p_path), os.X_OK):
                return os.fspath(p_str)
            else:
                raise ValueError(f"imageio-ffmpeg returned non-executable path: {p_str}")
        else:
            raise ValueError(f"imageio-ffmpeg returned {p_str}")
    except Exception as e:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug(
            "Failed to find imageio-ffmpeg: %s", e
        )

    for c in candidates:
        if safe_exists(c):
            return os.fspath(c)

    return None

def set_system_volume(percent: int, tolerance: int = 1,
                      change_mute: Literal["mute", "unmute"] | None = None,
                      force_pactl: bool = False) -> None:
    """
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
    """
    import subprocess
    import logging
    fallback_logging_config()
    if not sys.platform.startswith("linux"):
        raise RuntimeError("This set_system_volume() function is only intended to run on Linux systems.")
    fraction = percent / 100.0
    mute_arg = None
    if change_mute is not None:
        if change_mute.casefold() == "mute":
            mute_arg = 1
        elif change_mute.casefold() == "unmute":
            mute_arg = 0
        else:
            raise ValueError("change_mute must be 'mute', 'unmute', or None")
    # First, try using pulsectl to set the volume.
    if not force_pactl:
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("force_pactl=%s.", force_pactl)
        try:
            from pulsectl import Pulse, PulseError
            if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pulsectl] Attempting to set the volume to %d%% using pulsectl...", percent)
            with Pulse("volume-setter") as pulse:
                default_name = pulse.server_info().default_sink_name
                sink = pulse.get_sink_by_name(default_name)
                pulse.sink_suspend(sink.index, False)  # <— wake it up if it's suspended
                pulse.volume_set_all_chans(sink, fraction)
                # Optionally set mute
                if mute_arg is not None:
                    pulse.sink_mute(sink.index, mute_arg)
                    sink_after = pulse.get_sink_by_name(default_name)
                    # Verify mute state
                    if   mute_arg == 1 and not sink_after.mute:
                        raise RuntimeError("[pulsectl] Volume is not muted even though the user requested it to be muted.")
                    elif mute_arg == 0 and     sink_after.mute:
                        raise RuntimeError("[pulsectl] Volume is still muted even though the user requested it to be unmuted.")
                else:
                    # Fetch volume again to verify
                    sink_after = pulse.get_sink_by_name(default_name)
                vols = sink_after.volume.values  # list of channel floats 0.0–1.0
                avg = sum(vols) / len(vols)
                actual = int(round(avg * 100))
                if abs(actual - percent) > tolerance:
                    raise RuntimeError(f"[pulsectl] Expected {percent}%, but got {actual}%")
                state = "muted" if sink_after.mute else "unmuted"
                if mute_arg is not None and sink_after.mute != mute_arg:
                    raise RuntimeError(f"Mute verify failed: got {state}")
                logging.info("[pulsectl] Volume set to %d%%, %s", actual, state)
                return  # Successfully set volume and verified
        except ImportError:
            logging.warning("[pulsectl] Not installed; falling back to pactl...")
        except PulseError as e:
            logging.error("[pulsectl] PulseError: %s; falling back to pactl...", e)
        except RuntimeError as e:
            logging.error("%s; falling back to pactl...", e)
        except Exception as e:
            logging.error("[pulsectl] Unexpected error: %s; falling back to pactl...", e)

    # Fallback to pactl if pulsectl is not available or fails
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pactl] Attempting to set the volume to %d%% using pactl...", percent)
    the_command = ["pactl", "suspend-sink", "@DEFAULT_SINK@", "0"]
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pactl] Running command: %s", " ".join(the_command))
    result = subprocess.run(the_command, check=True, capture_output=True, text=True)
    if result.stderr:
        raise RuntimeError(f"[pactl] Error waking up sink from suspension: {result.stderr.strip()}")
    the_command = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"]
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pactl] Running command: %s", " ".join(the_command))
    result = subprocess.run(the_command, check=True, capture_output=True, text=True)
    if result.stderr:
        raise RuntimeError(f"[pactl] Error setting volume: {result.stderr.strip()}")
    # Set mute if requested
    if mute_arg is not None:
        cmd = ["pactl", "set-sink-mute", "@DEFAULT_SINK@", str(mute_arg)]
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pactl] %s", " ".join(cmd))
        mute_result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if mute_result.stderr:
            raise RuntimeError(f"[pactl] Error setting mute: {mute_result.stderr.strip()}")
        # Verify mute state
        mute_check_cmd = ["pactl", "get-sink-mute", "@DEFAULT_SINK@"]
        if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pactl] Running command: %s", " ".join(mute_check_cmd))
        mute_result = subprocess.run(mute_check_cmd, check=True, capture_output=True, text=True)
        if mute_result.stderr:
            raise RuntimeError(f"[pactl] Error getting mute state: {mute_result.stderr.strip()}")
        mute_output = mute_result.stdout.strip()
        if   mute_arg == 1 and "yes" not in mute_output:
            raise RuntimeError("[pactl] Volume is not muted even though the user requested it to be muted.")
        elif mute_arg == 0 and "no"  not in mute_output:
            raise RuntimeError("[pactl] Volume is still muted even though the user requested it to be unmuted.")
        logging.info("[pactl] Audio %s", 'muted' if mute_arg else 'unmuted')
    # Verify volume setting with pactl
    the_command = ["pactl", "get-sink-volume", "@DEFAULT_SINK@"]
    if logging.getLogger().isEnabledFor(logging.DEBUG): logging.debug("[pactl] Running command: %s", " ".join(the_command))
    result = subprocess.run(the_command, check=True, capture_output=True, text=True)
    if result.stderr:
        raise RuntimeError(f"[pactl] Error getting volume: {result.stderr.strip()}")
    output = result.stdout.strip()
    # Example output: "Volume: front-left: 32768 / 100% / 32768 / 100%"
    parts = output.split("/")
    if len(parts) < 2:
        raise RuntimeError(f"[pactl] Unexpected pactl output: {output}")
    actual = int(parts[1].strip().replace("%", ""))
    if abs(actual - percent) > tolerance:
        raise RuntimeError(f"[pactl] Expected {percent}%, but got {actual}%")
    logging.info("[pactl] Volume set to %d%%", percent)

def open_playlist_in_VLC(playlist: str | os.PathLike[str], no_start: bool = False) -> None:
    """Open a playlist in VLC. If no_start is True, don't start playback in VLC."""
    import subprocess
    playlist = ensure_file(playlist)
    if no_start: command_list = ["vlc", "--no-playlist-autostart", os.fspath(playlist)]
    else:        command_list = ["vlc",                            os.fspath(playlist)]
    subprocess.Popen(command_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def open_dir_in_VLC(the_dir: str | os.PathLike[str], sort_choice: str = "sort_by_name",
                    recursive: bool = False, no_start:  bool = False) -> None:
    """Create a playlist of the files in the specified directory, then play that playlist in VLC. By default, don't search the directory recursively and sort the files by name. Optional arguments allow recursive loading or sorting by modification time. If no_start is True, don't start playback in VLC."""
    import subprocess
    if the_dir is None:
        raise ValueError("The directory path cannot be None.")
    the_dir = ensure_dir(the_dir)
    # start_flag: str | None = "--start-paused" if no_start else None  # Note: the "--start-paused" flag forces you to press play in VLC EACH TIME YOU GO TO A NEW PLAYLIST ENTRY!
    start_flag: str | None = "--no-playlist-autostart" if no_start else None
    # List to store files with their modification times
    files_with_times: list[tuple[float, Path]] = []
    dirs_with_times:  list[tuple[float, Path]] = []  # Only used if not recursive
    entries:                    Iterable[Path] = the_dir.rglob("*") if recursive else the_dir.iterdir()
    for p in entries:
        if p and safe_is_file(p):
            if p.suffix.casefold() not in VIDEO_EXTENSIONS_SET:
                continue  # Exclude files that are not video files
            if (file_mtime := safe_mtime(p)) is not None:
                files_with_times.append((file_mtime, p))
        elif not recursive and p and safe_is_dir(p):
            if (dir_mtime := safe_mtime(p)) is not None:
                dirs_with_times.append((dir_mtime, p))
    if sort_choice == "sort_by_name":
        # Sort files by name, case-insensitively
        files_with_times.sort(   key=lambda x: x[1].name.casefold())
        if len(dirs_with_times) > 0:
            dirs_with_times.sort(key=lambda x: x[1].name.casefold())
    elif sort_choice == "sort_by_time":
        # Sort files by modification time (earliest first)
        files_with_times.sort(   key=lambda x: x[0])
        if len(dirs_with_times) > 0:
            dirs_with_times.sort(key=lambda x: x[0])
    # If present, put directories at the top of the list
    files_with_times = dirs_with_times + files_with_times
    # Create the .m3u playlist content with as_posix() to ensure forward slashes even on Windows
    playlist_content = "#EXTM3U\n"
    for _, file_path in files_with_times:
        playlist_content += f"#EXTINF:-1,{file_path.name.replace(',', '').replace('-', '')}" \
                            f"\n{file_path.as_posix()}\n"
    # Write the playlist to disk in the directory
    playlist_path = the_dir / f"{filename_format(the_dir.name)}_playlist.m3u"
    playlist_path.write_text(playlist_content, encoding=DEFAULT_ENCODING)
    # Open the playlist in VLC
    if start_flag: command_list = ["vlc", start_flag, os.fspath(playlist_path)]
    else:          command_list = ["vlc",             os.fspath(playlist_path)]
    subprocess.Popen(command_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def open_in_vlc(path: str | os.PathLike[str], no_start: bool = False) -> None:
    """
    Open a file or directory in VLC. If it's a directory, create a playlist of its contents first. If no_start is True, don't start playback in VLC.

    Args:
        path:     The file or directory path to open in VLC.
        no_start: If True, VLC will open the file or playlist but not start playback automatically
                    (default: False).

    Returns:
        None: The function performs the action of opening VLC and does not return any value.

    Raises:
        FileNotFoundError: If the specified path does not exist.
    """
    path = ensure_path(path)
    if not safe_exists(path):
        raise FileNotFoundError(f"The specified path does not exist: {os.fspath(path)}")
    if safe_is_dir(path):
        open_dir_in_VLC(     path, no_start=no_start)
    else:  # Open every file as if it's a playlist.
        open_playlist_in_VLC(path, no_start=no_start)

def get_video_duration_seconds(path: str | os.PathLike[str],
                               timeout: float = 10.0) -> float:
    """
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
    """
    import json
    import shutil
    import subprocess

    p: Path = ensure_path(path)
    if not safe_is_file(p):
        raise FileNotFoundError(f"No such file: {os.fspath(p)}")

    data: dict[str, Any] = {}

    def _run(cmd: list[str]) -> tuple[int, str, str]:
        """Helper: run a subprocess safely"""
        proc = subprocess.run(cmd,
                              capture_output=True,
                              text=True,
                              timeout=timeout,
                              check=False)
        return proc.returncode, proc.stdout, proc.stderr

    # ------------------------------------
    # 1) Try ffprobe (fast & very reliable)
    # ------------------------------------
    if shutil.which("ffprobe"):
        # Ask for JSON to simplify parsing. format.duration is typically present and precise.
        # -v error: suppress logs; -hide_banner: quiet banner; -show_format: include container info.
        cmd_ffprobe: list[str] = ["ffprobe",
                                  "-v", "error",
                                  "-hide_banner",
                                  "-print_format", "json",
                                  "-show_format",
                                  os.fspath(p)]
        rc, out, err = _run(cmd_ffprobe)
        if rc == 0 and out.strip():
            try:
                data = json.loads(out)
                # Preferred: container-level duration
                dur_str: str | None = None
                if isinstance(data.get("format"), dict):
                    dur_val = data["format"].get("duration")
                    if isinstance(dur_val, (int, float)):
                        duration = float(dur_val)
                        if duration > 0:
                            return duration
                    elif isinstance(dur_val, str):  # sometimes it's a string
                        try:
                            duration = float(dur_val)
                            if duration > 0:
                                return duration
                        except ValueError:
                            pass

                # Fallback: check individual streams for a duration and take the max > 0
                max_stream_dur: float = 0.0
                streams = data.get("streams")
                if isinstance(streams, list):
                    for s in streams:
                        dur = s.get("duration")
                        if isinstance(dur, (int, float)) and dur > 0:
                            max_stream_dur = max(max_stream_dur, float(dur))
                        elif isinstance(dur, str):
                            try:
                                f = float(dur)
                                if f > 0:
                                    max_stream_dur = max(max_stream_dur, f)
                            except ValueError:
                                pass
                if max_stream_dur > 0:
                    return max_stream_dur
            except json.JSONDecodeError:
                pass  # Will try next method

    # -----------------------------------
    # 2) Try mediainfo (another solid CLI)
    # -----------------------------------
    if shutil.which("mediainfo"):
        # JSON output is consistent; "General" track has Duration in ms.
        cmd_mediainfo: list[str] = ["mediainfo", "--Output=JSON", os.fspath(p)]
        rc, out, err = _run(cmd_mediainfo)
        if rc == 0 and out.strip():
            try:
                data   = json.loads(out)
                media  = data.get("media", {})
                tracks = media.get("track", [])
                if isinstance(tracks, list):
                    # Prefer "General" duration (milliseconds). If absent, use max of track durations.
                    general_ms: float = 0.0
                    max_ms: float = 0.0
                    for t in tracks:
                        if not isinstance(t, dict):
                            continue
                        ttype = t.get("@type")
                        # Keys can be "Duration" (ms) or "Duration/String".
                        dur_ms_val = t.get("Duration")
                        if isinstance(dur_ms_val, (int, float)):
                            ms = float(dur_ms_val)
                        elif isinstance(dur_ms_val, str):
                            try:
                                ms = float(dur_ms_val)
                            except ValueError:
                                ms = 0.0
                        else:
                            ms = 0.0

                        if ttype == "General" and ms > 0:
                            general_ms = ms
                        max_ms = max(max_ms, ms)

                    chosen_ms: float = general_ms if general_ms > 0 else max_ms
                    if chosen_ms > 0:
                        return chosen_ms / 1000.0
            except json.JSONDecodeError:
                pass  # Try last-resort method

    # ---------------------------------------
    # 3) Last resort: OpenCV (if available)
    # ---------------------------------------
    # Note: Not as robust as ffprobe/mediainfo; good fallback when those CLIs aren't installed.
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(os.fspath(p))
        try:
            if not cap.isOpened():
                raise RuntimeError("OpenCV could not open the file.")
            frames: float = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            fps:    float = cap.get(cv2.CAP_PROP_FPS)         or 0.0
            if frames > 0 and fps > 0:
                return frames / fps
        finally:
            cap.release()
    except Exception:
        # ImportError or any cv2 failure — ignore and raise below.
        pass

    # If we reach here, we couldn't determine the duration.
    raise RuntimeError("Unable to determine video duration. "
                       "Install FFmpeg (`ffprobe`) or MediaInfo (`mediainfo`) for best results.")

def extract_and_concatenate_segments(input_file: str | os.PathLike[str],
                                     timestamps: list,
                                     output_name_or_path: str | os.PathLike[str],
                                     subtitle_file: str | os.PathLike[str]) -> None:
    """Extracts segments from a video file and concatenates them into a new file."""
    import subprocess
    input_file      = ensure_path(input_file)
    subtitle_file   = ensure_path(subtitle_file)
    input_dir       = input_file.parent
    if type(output_name_or_path) is str:
        output_path = input_dir / output_name_or_path
    else:
        output_path = ensure_path(output_name_or_path)
    ffmpeg_path_str = find_ffmpeg()
    if not ffmpeg_path_str:
        raise RuntimeError("ffmpeg is not installed or not found in PATH. Please install ffmpeg to use this function.")

    print(f"Extracting segments from:\n{input_file} and saving to:\n{os.fspath(output_path)} with subtitles from:\n{subtitle_file}")
    # Create filter complex command for extracting and concatenating segments
    filter_complex = ""
    inputs = ""
    for i, (start, end) in enumerate(timestamps):
        filter_complex += f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];"
        filter_complex += f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];"
        inputs += f"[v{i}][a{i}]"

    filter_complex += f"{inputs}concat=n={len(timestamps)}:v=1:a=1[outv][outa]"

    # Command to extract segments and concatenate them
    command = [
        ffmpeg_path_str,
        "-i", os.fspath(input_file),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-c:a", "aac",
        os.fspath(output_path)
    ]
    subprocess.run(command, check=True)
