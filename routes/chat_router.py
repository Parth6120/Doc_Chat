import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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


@chat_router.post("/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        try:
            chain = RAGChain()
            async for chunk in chain.stream(
                query=request.query,
                session_id=request.session_id,
                user_id=request.user_id,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            log.error("Stream endpoint error", error=str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
