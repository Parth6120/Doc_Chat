from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.utils.file_manager import save_single_stream 

doc_router = APIRouter()

SUPPORTED_EXTENSION = {".pdf", ".docx", ".txt", ".csv", ".db", ".sqlite"}

@doc_router.post("/upload_docs/")
async def upload_document(file: UploadFile = File(...)):
    """
    Validates the file and passes the clean stream to the core logic
    """
    ext = Path(file.filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSION:
        log.warning("Rejected unsupported file type", filename = file.filename)
        raise HTTPException(status_code=400, detail=f"unsupported file type")
    
    target_dir = Path("./uploaded_docs")

    try:
        saved_path = save_single_stream(
            file_stream = file.file,
            original_filename = file.filename,
            target_dir = target_dir
        )
        return {"status": "success", "file_path": str(saved_path)}
        
    except Exception as e:
        log.error("Failed to save document stream", error = str(e))
        raise HTTPException(status_code=500, detail = "Failed to save the document")
