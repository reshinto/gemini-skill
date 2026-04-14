"""Console entry point for clone-free gemini-skill installation."""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

try:
    from importlib.resources.abc import Traversable
except ModuleNotFoundError:
    from importlib.abc import Traversable

from core.cli import install_main
from core.cli.installer.payload import iter_install_payload_paths

_PACKAGE_NAME = "gemini_skill_install"
_PAYLOAD_DIRNAME = "payload"


def _copy_traversable_tree(source_root: Traversable, destination_root: Path) -> None:
    """Recursively copy an ``importlib.resources`` tree to disk."""
    destination_root.mkdir(parents=True, exist_ok=True)
    for child in source_root.iterdir():
        destination_path = destination_root / child.name
        if child.is_dir():
            _copy_traversable_tree(child, destination_path)
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(child.read_bytes())


def _copy_source_checkout_payload(destination_root: Path) -> None:
    """Copy payload files directly from the source checkout during local development."""
    source_root = Path(__file__).resolve().parent.parent
    destination_root.mkdir(parents=True, exist_ok=True)
    for relative_path in iter_install_payload_paths():
        source_path = source_root / relative_path
        destination_path = destination_root / relative_path
        if source_path.is_dir():
            if destination_path.exists():
                shutil.rmtree(destination_path)
            shutil.copytree(
                source_path,
                destination_path,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def materialize_payload(destination_root: Path) -> Path:
    """Materialize the install payload into ``destination_root`` and return it."""
    packaged_payload = resources.files(_PACKAGE_NAME).joinpath(_PAYLOAD_DIRNAME)
    if packaged_payload.is_dir():
        _copy_traversable_tree(packaged_payload, destination_root)
        return destination_root

    _copy_source_checkout_payload(destination_root)
    return destination_root


def main(argv: Sequence[str] | None = None, *, install_dir: Path | None = None) -> None:
    """Run the bootstrap installer with the same CLI flags as ``setup/install.py``."""
    arguments = list(argv) if argv is not None else sys.argv[1:]
    with tempfile.TemporaryDirectory(prefix="gemini-skill-payload-") as temp_dir:
        payload_root = materialize_payload(Path(temp_dir))
        install_main.main(arguments, source_dir=payload_root, install_dir=install_dir)


def console_main() -> None:
    """Entrypoint used by packaging metadata."""
    main()
