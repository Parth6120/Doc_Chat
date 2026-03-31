import re
import uuid
import shutil

from pathlib import Path
from typing import Iterable, List, BinaryIO

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException



def save_single_stream(file_stream: BinaryIO, original_filename: str, target_dir: Path) -> Path:
    """
    Core Business Logic: Take a raw byte stream and saves it to disk in memory-safe chunks.
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(original_filename).suffix.lower()
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_',Path(original_filename).stem).lower()

        fname = f"{safe_name}_{uuid.uuid4().hex[:6]}{ext}"
        out_path = target_dir/fname

        with open(out_path, "wb") as disk_buffer:
            shutil.copyfileobj(file_stream, disk_buffer)

        log.info("file streamed and saved successfully", saved_as=str(out_path))
        return out_path

    except Exception as e:
        log.error("Failed to stream file to disk", error = str(e), filename = original_filename)
        raise CustomException("File save failed", e) from e
