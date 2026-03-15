from app.auth.security import hash_password, verify_password


def test_hash_password_returns_bcrypt_string():
    hashed = hash_password("mysecret")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert hashed != "mysecret"


def test_verify_password_correct():
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mysecret")
    assert verify_password("wrongpassword", hashed) is False


def test_two_hashes_of_same_password_differ():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1) is True
    assert verify_password("same", h2) is True
