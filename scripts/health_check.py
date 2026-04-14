#!/usr/bin/env python
"""Health check for the gemini-skill.

2.7-safe launcher.
"""
import os
import sys


def _check_python_version() -> None:
    """Exit with a clear message if the host Python is too old."""
    if sys.version_info < (3, 9):
        sys.exit(
            "gemini-skill requires Python 3.9+. Found: {}.{}".format(
                sys.version_info[0], sys.version_info[1]
            )
        )


def _repo_root() -> str:
    """Return the absolute repository root containing ``core/``."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_repo_root_on_syspath() -> str:
    """Prepend the repository root to ``sys.path`` exactly once."""
    repo_root_path: str = _repo_root()
    if repo_root_path not in sys.path:
        sys.path.insert(0, repo_root_path)
    return repo_root_path


def _bootstrap_runtime_environment() -> None:
    """Normalize canonical env keys into ``os.environ`` before health checks."""
    _ensure_repo_root_on_syspath()

    from core.infra.errors import EnvironmentResolutionError
    from core.infra.runtime_env import bootstrap_runtime_env

    try:
        bootstrap_runtime_env()
    except EnvironmentResolutionError as environment_error:
        sys.exit(str(environment_error))


def main(argv: list[str]) -> None:
    """End-to-end launcher entry point for the health command."""
    _check_python_version()
    _bootstrap_runtime_environment()
    _ensure_repo_root_on_syspath()

    from core.cli.health_main import main as health_main  # noqa: E402

    health_main(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
