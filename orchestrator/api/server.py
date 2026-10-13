import os
import re
import uuid
import logging
import jwt
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from db import api as db
from api import auth

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
logger = logging.getLogger("ghostline.api")

ph = PasswordHasher()

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.pool.open()
    logger.info("Database pool opened")
    yield
    await db.pool.close()
    logger.info("Database pool closed")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        return auth.decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    account_name: str
    email: EmailStr
    password: str


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:6]}"


@app.post("/auth/signup")
async def signup(req: SignupRequest):
    existing = await db.get_account_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    account_id = str(uuid.uuid4())
    slug = slugify(req.account_name)
    await db.create_account(account_id, req.account_name, slug)

    password_hash = ph.hash(req.password)
    user_id = str(uuid.uuid4())
    await db.create_account_user(user_id, account_id, req.email, password_hash)

    logger.info("New account created: %s (%s)", req.account_name, slug)
    return {"account_id": account_id, "slug": slug, "email": req.email}


@app.post("/auth/login")
async def login(req: LoginRequest):
    user = await db.get_account_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    try:
        ph.verify(user["password_hash"], req.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = auth.create_token(str(user["account_id"]), str(user["id"]), user["role"])
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user