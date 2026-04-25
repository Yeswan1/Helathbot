from pathlib import Path
import os
from typing import Dict, List, Optional

try:
    from .rag_simple import retrieve
    from .db import create_appointment, create_user, init_db, list_appointments, verify_user_password
except ImportError:
    from rag_simple import retrieve
    from db import create_appointment, create_user, init_db, list_appointments, verify_user_password

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from jose import jwt, JWTError
from datetime import datetime, timedelta

load_dotenv(override=True)

app = FastAPI(title="Smart Healthcare Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- JWT CONFIG ----------------

SECRET_KEY = "mysecretkey123"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.split(" ")[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------- MODELS ----------------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2)


class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: List[str]


class AppointmentRequest(BaseModel):
    name: str
    appointment_date: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    display_name: str
    password: str


# ---------------- STARTUP ----------------

@app.on_event("startup")
def startup_event():
    init_db()


# ---------------- ROUTES ----------------

@app.get("/")
def root():
    return {"message": "HealthBot API running 🚀"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(payload: RegisterRequest):
    user = create_user(payload.username, payload.display_name, payload.password)
    token = create_access_token({"sub": user["display_name"]})
    return {"token": token}


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = verify_user_password(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user["display_name"]})
    return {"token": token}


# ---------------- GROQ ----------------

def ask_groq(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(url, json=data, headers=headers)
    return response.json()["choices"][0]["message"]["content"]


# ---------------- CHAT (RAG) ----------------

@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, user: str = Depends(get_current_user)):

    chunks = retrieve(payload.question)

    context = "\n".join(chunks)

    prompt = f"""
Use the context below to answer:

{context}

Question: {payload.question}
"""

    answer = ask_groq(prompt)

    return ChatResponse(
        answer=answer,
        retrieved_chunks=chunks
    )


@app.post("/appointments")
def create_app(payload: AppointmentRequest, user: str = Depends(get_current_user)):
    return create_appointment(payload.name, payload.appointment_date)


@app.get("/appointments")
def list_app(user: str = Depends(get_current_user)):
    return {"appointments": list_appointments()}
