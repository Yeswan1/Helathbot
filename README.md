# Smart Healthcare Assistant (Full-Stack RAG)

A beginner-friendly healthcare chatbot using:
- FastAPI backend
- Local FAISS vector store
- sentence-transformers embeddings
- Groq API for answer generation
- SQLite for appointment booking
- Plain HTML + JavaScript frontend

## Project Structure

```text
smarthealth/
  backend/
    main.py
    rag.py
    db.py
  frontend/
    index.html
  data/
    health_guide.txt
    mental_wellness.txt
  scripts/
    smoke_test.py
  requirements.txt
  .env.example
  Dockerfile
```

## 1) Local Setup

1. Open terminal in the project root (`smarthealth`).
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create `.env` from `.env.example` and set your API key.
5. If you want Google sign-in, add `GOOGLE_CLIENT_ID` from Google Cloud Console.
  - Use a normal OAuth client ID for Google Identity Services.
  - Do not enable Google Identity Platform / Firebase paid features if you want to avoid billing prompts.
  - This app only verifies the Google ID token and does not require billing on its own.
6. Start the server from `backend` folder:

```bash
cd backend
uvicorn main:app --reload
```

6. Open your browser:
- `http://127.0.0.1:8000/` for UI
- `http://127.0.0.1:8000/docs` for Swagger API docs

## 2) API Endpoints

- `POST /auth/login`
  - Input JSON: `{ "username": "alex", "password": "secret123" }`
  - Output: `{ "token": "...", "username": "alex", "display_name": "Alex" }`
- `POST /auth/register`
  - Input JSON: `{ "username": "alex", "display_name": "Alex", "password": "secret123" }`
  - Output: `{ "token": "...", "username": "alex", "display_name": "Alex" }`
- `POST /auth/google`
  - Input JSON: `{ "credential": "<Google ID token>" }`
  - Requires `GOOGLE_CLIENT_ID` to be configured on the server
  - Output: `{ "token": "...", "username": "...", "display_name": "...", "email": "...", "provider": "google" }`
- `POST /chat`
  - Input JSON: `{ "question": "..." }`
  - Requires `Authorization: Bearer <token>`
  - Output: generated answer + retrieved chunks
- `POST /appointments`
  - Input JSON: `{ "name": "Alex", "appointment_date": "2026-05-01T10:30" }`
  - Requires `Authorization: Bearer <token>`
- `GET /appointments`
  - Output: all appointments from SQLite
  - Requires `Authorization: Bearer <token>`
- `GET /health`
  - Health check endpoint

## 3) Add Your Own Documents

Add `.txt` or `.pdf` files to the `data/` folder, then restart the app.

## 4) Deploy on Render

This repo includes a [`render.yaml`](render.yaml) blueprint and a Docker-based `Dockerfile`, so Render can deploy the app directly.

1. Push the repository to GitHub.
2. In Render, create a new Blueprint from the repo.
3. Render will read [`render.yaml`](render.yaml) and build the Docker image automatically.
4. Add environment variables in Render:
  - `GROQ_API_KEY`
  - Optional: `GROQ_MODEL` (default is `llama-3.1-8b-instant`)
  - Optional: `GROQ_BASE_URL` (default is `https://api.groq.com/openai/v1`)
  - Optional: `GOOGLE_CLIENT_ID` if you want Google sign-in
5. Render will route traffic to the port provided by `PORT`.

## 5) Deploy on Hugging Face Spaces (Docker)

1. Create a new Space on Hugging Face.
2. Choose **Docker** SDK.
3. Upload all project files to the Space repository.
4. In Space settings, add secret:
  - `GROQ_API_KEY`
5. Optional secret:
  - `GROQ_MODEL` (default is `llama-3.1-8b-instant`)
  - `GROQ_BASE_URL` (default is `https://api.groq.com/openai/v1`
  - `GOOGLE_CLIENT_ID` if you want Google sign-in
6. The `Dockerfile` starts the app on port `7860` by default and also respects `PORT` if the host provides it.
7. After build, open your Space URL.

## 6) One-Command Smoke Test

With the backend running, execute:

```bash
python scripts/smoke_test.py
```

Optional custom URL:

```bash
python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

This checks:
- `/health`
- `/chat` (RAG flow)
- `/chat` (mental wellness shortcut)
- `/appointments` create + list

## Notes

- Mental wellness keywords trigger immediate empathetic responses.
- This app is for educational support and not a replacement for medical diagnosis.
  


  & "D:/AGENTIC AI/LLM_usingLCEL/venvl/python.exe" -m uvicorn main:app --reload