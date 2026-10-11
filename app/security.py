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


import heapq
import math
import time
from collections import deque
from threading import Lock


class LoginRateLimiter:
    """In-memory sliding-window limiter for failed logins.

    Counts failures per (ip, username) and per ip. State lives in this process
    only: with several workers each one counts separately and a restart resets
    it. Swap the storage for Redis if the app is scaled out.

    Memory and CPU are bounded against attackers who flood it with unique
    keys: an ip stops recording once it is blocked (so one ip can create at
    most ``max_per_ip`` user keys), expired keys are swept at most once per
    ``window / 4``, and when ``max_keys`` is reached the stalest *unblocked*
    keys are evicted in batches of 10% (amortised O(1) per failure). Keys that
    are currently blocking someone are never evicted, so flooding the limiter
    cannot be used to wipe a lockout.
    """

    MAX_USERNAME_CHARS = 128  # longer names are truncated so keys stay small
    EVICT_FRACTION = 10  # evict 1/10 of max_keys at a time

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
        self._failures: dict[tuple, deque] = {}

    # --- helpers (callers hold the lock) -------------------------------------
    def _user_key(self, ip: str, username: str) -> tuple:
        return (ip, username.lower()[: self.MAX_USERNAME_CHARS])

    def _limit(self, key: tuple) -> int:
        return self.max_per_ip if len(key) == 1 else self.max_per_user

    def _live_events(self, key: tuple):
        """Failures of ``key`` still inside the window; drops the key when none are."""
        events = self._failures.get(key)
        if events is None:
            return None
        cutoff = self._clock() - self.window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._failures[key]
            return None
        return events

    def _is_blocked(self, key: tuple) -> bool:
        events = self._live_events(key)
        return events is not None and len(events) >= self._limit(key)

    def _expire_all(self, now: float) -> None:
        cutoff = now - self.window
        for key in [k for k, events in self._failures.items() if events[-1] <= cutoff]:
            del self._failures[key]
        self._last_sweep = now

    def _evict_batch(self) -> None:
        """Forget the stalest keys that are not blocking anyone."""
        batch = max(1, self.max_keys // self.EVICT_FRACTION)
        evictable = [k for k in self._failures if not self._is_blocked(k)]
        for key in heapq.nsmallest(batch, evictable, key=lambda k: self._failures[k][-1]):
            del self._failures[key]

    def _append(self, key: tuple, now: float) -> None:
        events = self._failures.get(key)
        if events is None:
            if len(self._failures) >= self.max_keys:
                self._evict_batch()
            if len(self._failures) >= self.max_keys:
                return  # table full of live lockouts: keep them, skip tracking this key
            events = self._failures[key] = deque(maxlen=self._limit(key))
        events.append(now)

    # --- public API ----------------------------------------------------------
    def retry_after(self, ip: str, username: str) -> int:
        """Seconds until a blocked caller may try again; 0 when not blocked."""
        with self._lock:
            waits = []
            for key in (self._user_key(ip, username), (ip,)):
                if self._is_blocked(key):
                    waits.append(math.ceil(self._failures[key][0] + self.window - self._clock()))
            return max(waits, default=0)

    def record_failure(self, ip: str, username: str) -> None:
        with self._lock:
            now = self._clock()
            if now - self._last_sweep >= self.window / 4:
                self._expire_all(now)
            self._append(self._user_key(ip, username), now)
            self._append((ip,), now)

    def reset(self, ip: str, username: str) -> None:
        with self._lock:
            self._failures.pop(self._user_key(ip, username), None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter()
