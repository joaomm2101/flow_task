"""Shared security rules."""

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # bcrypt ignores everything past 72 bytes


def validate_password_strength(password: str) -> str:
    """Pydantic validator: length, one letter and one digit; raises ValueError otherwise."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f'Password must have at least {MIN_PASSWORD_LENGTH} characters.')
    if len(password.encode('utf-8')) > MAX_PASSWORD_BYTES:
        raise ValueError(f'Password must have at most {MAX_PASSWORD_BYTES} bytes.')
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError('Password must contain at least one letter and one digit.')
    return password


import math
import time
from collections import defaultdict, deque
from threading import Lock


class LoginRateLimiter:
    """In-memory sliding-window limiter for failed logins.

    Counts failures per (ip, username) and per ip. State lives in this process
    only: with several workers each one counts separately and a restart resets
    it. Swap the storage for Redis if the app is scaled out.
    """

    def __init__(self, max_per_user=5, max_per_ip=20, window_seconds=15 * 60, clock=time.monotonic):
        self.max_per_user = max_per_user
        self.max_per_ip = max_per_ip
        self.window = window_seconds
        self._clock = clock
        self._lock = Lock()
        self._failures: dict[tuple, deque] = defaultdict(deque)

    def _prune(self, key):
        events = self._failures[key]
        cutoff = self._clock() - self.window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._failures[key]
            return deque()
        return events

    def retry_after(self, ip: str, username: str) -> int:
        """Seconds until a blocked caller may try again; 0 when not blocked."""
        with self._lock:
            waits = []
            for key, limit in (((ip, username.lower()), self.max_per_user), ((ip,), self.max_per_ip)):
                events = self._prune(key)
                if len(events) >= limit:
                    waits.append(math.ceil(events[0] + self.window - self._clock()))
            return max(waits, default=0)

    def record_failure(self, ip: str, username: str) -> None:
        with self._lock:
            now = self._clock()
            self._failures[(ip, username.lower())].append(now)
            self._failures[(ip,)].append(now)

    def reset(self, ip: str, username: str) -> None:
        with self._lock:
            self._failures.pop((ip, username.lower()), None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter()
