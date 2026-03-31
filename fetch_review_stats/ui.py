"""ANSI colors, Unicode icons, and formatting helpers for CLI output."""

from __future__ import annotations

import os
import sys
import threading
import time

# ── Color support detection ──────────────────────────────────────────

_COLOR = (
    not os.environ.get("NO_COLOR")
    and os.environ.get("FORCE_COLOR", "") != "0"
    and sys.stdout.isatty()
)

# ── ANSI escape codes ────────────────────────────────────────────────

RESET = "\033[0m" if _COLOR else ""
BOLD = "\033[1m" if _COLOR else ""
DIM = "\033[2m" if _COLOR else ""
RED = "\033[31m" if _COLOR else ""
GREEN = "\033[32m" if _COLOR else ""
YELLOW = "\033[33m" if _COLOR else ""
PURPLE = "\033[35m" if _COLOR else ""

# ── Unicode icons ────────────────────────────────────────────────────

OK = "✓"
FAIL = "✗"
WARN = "⚠"
ARROW = "→"

# ── Formatting helpers (return strings, never call print) ────────────


def success(text: str) -> str:
    return f"  {GREEN}{OK}{RESET} {text}"


def error(text: str) -> str:
    return f"  {RED}{FAIL}{RESET} {text}"


def warn(text: str) -> str:
    return f"  {YELLOW}{WARN}{RESET} {text}"


def dim(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def bold(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


def purple(text: str) -> str:
    return f"{PURPLE}{text}{RESET}"


def green(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


def header(name: str) -> str:
    """Section separator: ── name ──────────"""
    pad = 40 - len(name) - 2
    line = "─" * max(pad, 4)
    return f"\n  {PURPLE}── {BOLD}{name} {RESET}{PURPLE}{line}{RESET}"


def status(label: str, value: str | int, suffix: str = "") -> str:
    """Aligned status line:   ✓ Label          value suffix"""
    val_str = f"{value:,}" if isinstance(value, int) else str(value)
    suffix_str = f" {suffix}" if suffix else ""
    return f"    {GREEN}{OK}{RESET} {label:<20s} {GREEN}{val_str}{RESET}{suffix_str}"


def status_error(label: str, msg: str) -> str:
    """Aligned error line:   ✗ Label          error message"""
    return f"    {RED}{FAIL}{RESET} {label:<20s} {RED}{msg}{RESET}"


def filepath(path: str) -> str:
    """File path with arrow:   → filename"""
    return f"    {PURPLE}{ARROW}{RESET} {PURPLE}{path}{RESET}"


def config_line(label: str, value: str) -> str:
    """Config key-value:  Label       value"""
    return f"  {DIM}{label:<11s}{RESET} {BOLD}{value}{RESET}"


def summary_line(label: str, value: str | int, color: str = "") -> str:
    """Summary box row:  │ Label          value"""
    val_str = f"{value:,}" if isinstance(value, int) else str(value)
    c = color or GREEN
    return f"  {PURPLE}│{RESET} {label:<20s} {c}{val_str}{RESET}"


# ── Spinner ──────────────────────────────────────────────────────────

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_ERASE_LINE = "\033[2K\r" if _COLOR else "\r"


class Spinner:
    """Inline spinner that runs in a background thread.

    Usage:
        with Spinner("Fetching PRs"):
            result = slow_fetch()
        print(status("PRs authored", len(result)))
    """

    def __init__(self, label: str) -> None:
        self._label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "Spinner":
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the spinner line so the caller can print the final status
        sys.stdout.write(f"{_ERASE_LINE}")
        sys.stdout.flush()

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
            sys.stdout.write(f"{_ERASE_LINE}    {PURPLE}{frame}{RESET} {DIM}{self._label}{RESET}")
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.08)
