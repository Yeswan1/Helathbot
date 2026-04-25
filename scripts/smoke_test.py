import argparse
import json
import sys
from datetime import datetime

import requests


def login(base_url: str) -> dict:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    username = f"smoketester{stamp}"
    password = "secret123"

    register_body = {
        "username": username,
        "display_name": "Smoke Tester",
        "password": password,
    }
    register_res = requests.post(f"{base_url}/auth/register", json=register_body, timeout=15)
    if register_res.status_code not in (200, 400):
        register_res.raise_for_status()

    login_body = {"username": username, "password": password}
    res = requests.post(f"{base_url}/auth/login", json=login_body, timeout=15)
    res.raise_for_status()
    payload = res.json()
    token = payload.get("token", "")
    if not token:
        raise AssertionError("/auth/login did not return token")
    return {"Authorization": f"Bearer {token}"}


def check_health(base_url: str) -> None:
    res = requests.get(f"{base_url}/health", timeout=15)
    res.raise_for_status()
    payload = res.json()
    if payload.get("status") != "ok":
        raise AssertionError(f"Unexpected /health payload: {payload}")
    print("PASS /health")


def check_rag_chat(base_url: str, headers: dict) -> None:
    body = {"question": "What are healthy sleep habits?"}
    res = requests.post(f"{base_url}/chat", json=body, headers=headers, timeout=45)
    res.raise_for_status()
    payload = res.json()
    answer = payload.get("answer", "")
    chunks = payload.get("retrieved_chunks", [])

    if not answer.strip():
        raise AssertionError("/chat (RAG) returned empty answer")
    if not isinstance(chunks, list) or len(chunks) == 0:
        raise AssertionError("/chat (RAG) did not return retrieved chunks")
    print("PASS /chat (RAG)")


def check_wellness_chat(base_url: str, headers: dict) -> None:
    body = {"question": "I feel anxious today"}
    res = requests.post(f"{base_url}/chat", json=body, headers=headers, timeout=30)
    res.raise_for_status()
    payload = res.json()
    answer = payload.get("answer", "")
    chunks = payload.get("retrieved_chunks", None)

    if "anxious" not in answer.lower() and "breathing" not in answer.lower():
        raise AssertionError("/chat (wellness) response did not look like wellness support")
    if chunks != []:
        raise AssertionError("/chat (wellness) should return empty retrieved_chunks")
    print("PASS /chat (wellness)")


def check_appointments(base_url: str, headers: dict) -> None:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    name = f"Smoke Test {timestamp}"
    date = "2026-05-01T10:30"

    create_body = {"name": name, "appointment_date": date}
    create_res = requests.post(f"{base_url}/appointments", json=create_body, headers=headers, timeout=20)
    create_res.raise_for_status()
    created = create_res.json().get("appointment", {})

    if created.get("name") != name:
        raise AssertionError(f"Unexpected created appointment payload: {created}")

    list_res = requests.get(f"{base_url}/appointments", headers=headers, timeout=20)
    list_res.raise_for_status()
    appointments = list_res.json().get("appointments", [])
    names = [a.get("name") for a in appointments]

    if name not in names:
        raise AssertionError("Created appointment not found in /appointments list")
    print("PASS /appointments create + list")


def run(base_url: str) -> None:
    print(f"Running smoke tests against {base_url}")
    headers = login(base_url)
    print("PASS /auth/login")
    check_health(base_url)
    check_rag_chat(base_url, headers)
    check_wellness_chat(base_url, headers)
    check_appointments(base_url, headers)
    print("ALL TESTS PASSED")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run API smoke tests for Smart Healthcare Assistant")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL of running backend")
    args = parser.parse_args()

    try:
        run(args.base_url.rstrip("/"))
        return 0
    except (requests.RequestException, AssertionError, json.JSONDecodeError) as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
