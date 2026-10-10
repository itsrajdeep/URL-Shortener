import uuid

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app, follow_redirects=False)


@pytest.fixture
def stored_url():
    """Create a URL directly in PostgreSQL for redirect tests."""
    code = "t" + uuid.uuid4().hex[:8]
    original_url = "https://example.com/" + code

    with main.conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO urls (short_code, original_url, expires_at)
            VALUES (%s, %s, NULL)
            """,
            (code, original_url),
        )
    main.conn.commit()

    yield code, original_url

    # Remove associated click records before deleting the URL.
    with main.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM clicks WHERE short_code = %s",
            (code,),
        )
        cur.execute(
            "DELETE FROM urls WHERE short_code = %s",
            (code,),
        )
    main.conn.commit()
    main.r.delete(code)


def test_rate_limiter_blocks_eleventh_request():
    key = "rate_limit:testclient"
    main.r.delete(key)

    try:
        for i in range(10):
            response = client.post(
                "/shorten",
                json={"url": f"https://example.com/{i}"},
            )
            assert response.status_code == 200

        response = client.post(
            "/shorten",
            json={"url": "https://example.com/blocked"},
        )

        assert response.status_code == 429
        assert response.json()["detail"] == "Too many request"

    finally:
        main.r.delete(key)


def test_redis_cache_hit(stored_url):
    code, original_url = stored_url

    # Populate Redis before making the request.
    main.r.set(code,original_url,ex=300)

    response = client.get(f"/{code}")

    assert response.status_code == 302
    assert response.headers["location"] == original_url

    # A redirect served from Redis must still record a click.
    with main.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM clicks WHERE short_code = %s",
            (code,),
        )
        assert cur.fetchone()[0] == 1


def test_redis_cache_miss_fetches_postgres(stored_url):
    code, original_url = stored_url
    main.r.delete(code)

    response = client.get(f"/{code}")

    assert response.status_code == 302
    assert response.headers["location"] == original_url

    # PostgreSQL fallback should populate the Redis cache.
    assert main.r.get(code) == original_url

    with main.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM clicks WHERE short_code = %s",
            (code,),
        )
        assert cur.fetchone()[0] == 1


def test_unknown_code_returns_404():
    code = "missing" + uuid.uuid4().hex[:3]
    main.r.delete(code)

    response = client.get(f"/{code}")

    assert response.status_code == 404