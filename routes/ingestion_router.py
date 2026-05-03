from pathlib import Path
from fastapi import HTTPException, UploadFile, File, APIRouter, Query

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.utils.file_manager import save_single_stream
from multi_doc_chat.src.document_ingestion.data_ingestion import PineconeIngestor

ingestion_router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}

@ingestion_router.post("/pinecone/ingest/")
async def ingest_docs_to_pinecone(
    file: UploadFile = File(...),
    user_id: str = Query(..., description="Unique user identifier"),
):
    ext = Path(file.filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        log.warning("Rejected unsupported file type", filename=file.filename)
        raise HTTPException(status_code=400, detail="Unsupported file type")

    target_dir = Path("./uploaded_docs")
    saved_path = None

    try:
        saved_path = save_single_stream(
            file_stream=file.file,
            original_filename=file.filename,
            target_dir=target_dir,
        )

        ingestor = PineconeIngestor()
        chunk_count = ingestor.process_documents(file_paths=[saved_path], user_id=user_id)

        return {
            "status": "success",
            "user_id": user_id,
            "filename": file.filename,
            "chunks_vectorized": chunk_count,
        }

    except Exception as e:
        log.error("Ingestion endpoint failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to ingest documents.")

    finally:
        if saved_path and saved_path.exists():
            try:
                saved_path.unlink()
                log.debug("Temporary file removed", filename=saved_path.name)
            except Exception as e:
                log.error("Failed to delete temporary file", filename=saved_path.name, error=str(e))