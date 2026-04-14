#!/usr/bin/env python
"""Install the gemini-skill to ~/.claude/skills/gemini/.

2.7-safe launcher. Uses only Python 2.7-compatible syntax so even
old Pythons get a readable error instead of a SyntaxError.
"""
import os
import platform
import subprocess
import sys

_MIN_PYTHON = (3, 9)
_MIN_STABLE_MINOR = 9
_MAX_SEARCH_MINOR = 15
_REEXEC_ENV = "GEMINI_SKILL_INSTALL_REEXEC"
_PROBE_CODE = (
    "import platform, sys; "
    "print('%s|%s|%s|%s|%s|%s|%s' % ("
    "sys.version_info[0], "
    "sys.version_info[1], "
    "sys.version_info[2], "
    "getattr(sys.version_info, 'releaselevel', '') or "
    "(sys.version_info[3] if len(sys.version_info) > 3 else ''), "
    "getattr(sys, 'abiflags', '') or '', "
    "int('free-thread' in sys.version.lower()), "
    "platform.python_implementation()"
    "))"
)


def _current_python_info():
    """Return compatibility metadata for the current interpreter."""
    return {
        "major": sys.version_info[0],
        "minor": sys.version_info[1],
        "micro": sys.version_info[2],
        "releaselevel": getattr(sys.version_info, "releaselevel", "")
        or (sys.version_info[3] if len(sys.version_info) > 3 else "final"),
        "abiflags": getattr(sys, "abiflags", "") or "",
        "free_threaded": int("free-thread" in sys.version.lower()),
        "implementation": platform.python_implementation(),
    }


def _is_compatible_python(info):
    """Return True when install can safely build the SDK venv."""
    return (
        (info["major"], info["minor"]) >= _MIN_PYTHON
        and info["releaselevel"] == "final"
        and "t" not in info["abiflags"]
        and not info["free_threaded"]
        and info["implementation"] == "CPython"
    )


def _probe_python(command):
    """Return compatibility metadata for ``command`` or None if unavailable."""
    try:
        process = subprocess.Popen(
            [command, "-c", _PROBE_CODE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _stderr = process.communicate()
    except OSError:
        return None

    if process.returncode != 0:
        return None

    if not isinstance(stdout, str):
        stdout = stdout.decode("utf-8", "replace")
    parts = stdout.strip().split("|")
    if len(parts) != 7:
        return None

    try:
        return {
            "major": int(parts[0]),
            "minor": int(parts[1]),
            "micro": int(parts[2]),
            "releaselevel": parts[3],
            "abiflags": parts[4],
            "free_threaded": int(parts[5]),
            "implementation": parts[6],
        }
    except ValueError:
        return None


def _candidate_python_commands():
    """Return versioned python3 candidates from newest to oldest."""
    highest_minor = max(_MAX_SEARCH_MINOR, sys.version_info[1])
    commands = []
    minor = highest_minor
    while minor >= _MIN_STABLE_MINOR:
        commands.append("python3.%s" % minor)
        minor -= 1
    commands.append("python3")
    return commands


def _describe_python(info):
    """Format interpreter metadata for user-facing messages."""
    details = [
        "Python %s.%s.%s" % (info["major"], info["minor"], info["micro"]),
        info["implementation"],
        info["releaselevel"],
    ]
    if info["abiflags"]:
        details.append("abiflags=%s" % info["abiflags"])
    if info["free_threaded"]:
        details.append("free-threaded")
    return ", ".join(details)


def _incompatibility_reasons(info):
    """Return the install-blocking reasons for this interpreter."""
    reasons = []
    if (info["major"], info["minor"]) < _MIN_PYTHON:
        reasons.append("Python 3.9+ is required")
    if info["implementation"] != "CPython":
        reasons.append("CPython is required for the SDK venv")
    if info["releaselevel"] != "final":
        reasons.append("pre-release builds are not supported")
    if "t" in info["abiflags"] or info["free_threaded"]:
        reasons.append("free-threaded builds are not supported")
    return reasons


def _find_compatible_python():
    """Return the first compatible python command on PATH, if any."""
    for command in _candidate_python_commands():
        info = _probe_python(command)
        if info is None:
            continue
        if _is_compatible_python(info):
            return command, info
    return None, None


def _ensure_install_python():
    """Re-exec the installer under a stable compatible interpreter if needed."""
    current = _current_python_info()
    if (current["major"], current["minor"]) < _MIN_PYTHON:
        sys.exit(
            "gemini-skill requires Python 3.9+. Found: {}.{}".format(
                current["major"], current["minor"]
            )
        )

    if _is_compatible_python(current):
        return

    command, info = _find_compatible_python()
    if command is None:
        reasons = "; ".join(_incompatibility_reasons(current))
        searched = ", ".join(_candidate_python_commands())
        sys.exit(
            "gemini-skill install needs a stable CPython 3.9+ interpreter for the "
            "SDK venv.\n"
            "Current interpreter: {current}\n"
            "Rejected because: {reasons}\n"
            "Checked on PATH: {searched}\n"
            "Install a compatible Python and rerun, for example: python3.13 "
            "setup/install.py".format(
                current=_describe_python(current), reasons=reasons, searched=searched
            )
        )

    if os.environ.get(_REEXEC_ENV) == command:
        sys.exit(
            "gemini-skill install re-executed with {command} but it still was not "
            "usable for SDK installation.".format(command=command)
        )

    sys.stderr.write(
        "Re-running installer with compatible Python: {command} "
        "({details})\n".format(command=command, details=_describe_python(info))
    )
    env = os.environ.copy()
    env[_REEXEC_ENV] = command
    os.execvpe(command, [command, os.path.abspath(__file__)] + sys.argv[1:], env)


_ensure_install_python()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cli.install_main import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
