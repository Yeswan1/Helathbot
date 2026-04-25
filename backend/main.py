from pathlib import Path
import os
import secrets
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from .db import create_appointment, create_user, init_db, list_appointments, verify_user_password
    from .rag import RAGEngine
except ImportError:
    from db import create_appointment, create_user, init_db, list_appointments, verify_user_password
    from rag import RAGEngine

load_dotenv(override=True)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

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
    "sad": "I am sorry you are feeling sad. You are not alone. A short walk, deep breathing, or speaking with someone you trust may help.",
    "anxious": "Feeling anxious can be overwhelming. Try a slow breathing exercise: inhale for 4 seconds, hold for 4, exhale for 6.",
    "depressed": "I am really sorry you are feeling this way. It may help to talk to a mental health professional or someone you trust.",
    "stress": "Stress is common and manageable in small steps. Try short breaks, hydration, and writing down your top priorities.",
    "lonely": "Feeling lonely can be hard. Reaching out to a friend, family member, or support group can help.",
}


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, description="User question")


class ChatResponse(BaseModel):
    answer: str
    retrieved_chunks: List[str]


class AppointmentRequest(BaseModel):
    name: str = Field(..., min_length=2)
    appointment_date: str = Field(..., description="Use ISO format, e.g. 2026-04-30 10:30")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3)
    display_name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=6)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=10)


def get_current_user(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization token.")

    token = authorization.replace("Bearer ", "", 1).strip()
    user_name = SESSION_TOKENS.get(token)
    if not user_name:
        raise HTTPException(status_code=401, detail="Session expired or invalid token.")
    return user_name


def create_session_token(display_name: str) -> str:
    token = secrets.token_urlsafe(24)
    SESSION_TOKENS[token] = display_name
    return token


def get_rag_engine() -> RAGEngine:
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
        rag_engine.build_or_load_index()
    return rag_engine


def verify_google_credential(credential: str) -> dict:
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not google_client_id:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")

    response = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": credential},
        timeout=20,
    )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google credential.")

    payload = response.json()
    if payload.get("aud") != google_client_id:
        raise HTTPException(status_code=401, detail="Google credential was issued for a different client.")

    if not payload.get("email_verified", "false") in ("true", True):
        raise HTTPException(status_code=401, detail="Google email is not verified.")

    return payload


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    get_rag_engine()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/auth/google-config")
def google_config() -> dict:
    return {
        "enabled": bool(os.getenv("GOOGLE_CLIENT_ID")),
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    }


@app.post("/auth/register")
def register(payload: RegisterRequest) -> dict:
    username = payload.username.strip().lower()
    display_name = payload.display_name.strip()
    password = payload.password

    if verify_user_password(username, password):
        raise HTTPException(status_code=400, detail="Username already exists.")

    try:
        user = create_user(username, display_name, password)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Registration failed: {exc}") from exc

    token = secrets.token_urlsafe(24)
    SESSION_TOKENS[token] = user["display_name"]
    return {"token": token, "username": user["username"], "display_name": user["display_name"]}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict:
    username = payload.username.strip().lower()
    password = payload.password

    user = verify_user_password(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = secrets.token_urlsafe(24)
    SESSION_TOKENS[token] = user["display_name"]
    return {"token": token, "username": user["username"], "display_name": user["display_name"]}


@app.post("/auth/google")
def google_login(payload: GoogleAuthRequest) -> dict:
    google_user = verify_google_credential(payload.credential.strip())
    display_name = (google_user.get("name") or google_user.get("email", "Google User")).strip()
    email = (google_user.get("email") or "").strip().lower()

    token = create_session_token(display_name)
    return {
        "token": token,
        "username": email or display_name.lower().replace(" ", ""),
        "display_name": display_name,
        "email": email,
        "provider": "google",
    }


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, _: str = Depends(get_current_user)) -> ChatResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    lowered = question.lower()
    for keyword, support_message in MENTAL_WELLNESS_KEYWORDS.items():
        if keyword in lowered:
            return ChatResponse(answer=support_message, retrieved_chunks=[])

    engine = get_rag_engine()
    retrieved = engine.retrieve(question, k=3)
    answer = engine.generate_answer(question, retrieved)
    return ChatResponse(answer=answer, retrieved_chunks=retrieved)


@app.post("/appointments")
def create_appointment_endpoint(payload: AppointmentRequest, _: str = Depends(get_current_user)) -> dict:
    appointment = create_appointment(payload.name.strip(), payload.appointment_date.strip())
    return {"message": "Appointment booked successfully.", "appointment": appointment}


@app.get("/appointments")
def list_appointments_endpoint(_: str = Depends(get_current_user)) -> dict:
    return {"appointments": list_appointments()}


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
