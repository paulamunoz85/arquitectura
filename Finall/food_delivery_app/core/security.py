import base64
import hashlib
import hmac
import json
import os
import time

try:
    import bcrypt  # type: ignore
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

_SECRET_KEY = b"marketplace-super-secret-key-2026"  # firma HMAC del token de sesión


def hash_password(plain: str) -> str:
    if _HAS_BCRYPT:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # Fallback PBKDF2 (100k iteraciones) con salt embebido "salt$hash"
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 100_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if _HAS_BCRYPT and hashed.startswith("$2"):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False
    try:
        salt_b64, hash_b64 = hashed.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def generar_token(payload: dict, ttl_segundos: int = 60 * 60 * 8) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    body = dict(payload)
    body["exp"] = time.time() + ttl_segundos
    segment1 = _b64(json.dumps(header).encode())
    segment2 = _b64(json.dumps(body).encode())
    signing_input = f"{segment1}.{segment2}".encode()
    signature = hmac.new(_SECRET_KEY, signing_input, hashlib.sha256).digest()
    segment3 = _b64(signature)
    return f"{segment1}.{segment2}.{segment3}"


def validar_token(token: str):
    try:
        segment1, segment2, segment3 = token.split(".")
        signing_input = f"{segment1}.{segment2}".encode()
        expected_sig = hmac.new(_SECRET_KEY, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64d(segment3)):
            return None
        payload = json.loads(_b64d(segment2))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
