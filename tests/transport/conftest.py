"""Shared pytest fixtures for the transport test package.

The dual-backend transport layer carries two pieces of process-wide state:

1. ``core.transport._COORDINATOR`` — the lazy singleton TransportCoordinator
   built by ``core.transport.get_coordinator``. Tests that build their own
   coordinator (or that reach into the facade) must run against a fresh
   slot so cross-test pollution can't hide bugs.
2. ``core.transport.sdk.client_factory.get_client`` — an ``lru_cache``-backed
   singleton that holds the constructed ``google.genai.Client``. A test
   that monkey-patches ``sys.modules["google.genai"]`` to a Mock will leave
   the cached client pointing at the Mock if the next test forgets to
   clear it.

This conftest installs ONE autouse fixture that resets both between every
test in this directory tree. Individual test files can still install their
own fixtures (e.g. ``test_facade.py``'s local reset hook); the autouse here
runs in addition and is idempotent — calling ``reset_coordinator()`` /
``cache_clear()`` on an already-empty cache is a no-op.

Why is this not a one-liner inside each test file? Two reasons:

1. **Forgetting it is a silent bug.** A new test that adds a Mock client
   and forgets to reset will leak the Mock into the next test in
   alphabetical order, which will then fail in a way that's hard to
   trace back to the missing reset.
2. **The autouse fixture is invisible to the test author.** It runs
   automatically for every test under ``tests/transport/`` and never
   needs to be requested explicitly.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _reset_transport_singletons() -> Iterator[None]:
    """Drop the facade coordinator + SDK client cache between every test."""
    # Lazy imports inside the fixture so an import failure of one of these
    # modules doesn't mask the underlying test failure with a fixture error.
    import core.transport as facade
    from core.transport.sdk import client_factory

    facade.reset_coordinator()
    client_factory.get_client.cache_clear()
    yield
    facade.reset_coordinator()
    client_factory.get_client.cache_clear()
