from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.src.Generation.rag_chain import RAGChain

chat_router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    query: str


@chat_router.post("/query")
async def chat_query(request: ChatRequest):
    try:
        chain = RAGChain()
        result = await chain.generate(
            query=request.query,
            session_id=request.session_id,
            user_id=request.user_id,
        )
        return {
            "status": "success",
            "session_id": request.session_id,
            "answer": result["answer"],
            "sources": result["sources"],
        }
    except Exception as e:
        log.error("Chat query endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate response.")
