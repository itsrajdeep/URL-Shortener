import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  #allows to test without starting server

from main import app, Base62Encode, generate_code

client = TestClient(app) #Testing Client


#  Encoder Tests ---
def test_base62_zero():
    assert Base62Encode(0) == "0"

def test_base62_one():
    assert Base62Encode(1) == "1"

def test_base62_61():
    assert Base62Encode(61) == "Z"

def test_base62_62():
    assert Base62Encode(62) == "10"

def test_base62_large_number():
    result = Base62Encode(100000)

    assert isinstance(result, str)
    assert len(result) > 0


#Code-Generator Tests --- 

def test_generate_code_not_empty():
    code = generate_code()

    assert code != ""

def test_generate_code_is_string():
    code = generate_code()

    assert isinstance(code, str)

def test_generate_code_length():
    code = generate_code()

    assert 1 <= len(code) <= 6

#API Tests -----

def test_shorten_valid_url():
    response = client.post(
        "/shorten",
        json={"url": "https://www.google.com"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "code" in data
    assert "short_url" in data

def test_shorten_returns_valid_code():
    response = client.post(
        "/shorten",
        json={"url": "https://example.com"}
    )

    data = response.json()

    assert isinstance(data["code"], str)
    assert len(data["code"]) > 0


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