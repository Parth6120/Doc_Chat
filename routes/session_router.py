from fastapi import APIRouter, HTTPException, Query, Body

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.config.config import get_settings
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.utils.chat_history import ChatHistoryManager

session_router = APIRouter()


def _get_manager() -> ChatHistoryManager:
    settings = get_settings()
    config = load_config()
    return ChatHistoryManager(
        mongodb_url=settings.MONGODB_URL.get_secret_value(),
        db_name=config["mongodb"]["db_name"],
    )


@session_router.post("/new")
async def create_session(
    user_id: str = Query(..., description="Unique user identifier"),
    title: str = Query("New Chat", description="Session display name"),
):
    try:
        session_id = await _get_manager().create_session(user_id, title=title)
        return {"status": "success", "user_id": user_id, "session_id": session_id, "title": title}
    except Exception as e:
        log.error("Failed to create session", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create session.")


@session_router.patch("/{session_id}/rename")
async def rename_session(
    session_id: str,
    title: str = Body(..., embed=True, description="New session title"),
):
    try:
        await _get_manager().rename_session(session_id, title)
        return {"status": "success", "session_id": session_id, "title": title}
    except Exception as e:
        log.error("Failed to rename session", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to rename session.")


@session_router.get("/list")
async def list_sessions(user_id: str = Query(..., description="Unique user identifier")):
    try:
        sessions = await _get_manager().list_sessions(user_id)
        return {"user_id": user_id, "sessions": sessions}
    except Exception as e:
        log.error("Failed to list sessions", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list sessions.")


@session_router.get("/{session_id}/messages")
async def get_session_messages(session_id: str):
    try:
        messages = await _get_manager().get_history(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        log.error("Failed to get messages", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get messages.")


@session_router.delete("/{session_id}")
async def delete_session(session_id: str):
    try:
        await _get_manager().delete_session(session_id)
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        log.error("Failed to delete session", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete session.")
