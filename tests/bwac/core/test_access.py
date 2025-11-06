from bwac.core.access import Access


def test_acquire(tmp_path):
    access = Access()
    access.acquire()

    assert access.access_token
    assert access.expires_in
