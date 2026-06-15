from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

# Win32 process-creation constants. Resolved via getattr with documented numeric
# fallbacks so this module imports cleanly on non-Windows platforms where the
# subprocess attributes are absent.
#
# Hiding a console child of a GUI parent is documented by Microsoft (and used by
# CPython's own stdlib) as two complementary mechanisms applied together:
#   * CREATE_NO_WINDOW in dwCreationFlags, so a console child gets no console
#     window of its own, and
#   * a STARTUPINFO with STARTF_USESHOWWINDOW and wShowWindow = SW_HIDE, which
#     hides the window of any intermediate shell that does create one.
# Applying both is belt-and-suspenders: it suppresses the brief black console
# flashes a GUI host (e.g. a PySide6 admin app) would otherwise see when this
# library spawns short-lived powershell.exe / dism.exe helpers.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_STARTF_USESHOWWINDOW = getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
_SW_HIDE = getattr(subprocess, "SW_HIDE", 0)


def _is_windows() -> bool:
    return os.name == "nt" and sys.platform == "win32"


def hidden_console_kwargs() -> dict[str, Any]:
    """Return subprocess keyword arguments that hide a console child's window.

    On Windows this returns ``creationflags`` carrying ``CREATE_NO_WINDOW`` and a
    ``STARTUPINFO`` configured for ``SW_HIDE``. On any other platform it returns a
    no-op pair (``{"creationflags": 0, "startupinfo": None}``) so Linux/macOS and
    CI behavior is unchanged. The keys are intended to be merged into an existing
    ``subprocess.run`` / ``subprocess.Popen`` call without altering its command,
    timeouts, capture, or parsing — only the child window is hidden.
    """
    if not _is_windows():
        return {"creationflags": 0, "startupinfo": None}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= _STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = _SW_HIDE
    return {"creationflags": _CREATE_NO_WINDOW, "startupinfo": startupinfo}


def with_hidden_console(**kwargs: Any) -> dict[str, Any]:
    """Merge :func:`hidden_console_kwargs` into ``kwargs`` without clobbering.

    Existing values win: ``creationflags`` is OR-combined with the hide flag, and
    a caller-supplied ``startupinfo`` is preserved as-is. This keeps every
    existing call's ``capture_output`` / ``text`` / ``encoding`` / ``errors`` /
    ``timeout`` / ``check`` arguments exactly as passed.
    """
    hide = hidden_console_kwargs()

    creationflags = int(kwargs.pop("creationflags", 0)) | int(hide["creationflags"])

    startupinfo = kwargs.pop("startupinfo", None)
    if startupinfo is None:
        startupinfo = hide["startupinfo"]

    merged = dict(kwargs)
    merged["creationflags"] = creationflags
    if startupinfo is not None:
        merged["startupinfo"] = startupinfo
    return merged
