from fastapi import FastAPI
import uvicorn

from routes.ingestion_router import ingestion_router

app = FastAPI(
    title = "Multi-Doc-Chat"
)

app.include_router(
    ingestion_router,
    prefix = "/documents",
    tags = ["Document Management"]
)

@app.get("/")
def server_status():
    return {"status": "Online"}

