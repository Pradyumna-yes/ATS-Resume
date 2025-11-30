# app/services/auth.py
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets
from jose import jwt, JWTError
from pydantic import BaseModel
from app.core.config import settings

 # Password hashing using PBKDF2-HMAC-SHA256 (avoids bcrypt backend issues)
_PBKDF2_ITERATIONS = 100_000

# JWT config
SECRET_KEY = getattr(settings, "SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60))

class TokenData(BaseModel):
    sub: Optional[str] = None

def hash_password(password: str) -> str:
    if password is None:
        password = ""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    if plain is None:
        plain = ""
    try:
        scheme, iterations, salt, hashhex = hashed.split("$")
        iterations = int(iterations)
    except Exception:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), iterations)
    return secrets.compare_digest(dk.hex(), hashhex)

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.utcnow()
    exp = now + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "iat": now, "exp": exp}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return TokenData(sub=sub)
    except JWTError as exc:
        raise exc
