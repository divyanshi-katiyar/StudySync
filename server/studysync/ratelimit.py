"""In-memory sliding-window rate limiter.

Good enough for one process. With several instances behind a load balancer the counters would move to Redis
(listed as optional in the Week 1 architecture); the interface here would stay the same.
"""
import math
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque:
        q = self._hits[key]
        while q and now - q[0] >= window:
            q.popleft()
        return q

    def hit(self, key: str, limit: int, window: float, now: float | None = None):
        """Count one request. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._prune(key, window, now)
            if len(q) >= limit:
                return False, max(1, math.ceil(window - (now - q[0])))
            q.append(now)
            if len(self._hits) > 20_000:
                self._sweep(window, now)
            return True, 0

    def blocked(self, key: str, limit: int, window: float, now: float | None = None):
        """Check without counting. Used for failed-login tracking."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._prune(key, window, now)
            if len(q) >= limit:
                return True, max(1, math.ceil(window - (now - q[0])))
            return False, 0

    def record(self, key: str, now: float | None = None):
        with self._lock:
            self._hits[key].append(time.monotonic() if now is None else now)

    def clear(self, key: str):
        with self._lock:
            self._hits.pop(key, None)

    def _sweep(self, window: float, now: float):
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] >= window]:
            del self._hits[key]
