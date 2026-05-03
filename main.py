from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routes.ingestion_router import ingestion_router
from routes.session_router import session_router
from routes.chat_router import chat_router

app = FastAPI(title="Multi-Doc-Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    ingestion_router,
    prefix="/documents",
    tags=["Document Management"])

app.include_router(
    session_router,
    prefix="/session",
    tags=["Session Management"])

app.include_router(
    chat_router,
    prefix="/chat",
    tags=["Chat"])

@app.get("/")
def server_status():
    return {"status": "Online"}

