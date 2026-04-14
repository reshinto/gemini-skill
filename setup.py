"""Packaging metadata for the clone-free bootstrap installer."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py as _build_py

_REPO_ROOT = Path(__file__).parent.resolve()
_PAYLOAD_PACKAGE_DIR = "gemini_skill_install/payload"


def _read_text(relative_path: str) -> str:
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8").strip()


def _iter_install_payload_paths() -> tuple[str, ...]:
    """Load the shared payload manifest without importing project packages."""
    payload_module_path = _REPO_ROOT / "core" / "cli" / "installer" / "payload.py"
    module_spec = importlib.util.spec_from_file_location(
        "gemini_skill_install_payload_manifest", payload_module_path
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Could not load payload manifest from {payload_module_path}")
    payload_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(payload_module)
    manifest = getattr(payload_module, "iter_install_payload_paths", None)
    if manifest is None:
        raise RuntimeError("Payload manifest module does not export iter_install_payload_paths")
    return tuple(manifest())


class build_py(_build_py):
    """Build wheel contents and inject the install payload into package data."""

    def run(self) -> None:
        super().run()
        self._copy_payload_into_build_lib()

    def _copy_payload_into_build_lib(self) -> None:
        payload_root = Path(self.build_lib) / _PAYLOAD_PACKAGE_DIR
        if payload_root.exists():
            shutil.rmtree(payload_root)
        payload_root.mkdir(parents=True, exist_ok=True)

        for relative_path in _iter_install_payload_paths():
            source_path = _REPO_ROOT / relative_path
            destination_path = payload_root / relative_path
            if source_path.is_dir():
                shutil.copytree(
                    source_path,
                    destination_path,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
                continue
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)


setup(
    name="gemini-skill-install",
    version=_read_text("VERSION"),
    description="Bootstrap installer for the gemini Claude Code skill",
    long_description=(_REPO_ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/reshinto/gemini-skill",
    license="MIT",
    python_requires=">=3.9",
    packages=find_packages(
        include=[
            "core",
            "core.*",
            "gemini_skill_install",
            "gemini_skill_install.*",
        ]
    ),
    include_package_data=False,
    install_requires=["typing-extensions>=4.0; python_version<'3.10'"],
    entry_points={
        "console_scripts": ["gemini-skill-install=gemini_skill_install.cli:console_main"]
    },
    cmdclass={"build_py": build_py},
)
