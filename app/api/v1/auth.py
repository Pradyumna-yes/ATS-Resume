# app/api/v1/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from app.db.documents import User
from app.services.auth import hash_password, verify_password, create_access_token, decode_access_token, TokenData
from beanie import PydanticObjectId
from beanie.exceptions import CollectionWasNotInitialized
from uuid import uuid4

# In-memory user store fallback for environments without Mongo
_INMEM_USERS: dict[str, dict] = {}

router = APIRouter()

class SignupIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/auth/signup", status_code=201)
async def signup(payload: SignupIn):
    try:
        existing = await User.find_one({"email": payload.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        u = User(email=payload.email, password_hash=hash_password(payload.password))
        await u.insert()
        token = create_access_token(str(u.id))
        return {"access_token": token, "token_type": "bearer"}
    except CollectionWasNotInitialized:
        # fallback to in-memory store
        if any(u["email"] == payload.email for u in _INMEM_USERS.values()):
            raise HTTPException(status_code=400, detail="Email already registered")
        uid = str(uuid4())
        _INMEM_USERS[uid] = {"id": uid, "email": payload.email, "password_hash": hash_password(payload.password)}
        token = create_access_token(uid)
        return {"access_token": token, "token_type": "bearer"}

@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn):
    try:
        user = await User.find_one({"email": payload.email})
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token(str(user.id))
        return {"access_token": token, "token_type": "bearer"}
    except CollectionWasNotInitialized:
        # fallback to in-memory
        for u in _INMEM_USERS.values():
            if u["email"] == payload.email and verify_password(payload.password, u["password_hash"]):
                token = create_access_token(u["id"])
                return {"access_token": token, "token_type": "bearer"}
        raise HTTPException(status_code=401, detail="Invalid credentials")

# Dependency to get current user (id)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        td = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not td.sub:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user = await User.get(td.sub)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except CollectionWasNotInitialized:
        u = _INMEM_USERS.get(td.sub)
        if not u:
            raise HTTPException(status_code=401, detail="User not found")
        # return a lightweight object with expected attributes
        class SimpleUser:
            def __init__(self, d):
                self.id = d.get("id")
                self.email = d.get("email")
                self.password_hash = d.get("password_hash")
        return SimpleUser(u)
