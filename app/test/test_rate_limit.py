from fastapi import status

from ..security import LoginRateLimiter, login_rate_limiter
from .utils import app, client, test_user  # noqa: F401  (test_user is a fixture)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_blocks_after_max_failures_and_expires():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=3, max_per_ip=10, window_seconds=60, clock=clock)

    for _ in range(3):
        assert limiter.retry_after('1.1.1.1', 'Ana') == 0
        limiter.record_failure('1.1.1.1', 'ana')
    assert 0 < limiter.retry_after('1.1.1.1', 'ANA') <= 60

    # other usernames / ips are unaffected by a single user being blocked
    assert limiter.retry_after('1.1.1.1', 'bob') == 0
    assert limiter.retry_after('2.2.2.2', 'ana') == 0

    clock.now += 61
    assert limiter.retry_after('1.1.1.1', 'ana') == 0


def test_limiter_blocks_an_ip_that_sprays_many_usernames():
    limiter = LoginRateLimiter(max_per_user=5, max_per_ip=4, window_seconds=60, clock=FakeClock())
    for name in ('a', 'b', 'c', 'd'):
        limiter.record_failure('9.9.9.9', name)
    assert limiter.retry_after('9.9.9.9', 'someone-new') > 0


def test_successful_login_clears_the_user_counter():
    limiter = LoginRateLimiter(max_per_user=3, window_seconds=60, clock=FakeClock())
    limiter.record_failure('1.1.1.1', 'ana')
    limiter.record_failure('1.1.1.1', 'ana')
    limiter.reset('1.1.1.1', 'ana')
    limiter.record_failure('1.1.1.1', 'ana')
    assert limiter.retry_after('1.1.1.1', 'ana') == 0


def test_login_endpoint_locks_out_after_five_failures(test_user):
    wrong = {'username': test_user.username, 'password': 'wrong-password1'}
    for _ in range(5):
        assert client.post('/auth/token', data=wrong).status_code == status.HTTP_401_UNAUTHORIZED

    # even the right password is refused while locked out
    response = client.post(
        '/auth/token', data={'username': test_user.username, 'password': 'testpassword'}
    )
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert int(response.headers['retry-after']) > 0


def test_login_endpoint_success_resets_counter(test_user):
    wrong = {'username': test_user.username, 'password': 'wrong-password1'}
    right = {'username': test_user.username, 'password': 'testpassword'}
    for _ in range(4):
        client.post('/auth/token', data=wrong)
    assert client.post('/auth/token', data=right).status_code == status.HTTP_200_OK
    for _ in range(4):
        assert client.post('/auth/token', data=wrong).status_code == status.HTTP_401_UNAUTHORIZED
    assert client.post('/auth/token', data=right).status_code == status.HTTP_200_OK
