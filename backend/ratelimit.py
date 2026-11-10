import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """Small in-process limiter. A reverse proxy/WAF should provide the global limit."""

    def __init__(self, limit: int, window_seconds: int, max_keys: int = 10_000):
        self.limit = limit
        self.window = window_seconds
        self.max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float] | None:
        bucket = self._events.get(key)
        if bucket is None:
            return None
        while bucket and now - bucket[0] >= self.window:
            bucket.popleft()
        if not bucket:
            self._events.pop(key, None)
            return None
        return bucket

    def retry_after(self, key: str) -> float | None:
        """Return seconds until another attempt is allowed, or None."""
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, now)
            if bucket is not None and len(bucket) >= self.limit:
                return max(0.0, self.window - (now - bucket[0]))
            return None

    def hit(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._events) >= self.max_keys:
                for existing in list(self._events):
                    self._prune(existing, now)
                if len(self._events) >= self.max_keys:
                    self._events.clear()
            self._events.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


login_ip_limiter = SlidingWindowLimiter(limit=30, window_seconds=5 * 60)
login_email_limiter = SlidingWindowLimiter(limit=10, window_seconds=5 * 60)

# First-login invitations (mailed after user creation by admins):
invite_ip_limiter = SlidingWindowLimiter(limit=30, window_seconds=5 * 60)
invite_token_limiter = SlidingWindowLimiter(limit=10, window_seconds=60 * 60)

# Company signup flow:
# - submitting the form: few per IP per hour (mail flooding protection)
# - resend: small per e-mail quota on top of the IP limiter
# - verification: attempts are cheap but limited per IP and per token
signup_ip_limiter = SlidingWindowLimiter(limit=5, window_seconds=60 * 60)
signup_resend_ip_limiter = SlidingWindowLimiter(limit=10, window_seconds=60 * 60)
signup_resend_limiter = SlidingWindowLimiter(limit=3, window_seconds=60 * 60)
verify_ip_limiter = SlidingWindowLimiter(limit=30, window_seconds=5 * 60)
verify_token_limiter = SlidingWindowLimiter(limit=10, window_seconds=60 * 60)
