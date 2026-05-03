"""
API client — the single modularity boundary between the Streamlit UI and the
FastAPI backend. All HTTP calls live here. No backend URLs appear elsewhere.
"""

import json
import os

import httpx

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
_TIMEOUT = httpx.Timeout(120.0)
_UPLOAD_TIMEOUT = httpx.Timeout(300.0)


def create_session(user_id: str, title: str = "New Chat") -> str:
    r = httpx.post(
        f"{BASE_URL}/session/new",
        params={"user_id": user_id, "title": title},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["session_id"]


def rename_session(session_id: str, title: str) -> None:
    r = httpx.patch(
        f"{BASE_URL}/session/{session_id}/rename",
        json={"title": title},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()


def list_sessions(user_id: str) -> list:
    r = httpx.get(f"{BASE_URL}/session/list", params={"user_id": user_id}, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["sessions"]


def delete_session(session_id: str) -> None:
    r = httpx.delete(f"{BASE_URL}/session/{session_id}", timeout=_TIMEOUT)
    r.raise_for_status()


def get_session_messages(session_id: str) -> list:
    r = httpx.get(f"{BASE_URL}/session/{session_id}/messages", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()["messages"]


def ingest_document(file_bytes: bytes, filename: str, user_id: str) -> dict:
    with httpx.Client(timeout=_UPLOAD_TIMEOUT) as client:
        r = client.post(
            f"{BASE_URL}/documents/pinecone/ingest/",
            files={"file": (filename, file_bytes)},
            params={"user_id": user_id},
        )
        r.raise_for_status()
    return r.json()


def stream_chat(user_id: str, session_id: str, query: str, sources_out: list):
    """
    Generator that yields text tokens from the SSE streaming endpoint.
    Populates `sources_out` with source filenames when streaming finishes.
    Pass this directly to st.write_stream().
    """
    with httpx.stream(
        "POST",
        f"{BASE_URL}/chat/stream",
        json={"user_id": user_id, "session_id": session_id, "query": query},
        timeout=_UPLOAD_TIMEOUT,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            try:
                payload = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if payload.get("done"):
                sources_out.extend(payload.get("sources", []))
            elif "token" in payload:
                yield payload["token"]
