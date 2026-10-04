import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from main import app, urls, Base62Encode, generate_code


client = TestClient(app)


# -------------------------
# Base62 tests
# -------------------------

def test_base62_zero():
    assert Base62Encode(0) == "0"


def test_base62_one():
    assert Base62Encode(1) == "1"


def test_base62_61():
    assert Base62Encode(61) == "Z"


def test_base62_62():
    assert Base62Encode(62) == "10"


def test_base62_63():
    assert Base62Encode(63) == "11"


def test_base62_large_number():
    result = Base62Encode(100000)

    assert isinstance(result, str)
    assert len(result) > 0


# -------------------------
# Code generator tests
# -------------------------

def test_generate_code_not_empty():
    code = generate_code()

    assert code != ""


def test_generate_code_is_string():
    code = generate_code()

    assert isinstance(code, str)


def test_generate_code_has_no_collision():
    urls.clear()

    urls["1"] = "https://example.com"

    code = generate_code()

    assert code != "1"
    assert code not in urls


# -------------------------
# POST /shorten tests
# -------------------------

def test_shorten_valid_url():
    urls.clear()

    response = client.post(
        "/shorten",
        json={"url": "https://www.google.com"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "code" in data
    assert "short_url" in data


def test_shorten_stores_url():
    urls.clear()

    response = client.post(
        "/shorten",
        json={"url": "https://example.com"}
    )

    data = response.json()

    code = data["code"]

    assert code in urls
    assert urls[code] == "https://example.com/"


def test_invalid_url():
    response = client.post(
        "/shorten",
        json={"url": "not-a-valid-url"}
    )

    assert response.status_code == 422


def test_missing_url():
    response = client.post(
        "/shorten",
        json={}
    )

    assert response.status_code == 422


def test_url_wrong_type():
    response = client.post(
        "/shorten",
        json={"url": 12345}
    )

    assert response.status_code == 422


# -------------------------
# Redirect tests
# -------------------------

def test_redirect_existing_code():
    urls.clear()

    urls["abc"] = "https://google.com"

    response = client.get(
        "/abc",
        follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://google.com"


def test_redirect_invalid_code():
    urls.clear()

    response = client.get(
        "/doesnotexist",
        follow_redirects=False
    )

    assert response.status_code == 404