# Protect the public /ask endpoint. Every call spends Anthropic API credit, so a deployed
# server must not answer strangers: require a shared key, and cap how many questions per minute.
# Standard library only, so the unit tests (and CI) don't need the API or the database.
import secrets
import threading
import time
from collections import deque


def key_ok(given, expected):
    """True only if a key is configured and the request sent exactly that key.

    Fails closed: with no key configured (expected empty), every request is refused,
    so forgetting to set APP_API_KEY can't leave the endpoint open.
    compare_digest takes the same time however many characters match (no timing leak).
    """
    if not expected or given is None:
        return False
    return secrets.compare_digest(given.encode(), expected.encode())


class RateLimiter:
    """At most max_calls in any window of per_seconds (sliding window, one server process)."""

    def __init__(self, max_calls, per_seconds, clock=time.monotonic):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.clock = clock                  # injectable so tests don't have to sleep
        self.calls = deque()                # timestamps of accepted calls, oldest first
        self.lock = threading.Lock()        # FastAPI runs sync endpoints in a thread pool

    def allow(self):
        with self.lock:
            now = self.clock()
            while self.calls and now - self.calls[0] >= self.per_seconds:
                self.calls.popleft()        # drop calls that left the window
            if len(self.calls) >= self.max_calls:
                return False
            self.calls.append(now)
            return True
