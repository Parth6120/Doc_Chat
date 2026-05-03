import uuid
from datetime import datetime, timezone
from typing import List, Dict

import motor.motor_asyncio

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException


class ChatHistoryManager:
    """
    Manages per-user, per-session chat history stored in MongoDB.
    Collections:
      sessions  — one document per conversation thread
      messages  — one document per message, referenced by session_id
    """

    def __init__(self, mongodb_url: str, db_name: str):
        client = motor.motor_asyncio.AsyncIOMotorClient(mongodb_url)
        db = client[db_name]
        self._sessions = db["sessions"]
        self._messages = db["messages"]

    async def create_session(self, user_id: str) -> str:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        await self._sessions.insert_one({
            "_id": session_id,
            "user_id": user_id,
            "title": "New Chat",
            "created_at": now,
            "updated_at": now,
        })
        log.info("Session created", user_id=user_id, session_id=session_id)
        return session_id

    async def list_sessions(self, user_id: str) -> List[Dict]:
        cursor = self._sessions.find(
            {"user_id": user_id},
            {"_id": 1, "title": 1, "created_at": 1, "updated_at": 1},
        ).sort("updated_at", -1)
        sessions = []
        async for doc in cursor:
            doc["session_id"] = doc.pop("_id")
            sessions.append(doc)
        return sessions

    async def get_history(self, session_id: str) -> List[Dict]:
        """Returns messages in chronological order as {role, content} dicts."""
        cursor = self._messages.find(
            {"session_id": session_id},
            {"_id": 0, "role": 1, "content": 1},
        ).sort("_id", 1)
        return [doc async for doc in cursor]

    async def save_exchange(self, session_id: str, query: str, answer: str) -> None:
        now = datetime.now(timezone.utc)
        await self._messages.insert_many([
            {"session_id": session_id, "role": "human", "content": query, "timestamp": now},
            {"session_id": session_id, "role": "ai", "content": answer, "timestamp": now},
        ])
        await self._sessions.update_one(
            {"_id": session_id},
            {"$set": {"updated_at": now}},
        )
        log.info("Exchange saved", session_id=session_id)

    async def delete_session(self, session_id: str) -> None:
        await self._sessions.delete_one({"_id": session_id})
        await self._messages.delete_many({"session_id": session_id})
        log.info("Session deleted", session_id=session_id)
