from guard import key_ok, RateLimiter


def test_correct_key_passes():
    assert key_ok("s3cret", "s3cret")


def test_wrong_or_missing_key_is_refused():
    assert not key_ok("wrong", "s3cret")
    assert not key_ok(None, "s3cret")
    assert not key_ok("", "s3cret")


def test_no_key_configured_refuses_everyone():
    # fail closed: forgetting APP_API_KEY must not open the endpoint
    assert not key_ok("anything", "")
    assert not key_ok("", "")
    assert not key_ok(None, "")


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_rate_limit_blocks_after_max_calls():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=3, per_seconds=60, clock=clock)
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]


def test_rate_limit_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=2, per_seconds=60, clock=clock)
    assert limiter.allow() and limiter.allow()
    clock.t = 59.9
    assert not limiter.allow()          # both calls are still inside the window
    clock.t = 60.0
    assert limiter.allow()              # the first two left the window


def test_refused_calls_do_not_use_up_the_window():
    clock = FakeClock()
    limiter = RateLimiter(max_calls=1, per_seconds=60, clock=clock)
    assert limiter.allow()
    for _ in range(5):
        assert not limiter.allow()
    clock.t = 60.0
    assert limiter.allow()              # refused calls were not recorded
