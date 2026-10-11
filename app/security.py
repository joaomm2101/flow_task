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

    MAX_USERNAME_CHARS = 128  # longer names are truncated so keys stay small

    def __init__(
        self, max_per_user=5, max_per_ip=20, window_seconds=15 * 60, max_keys=10_000, clock=time.monotonic
    ):
        self.max_per_user = max_per_user
        self.max_per_ip = max_per_ip
        self.window = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._last_sweep = clock()
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

    def _user_key(self, ip: str, username: str) -> tuple:
        return (ip, username.lower()[: self.MAX_USERNAME_CHARS])

    def _sweep(self) -> None:
        """Drop expired entries for every key, then bound the number of keys.

        Without this, an attacker sending unique usernames would grow the
        dict forever, because a key is otherwise only pruned when it is
        looked up again.
        """
        now = self._clock()
        cutoff = now - self.window
        for key in [k for k, events in self._failures.items() if not events or events[-1] <= cutoff]:
            del self._failures[key]
        if len(self._failures) > self.max_keys:
            # still over the cap: forget the keys whose latest failure is oldest
            by_age = sorted(self._failures, key=lambda k: self._failures[k][-1])
            for key in by_age[: len(self._failures) - self.max_keys]:
                del self._failures[key]
        self._last_sweep = now

    def retry_after(self, ip: str, username: str) -> int:
        """Seconds until a blocked caller may try again; 0 when not blocked."""
        with self._lock:
            waits = []
            for key, limit in ((self._user_key(ip, username), self.max_per_user), ((ip,), self.max_per_ip)):
                events = self._prune(key)
                if len(events) >= limit:
                    waits.append(math.ceil(events[0] + self.window - self._clock()))
            return max(waits, default=0)

    def record_failure(self, ip: str, username: str) -> None:
        with self._lock:
            now = self._clock()
            if len(self._failures) >= self.max_keys or now - self._last_sweep >= self.window / 4:
                self._sweep()
            self._failures[self._user_key(ip, username)].append(now)
            self._failures[(ip,)].append(now)

    def reset(self, ip: str, username: str) -> None:
        with self._lock:
            self._failures.pop(self._user_key(ip, username), None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter()
