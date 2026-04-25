from pathlib import Path
import os
import secrets
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .db import create_appointment, create_user, init_db, list_appointments, verify_user_password
    from .rag import RAGEngine
except ImportError:
    from db import create_appointment, create_user, init_db, list_appointments, verify_user_password
    from rag import RAGEngine

load_dotenv(override=True)

app = FastAPI(title="Smart Healthcare Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_engine: Optional[RAGEngine] = None
SESSION_TOKENS: Dict[str, str] = {}

MENTAL_WELLNESS_KEYWORDS = {
    "sad": "I am sorry you are feeling sad. You are not alone.",
    "anxious": "Try breathing slowly: inhale 4s, hold 4s, exhale 6s.",
    "depressed": "Please consider talking to a professional.",
    "stress": "Take breaks and stay hydrated.",
    "lonely": "Reach out to someone you trust.",
}


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


class GoogleAuthRequest(BaseModel):
    credential: str


# ---------------- AUTH ----------------

def get_current_user(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")

    token = authorization.replace("Bearer ", "")
    user = SESSION_TOKENS.get(token)

    if not user:
        raise HTTPException(status_code=401, detail="Session expired")

    return user


def create_session_token(name: str):
    token = secrets.token_urlsafe(24)
    SESSION_TOKENS[token] = name
    return token


# ---------------- RAG ----------------

def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
        rag_engine.build_or_load_index()
    return rag_engine


# ---------------- STARTUP ----------------

@app.on_event("startup")
def startup_event():
    init_db()
    # ❌ Removed heavy RAG loading here


# ---------------- ROUTES ----------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(payload: RegisterRequest):
    user = create_user(payload.username, payload.display_name, payload.password)
    token = create_session_token(user["display_name"])
    return {"token": token}


@app.post("/auth/login")
def login(payload: LoginRequest):
    user = verify_user_password(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session_token(user["display_name"])
    return {"token": token}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, _: str = Depends(get_current_user)):
    question = payload.question.lower()

    # mental support shortcut
    for key, msg in MENTAL_WELLNESS_KEYWORDS.items():
        if key in question:
            return ChatResponse(answer=msg, retrieved_chunks=[])

    engine = get_rag_engine()
    chunks = engine.retrieve(question)
    answer = engine.generate_answer(question, chunks)

    return ChatResponse(answer=answer, retrieved_chunks=chunks)


@app.post("/appointments")
def create_app(payload: AppointmentRequest, _: str = Depends(get_current_user)):
    return create_appointment(payload.name, payload.appointment_date)


@app.get("/appointments")
def list_app(_: str = Depends(get_current_user)):
    return {"appointments": list_appointments()}
