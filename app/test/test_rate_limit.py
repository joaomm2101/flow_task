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


def test_limiter_memory_is_bounded_when_spraying_unique_usernames():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=5, max_per_ip=10_000, window_seconds=60, max_keys=50, clock=clock)

    for i in range(1000):
        limiter.record_failure('7.7.7.7', f'user-{i}')

    assert len(limiter._failures) <= 51  # cap, plus the entry added right after a sweep


def test_limiter_forgets_expired_keys_without_being_queried_again():
    clock = FakeClock()
    limiter = LoginRateLimiter(window_seconds=60, max_keys=1000, clock=clock)
    for i in range(20):
        limiter.record_failure(f'10.0.0.{i}', 'someone')

    clock.now += 120  # everything expired; nobody ever asks about those keys again
    limiter.record_failure('10.9.9.9', 'new')

    assert len(limiter._failures) == 2  # only the fresh (ip, user) and (ip,) keys remain


def test_limiter_truncates_huge_usernames():
    limiter = LoginRateLimiter(clock=FakeClock())
    limiter.record_failure('1.1.1.1', 'x' * 1_000_000)
    assert all(len(str(part)) <= 128 for key in limiter._failures for part in key)


def test_flooding_with_unique_keys_cannot_wipe_an_active_lockout():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=3, max_per_ip=100, window_seconds=600, max_keys=100, clock=clock)
    for _ in range(3):
        limiter.record_failure('6.6.6.6', 'victim')
    assert limiter.retry_after('6.6.6.6', 'victim') > 0

    # a botnet floods the limiter with thousands of one-off (ip, username) keys
    for i in range(5000):
        clock.now += 0.01
        limiter.record_failure(f'10.{i // 250}.{i % 250}.1', f'noise-{i}')

    assert len(limiter._failures) <= 100
    assert limiter.retry_after('6.6.6.6', 'victim') > 0  # the lockout survived


def test_full_table_of_lockouts_keeps_tracking_new_keys_and_stays_bounded():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=1, max_per_ip=1, window_seconds=600, max_keys=10, clock=clock)
    for i in range(5):  # 5 ips x (user key + ip key) = 10 keys, all blocking
        clock.now += 1
        limiter.record_failure(f'1.1.1.{i}', 'u')

    clock.now += 1
    limiter.record_failure('2.2.2.2', 'newcomer')  # must not be silently ignored (no fail-open)

    assert limiter.retry_after('2.2.2.2', 'newcomer') > 0
    assert len(limiter._failures) <= 10
    # the dropped lockouts are the ones closest to expiry (the oldest), the latest survive
    assert limiter.retry_after('1.1.1.4', 'u') > 0
    assert limiter.retry_after('1.1.1.0', 'u') == 0


def test_attacker_filling_the_table_with_lockouts_cannot_stop_new_attackers_being_limited():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=3, max_per_ip=3, window_seconds=600, max_keys=50, clock=clock)
    for i in range(200):  # botnet burns 3 failures per ip to fill the table with live lockouts
        clock.now += 0.01
        for _ in range(3):
            limiter.record_failure(f'8.8.{i // 250}.{i % 250}', 'x')
    assert len(limiter._failures) <= 50

    for _ in range(3):  # an unrelated attacker now guesses a victim's password
        limiter.record_failure('5.5.5.5', 'victim')

    assert limiter.retry_after('5.5.5.5', 'victim') > 0


def test_full_table_does_not_rescan_on_every_failure():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=1, max_per_ip=1, window_seconds=600, max_keys=1000, clock=clock)
    batches = 0
    original = limiter._evict_batch

    def counting_evict():
        nonlocal batches
        batches += 1
        original()

    limiter._evict_batch = counting_evict
    for i in range(5000):  # every new key is a live lockout, so nothing is "unblocked" to evict
        clock.now += 0.001
        limiter.record_failure(f'4.{i // 65536}.{(i // 256) % 256}.{i % 256}', 'u')

    assert batches <= 120  # ~10k insertions / 100 per batch, not ~9k scans
    assert len(limiter._failures) <= 1000


def test_eviction_work_is_amortised_not_per_failure():
    clock = FakeClock()
    limiter = LoginRateLimiter(max_per_user=5, max_per_ip=5, window_seconds=600, max_keys=1000, clock=clock)
    batches = 0
    original = limiter._evict_batch

    def counting_evict():
        nonlocal batches
        batches += 1
        original()

    limiter._evict_batch = counting_evict

    for i in range(10_000):
        clock.now += 0.001
        limiter.record_failure(f'3.{i // 65536}.{(i // 256) % 256}.{i % 256}', 'user')

    # 20k key insertions at a cap of 1000 evict 100 keys per batch => ~200 batches, not ~20k
    assert batches <= 300
    assert len(limiter._failures) <= 1000


def test_a_single_ip_cannot_create_unbounded_keys_through_the_endpoint(test_user):
    for i in range(60):
        client.post('/auth/token', data={'username': f'ghost-{i}', 'password': 'whatever1'})

    # blocked after 20 failures: the remaining 40 requests are refused before recording anything
    assert len(login_rate_limiter._failures) <= 20 + 1
