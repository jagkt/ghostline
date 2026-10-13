import os
import time
import jwt

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = int(os.environ["JWT_EXPIRY_MINUTES"])


def create_token(account_id, user_id, role):
    now = int(time.time())
    payload = {
        "account_id": account_id,
        "user_id": user_id,
        "role": role,
        "iat": now,
        "exp": now + JWT_EXPIRY_MINUTES * 60,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
