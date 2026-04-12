"""Protocol defining the uniform adapter interface.

All adapters must implement this protocol. The standard flow is:
    get_parser() → parse args → run(**kwargs)

The protocol is runtime-checkable so dispatch.py can validate
adapters at import time.

Dependency: none (leaf module, stdlib only).
"""
from __future__ import annotations

import argparse
from typing import Any, runtime_checkable

from typing import Protocol


@runtime_checkable
class AdapterProtocol(Protocol):
    """Interface that every adapter must implement.

    Methods:
        get_parser: Return an ArgumentParser for this adapter's CLI flags.
        run: Execute the adapter's main logic with parsed arguments.
    """

    def get_parser(self) -> argparse.ArgumentParser:
        """Return an ArgumentParser for this adapter's CLI arguments."""
        ...

    def run(self, **kwargs: Any) -> None:
        """Execute the adapter's main logic.

        Standard flow: parse_args → build_request → call_api →
        parse_response → track_cost → emit_output.

        Args:
            **kwargs: Parsed arguments from get_parser().
        """
        ...
