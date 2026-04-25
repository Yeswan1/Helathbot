import os
import requests
from pathlib import Path

HF_API_KEY = os.getenv("HF_API_KEY")

BASE_DIR = Path(__file__).resolve().parent


def get_embedding(text):
    url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}"
    }

    response = requests.post(url, headers=headers, json={"inputs": text})
    return response.json()[0]


def cosine_sim(a, b):
    return sum(x * y for x, y in zip(a, b))


def load_docs():
    file_path = BASE_DIR / "data" / "medical_data.txt"
    with open(file_path, "r") as f:
        return f.read().split("\n\n")


def retrieve(query):
    docs = load_docs()
    query_vec = get_embedding(query)

    scores = []
    for doc in docs:
        doc_vec = get_embedding(doc)
        score = cosine_sim(query_vec, doc_vec)
        scores.append((score, doc))

    scores.sort(reverse=True)
    return [doc for _, doc in scores[:2]]
