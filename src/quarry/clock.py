"""Wall-clock budget: overall deadline, reserve for wrap-up, and per-phase slices."""

from __future__ import annotations

import os
import time
from typing import Callable, Optional

DEFAULT_TIMEOUT_SEC = 1500.0
MIN_RESERVE_SEC = 60.0
RESERVE_SHARE = 0.05


def read_timeout_env(environ: Optional[dict] = None) -> float:
    """Return AGENT_TIMEOUT in seconds, or the default when it is missing or invalid."""
    env = os.environ if environ is None else environ
    raw = str(env.get("AGENT_TIMEOUT", "")).strip()
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SEC
    return value if value > 0 else DEFAULT_TIMEOUT_SEC


class Clock:
    """Tracks the run deadline. `now` is injectable so tests control time."""

    def __init__(self, total_sec: float, now: Callable[[], float] = time.monotonic):
        self._now = now
        self.start = now()
        self.total = float(total_sec)
        self.reserve = max(MIN_RESERVE_SEC, RESERVE_SHARE * self.total)
        self.deadline = self.start + self.total - self.reserve

    @classmethod
    def from_env(cls, environ: Optional[dict] = None, now: Callable[[], float] = time.monotonic) -> Clock:
        return cls(read_timeout_env(environ), now)

    def now(self) -> float:
        return self._now()

    def elapsed(self) -> float:
        return self._now() - self.start

    def remaining(self) -> float:
        """Seconds left before wrap-up must start (never negative)."""
        return max(0.0, self.deadline - self._now())

    def expired(self) -> bool:
        return self.remaining() <= 0.0

    def slice(self, share: float, reserve_sec: float = 0.0) -> PhaseTimer:
        """A timer for one phase, optionally preserving working time for a later phase."""
        budget = min(share * self.total, max(0.0, self.remaining() - reserve_sec))
        return PhaseTimer(self, self._now() + budget)

    def command_timeout(self, cap: float = 300.0) -> float:
        """Timeout for one command: min(cap, 25% of what is left), at least 5 s."""
        return max(5.0, min(cap, 0.25 * self.remaining()))


class PhaseTimer:
    def __init__(self, clock: Clock, end: float):
        self.clock = clock
        self.end = min(end, clock.deadline)

    def remaining(self) -> float:
        return max(0.0, self.end - self.clock.now())

    def expired(self) -> bool:
        return self.remaining() <= 0.0
