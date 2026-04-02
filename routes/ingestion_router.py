import os
from pathlib import Path
from typing import List
from fastapi import HTTPException, UploadFile, File, APIRouter

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.utils.file_manager import save_single_stream

from multi_doc_chat.src.document_ingestion.data_ingestion import PineconeIngestor

ingestion_router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}

@ingestion_router.post("/pinecone/ingest/")
async def ingest_docs_to_pinecone(file: UploadFile = File(...)):
    """
    Receives a batch of files, save them temporarily, proecess them, chunk them, and save it to vector db.
    """
    ext = Path(file.filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        log.warning("Rejected unsupported file type", filename = file.filename)
        raise HTTPException(status_code=400, detail=f"unsupported file type")
    
    target_dir = Path("./uploaded_docs")

    try:
        saved_path = save_single_stream(
            file_stream = file.file,
            original_filename = file.filename,
            target_dir = target_dir
        )
        # return {"status": "success", "file_path": str(saved_path)}

       
        ingestor = PineconeIngestor()

        chunk_counts = ingestor.process_documents(file_paths = [saved_path])

        return {
            "status": "Success",
            "message": "Documents successfully processed and stored in vector db",
            "chunk_vectorized": chunk_counts,
        }
    
    except Exception as e:
        log.error("Ingestion endpoint failed", error = str(e))
        raise HTTPException(status_code=500, detail="Failed to ingest documents.")
    
    finally:
        # clean the single temporary uploaded file
        if saved_path and saved_path.exists():
            try:
                saved_path.unlink()
                log.debug(f"Temporary uploaded file is removed: {saved_path.name}")
            except Exception as e:
                log.error(f"Failed to delete the file: {saved_path.name}", error = str(e))