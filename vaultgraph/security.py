"""Password hashing (scrypt, stdlib) and JWT (HS256, PyJWT)."""
import hashlib, hmac, os, time
import jwt
from . import config
from .errors import AuthError


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), dk_hex)  # constant-time compare
    except Exception:
        return False


def create_token(user_id: int, secret: str | None = None, ttl_min: int | None = None) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + 60 * (ttl_min or config.JWT_TTL_MIN)}
    return jwt.encode(payload, secret or config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str, secret: str | None = None) -> int:
    try:
        # algorithms is pinned: prevents the classic "alg: none" / algorithm-confusion attacks.
        data = jwt.decode(token, secret or config.JWT_SECRET, algorithms=["HS256"])
        return int(data["sub"])
    except Exception:
        raise AuthError("invalid or expired token")
