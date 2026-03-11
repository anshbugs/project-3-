"""
Retry outbound network calls to cope with transient 'Network is unreachable'
(e.g. on Render/cloud containers during cold start or brief outages).
"""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Errors that usually mean "try again" (network/DNS/connection).
RETRY_EXCEPTIONS = (OSError, ConnectionError)

# Default: 4 attempts, delays 2s, 4s, 8s.
MAX_ATTEMPTS = 4
BASE_DELAY_SEC = 2.0


def with_network_retry(
    fn: Callable[[], T],
    max_attempts: int = MAX_ATTEMPTS,
    base_delay: float = BASE_DELAY_SEC,
) -> T:
    """Run fn(); on OSError/ConnectionError, retry with exponential backoff."""
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except RETRY_EXCEPTIONS as e:
            last_err = e
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Network error (attempt %s/%s): %s; retrying in %.1fs",
                attempt + 1,
                max_attempts,
                e,
                delay,
            )
            time.sleep(delay)
    if last_err:
        raise last_err
    raise RuntimeError("with_network_retry: unexpected exit")
