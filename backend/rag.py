from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import faiss
import numpy as np
from pypdf import PdfReader
import requests
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "backend" / "index_store"
INDEX_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = INDEX_DIR / "healthcare.faiss"
CHUNKS_FILE = INDEX_DIR / "chunks.json"


class RAGEngine:
    """Small, beginner-friendly RAG engine using local FAISS + embeddings."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.embedding_model = SentenceTransformer(model_name)
        self.index: faiss.IndexFlatL2 | None = None
        self.chunks: List[str] = []

    def _read_documents(self, folder_path: Path) -> List[str]:
        docs: List[str] = []
        for file_path in folder_path.glob("**/*"):
            if file_path.suffix.lower() == ".txt":
                docs.append(file_path.read_text(encoding="utf-8", errors="ignore"))
            elif file_path.suffix.lower() == ".pdf":
                pdf_text = []
                reader = PdfReader(str(file_path))
                for page in reader.pages:
                    pdf_text.append(page.extract_text() or "")
                docs.append("\n".join(pdf_text))
        return docs

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
        """Simple sliding-window chunking by character count."""
        normalized = " ".join(text.split())
        if not normalized:
            return []

        chunks = []
        start = 0
        while start < len(normalized):
            end = start + chunk_size
            chunks.append(normalized[start:end])
            if end >= len(normalized):
                break
            start = end - overlap
        return chunks

    def build_or_load_index(self) -> None:
        if INDEX_FILE.exists() and CHUNKS_FILE.exists():
            self.index = faiss.read_index(str(INDEX_FILE))
            self.chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
            return

        documents = self._read_documents(DATA_DIR)
        all_chunks: List[str] = []
        for doc in documents:
            all_chunks.extend(self._chunk_text(doc))

        if not all_chunks:
            all_chunks = [
                "No healthcare documents found. Please add .txt or .pdf files to the data folder."
            ]

        embeddings = self.embedding_model.encode(all_chunks, convert_to_numpy=True)
        embeddings = np.array(embeddings, dtype="float32")

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)
        self.chunks = all_chunks

        faiss.write_index(self.index, str(INDEX_FILE))
        CHUNKS_FILE.write_text(json.dumps(self.chunks, indent=2), encoding="utf-8")

    def retrieve(self, question: str, k: int = 3) -> List[str]:
        if self.index is None:
            raise RuntimeError("RAG index is not initialized.")

        query_embedding = self.embedding_model.encode([question], convert_to_numpy=True)
        query_embedding = np.array(query_embedding, dtype="float32")

        top_k = min(k, len(self.chunks))
        _, indices = self.index.search(query_embedding, top_k)
        return [self.chunks[idx] for idx in indices[0] if idx < len(self.chunks)]

    def generate_answer(self, question: str, context_chunks: List[str]) -> str:
        api_key = os.getenv("GROQ_API_KEY")
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

        context_text = "\n\n".join(context_chunks)

        # Fallback keeps the app usable for beginners without an API key.
        if not api_key:
            return (
                "I found relevant healthcare information but no LLM API key is configured. "
                "Set GROQ_API_KEY in your .env file for full AI-generated answers.\n\n"
                f"Relevant context:\n{context_text[:1200]}"
            )

        system_prompt = (
            "You are a careful healthcare assistant. "
            "Use only the provided context, avoid diagnosis, and encourage consulting medical professionals for serious issues."
        )
        user_prompt = (
            f"Context:\n{context_text}\n\n"
            f"Question: {question}\n\n"
            "Answer clearly in simple language."
        )

        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["choices"][0]["message"]["content"]
        except Exception as exc:
            return (
                "I could not generate a full AI response right now. "
                f"Error: {exc}.\n\nRelevant context:\n{context_text[:1200]}"
            )
