"""Fallback eligibility decision table for the dual-backend coordinator.

The coordinator wraps every backend call. When the primary backend raises an
exception, the coordinator must decide one of two things:

1. **Eligible** — try the fallback backend. The exception looks like a
   transport-class issue (network glitch, server 5xx, missing SDK surface)
   that has a real chance of succeeding on the other backend.
2. **Not eligible** — re-raise immediately. The exception will fail the same
   way on the fallback (bad API key, malformed request, programmer bug),
   so retrying just hides the real problem behind a slower failure.

This file is the pure decision table that captures rule #1 vs rule #2. It is
intentionally side-effect-free so the entire policy can be unit-tested with
a parametrize matrix and zero fixtures — see ``tests/transport/test_policy.py``.

What you'll learn from this file:
- A "policy module" pattern: a single pure function that takes a value and
  returns a decision. Decisions are easy to test, easy to reason about, and
  easy to evolve safely because there's nowhere for hidden state to lurk.
- ``isinstance`` ordering matters. We check the most specific classes first
  (``CostLimitError`` before ``ValueError``-style fallbacks) so subclasses
  are routed by their own rule, not the parent's.

Why type-based dispatch instead of error-message string matching: string
matching against SDK error messages is fragile (the SDK changes wording
between versions) and dangerous (an unrelated error mentioning a common
substring would be silently swallowed). The policy here only ever asks
``isinstance(exc, X)`` so behavior is locked to the exception class
hierarchy, not to whatever the upstream library happens to print today.
"""
from __future__ import annotations

import socket
from urllib.error import URLError

from core.infra.errors import (
    APIError,
    AuthError,
    CapabilityUnavailableError,
    CostLimitError,
    ModelNotFoundError,
)
from core.transport.base import BackendUnavailableError

# Exceptions that always block fallback. The coordinator must re-raise these
# the moment the primary backend produces them. Order matters here only for
# readability — ``isinstance`` against a tuple checks every member regardless
# of position.
_NEVER_FALLBACK: tuple[type[BaseException], ...] = (
    AuthError,
    ModelNotFoundError,
    CostLimitError,
    AssertionError,
    ValueError,
    TypeError,
)

# Exceptions that always allow fallback. These represent "this backend is
# unable to even attempt the work" (missing SDK, missing capability) or
# "the network failed before the request could complete".
_ALWAYS_FALLBACK: tuple[type[BaseException], ...] = (
    BackendUnavailableError,
    CapabilityUnavailableError,
    ImportError,  # also catches ModuleNotFoundError, which is a subclass
    URLError,
    socket.timeout,
    ConnectionError,
)


def is_fallback_eligible(exc: BaseException) -> bool:
    """Decide whether an exception from the primary backend permits fallback.

    The function is intentionally exhaustive — every supported exception
    class has a corresponding row in ``tests/transport/test_policy.py``. If
    you add a new error type to the skill, add it to one of the lists above
    AND add a parametrized test row.

    Args:
        exc: The exception raised by the primary backend during a call.
            Accepts ``BaseException`` (not just ``Exception``) so that the
            policy can reason about ``KeyboardInterrupt`` and friends if
            they ever bubble through the coordinator — though by default
            those are NOT eligible because they're user signals, not
            transport failures.

    Returns:
        True if the coordinator should try the fallback backend.
        False if the coordinator should re-raise immediately.

    Example:
        >>> from core.transport.policy import is_fallback_eligible
        >>> from core.infra.errors import APIError, AuthError
        >>> is_fallback_eligible(AuthError("bad key"))
        False
        >>> is_fallback_eligible(APIError("rate limit", status_code=429))
        True
    """
    # Rule 1: hard "no" list short-circuits. Auth, programmer bugs, and
    # cost-limit failures will fail identically on either backend, so the
    # coordinator must surface them immediately rather than burn time on a
    # second attempt.
    if isinstance(exc, _NEVER_FALLBACK):
        return False

    # Rule 2: APIError eligibility is decided by HTTP status. 4xx (except
    # 429) means the request itself was wrong — the fallback will reject it
    # the same way. 429 (rate limit) and 5xx (server) are transient and
    # worth a retry on the other backend. APIError without a status code
    # means a parse failure or a transport-class issue surfaced through the
    # APIError type, which is also fallback-eligible.
    if isinstance(exc, APIError):
        if exc.status_code is None:
            return True
        if 400 <= exc.status_code < 500 and exc.status_code != 429:
            return False
        return True

    # Rule 3: hard "yes" list — backend availability failures and network
    # glitches that are independent of the request payload.
    if isinstance(exc, _ALWAYS_FALLBACK):
        return True

    # Rule 4: anything we haven't classified defaults to NOT eligible.
    # Failing closed is the safe default: an unknown exception is more
    # likely to be a programmer bug than a transient transport issue, and
    # bubbling it up immediately surfaces the gap instead of masking it
    # behind a slow second attempt.
    return False
