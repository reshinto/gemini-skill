"""Tests for core/adapter/contract.py — adapter protocol definition.

Verifies that the AdapterProtocol defines the expected interface
and that conforming/non-conforming classes are detected correctly.
"""
from __future__ import annotations

import argparse

import pytest


class TestAdapterProtocol:
    """AdapterProtocol must define get_parser() and run() methods."""

    def test_protocol_has_get_parser(self):
        from core.adapter.contract import AdapterProtocol
        assert hasattr(AdapterProtocol, "get_parser")

    def test_protocol_has_run(self):
        from core.adapter.contract import AdapterProtocol
        assert hasattr(AdapterProtocol, "run")

    def test_conforming_class_is_accepted(self):
        from core.adapter.contract import AdapterProtocol

        class GoodAdapter:
            def get_parser(self) -> argparse.ArgumentParser:
                return argparse.ArgumentParser()

            def run(self, **kwargs) -> None:
                pass

        # Should be recognized as implementing the protocol
        adapter: AdapterProtocol = GoodAdapter()
        assert hasattr(adapter, "get_parser")
        assert hasattr(adapter, "run")

    def test_protocol_is_runtime_checkable(self):
        from core.adapter.contract import AdapterProtocol

        class GoodAdapter:
            def get_parser(self) -> argparse.ArgumentParser:
                return argparse.ArgumentParser()

            def run(self, **kwargs) -> None:
                pass

        assert isinstance(GoodAdapter(), AdapterProtocol)

    def test_non_conforming_class_fails_check(self):
        from core.adapter.contract import AdapterProtocol

        class BadAdapter:
            pass

        assert not isinstance(BadAdapter(), AdapterProtocol)

    def test_partial_conformance_fails(self):
        from core.adapter.contract import AdapterProtocol

        class PartialAdapter:
            def get_parser(self) -> argparse.ArgumentParser:
                return argparse.ArgumentParser()
            # Missing run()

        assert not isinstance(PartialAdapter(), AdapterProtocol)
