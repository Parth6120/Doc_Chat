from fastapi import FastAPI
import uvicorn

from routes.document_router import doc_router

app = FastAPI(
    title = "Multi-Doc-Chat"
)

app.include_router(
    doc_router,
    prefix = "/documents",
    tags = ["Document Management"]
)

@app.get("/")
def server_status():
    return {"status": "Online"}

