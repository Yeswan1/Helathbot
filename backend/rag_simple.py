import os
import requests

HF_API_KEY = os.getenv("HF_API_KEY")

def get_embedding(text):
    url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}"
    }

    response = requests.post(url, headers=headers, json={"inputs": text})
    return response.json()[0]


def cosine_sim(a, b):
    return sum(x*y for x,y in zip(a,b))
