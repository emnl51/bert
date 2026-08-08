from app.secrets import decrypt_secret, encrypt_secret


def test_secret_roundtrip():
    token = '123456:ABC-secret-value'
    encrypted = encrypt_secret(token)
    assert encrypted != token
    assert decrypt_secret(encrypted) == token
