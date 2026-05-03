import uuid
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException
from multi_doc_chat.config.config import get_settings
from multi_doc_chat.utils.text_cleaner import clean_extracted_text
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.utils.hash_store import HashStore


class PineconeIngestor:
    """
    Process the doc and upsert it into the pinecone vector database.
    """
    def __init__(self, index_name: Optional[str] = None):
        try:
            self.settings = get_settings()
            self.config = load_config()

            self.index_name = index_name or self.config["pinecone"]["index_name"]

            self.pinecone_index = Pinecone(
                api_key=self.settings.PINECONE_API_KEY.get_secret_value()
            ).Index(self.index_name)

            embedding_cfg = self.config["embedding_model"]
            self.embeddings_model = GoogleGenerativeAIEmbeddings(
                model=embedding_cfg["model_name"],
                output_dimensionality=embedding_cfg["output_dimensionality"],
                google_api_key=self.settings.EMBEDDING_API_KEY.get_secret_value()
            )

            chunking_cfg = self.config.get("chunking", {})
            self.chunk_size = chunking_cfg.get("chunk_size", 1000)
            self.chunk_overlap = chunking_cfg.get("chunk_overlap", 250)

            self.hash_store = HashStore(self.settings.REDIS_URL.get_secret_value())

            log.info("PineconeIngestor initialized", index_name=self.index_name)

        except Exception as e:
            log.error("Failed to initialize Pinecone Ingestion", error=str(e))
            raise CustomException("Ingestor Initialization error", e) from e

    def _load_documents(self, file_paths: List[Path]) -> Tuple[List[Document], List[Path]]:
        docs = []
        skipped = []
        for path in file_paths:
            ext = path.suffix.lower()
            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(str(path))
                elif ext == ".txt":
                    loader = TextLoader(str(path))
                else:
                    log.warning("Unsupported file type, skipping", path=str(path), ext=ext)
                    skipped.append(path)
                    continue

                docs.extend(loader.load())

            except Exception as e:
                log.error("Failed to load file", path=str(path), error=str(e))
                skipped.append(path)

        log.info("Documents loaded into memory", total_pages=len(docs), skipped_count=len(skipped))
        return docs, skipped

    def _chunk_documents(self, docs: List[Document]) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        chunks = splitter.split_documents(docs)
        log.info("Documents split into chunks", chunk_count=len(chunks))
        return chunks

    def _generate_chunk_ids(self, chunks: List[Document], file_hashes: Dict[str, str]) -> List[str]:
        """Deterministic IDs: sha256(file_hash + chunk_index) — idempotent upserts."""
        counter: Dict[str, int] = {}
        ids = []
        for chunk in chunks:
            source = chunk.metadata.get("source", "unknown")
            file_hash = file_hashes.get(source, hashlib.sha256(source.encode()).hexdigest())
            idx = counter.get(source, 0)
            counter[source] = idx + 1
            chunk_id = hashlib.sha256(f"{file_hash}:{idx}".encode()).hexdigest()
            ids.append(chunk_id)
        return ids

    def _upsert_to_pinecone(self, chunks: List[Document], namespace: str, ids: List[str]) -> None:
        try:
            store = PineconeVectorStore(
                index=self.pinecone_index,
                embedding=self.embeddings_model,
                namespace=namespace,
            )
            store.add_documents(chunks, ids=ids)
            log.info("Documents upserted to the vector database", namespace=namespace, index=self.index_name)
        except Exception as e:
            log.error("Failed to upsert documents to Pinecone", namespace=namespace, error=str(e))
            raise CustomException("Pinecone upsert failed", e) from e

    def process_documents(self, file_paths: List[Path], session_id: Optional[str] = None) -> int:
        """
        Main orchestration pipeline. Takes saved files and pushes them to Pinecone. Returns chunk count.
        Skips files whose content has already been ingested (via SHA-256 hash check).
        """
        namespace = session_id or f"session_{uuid.uuid4().hex[:8]}"
        log.info("Starting ingestion pipeline", namespace=namespace, file_count=len(file_paths))

        try:
            # --- Deduplication: filter out already-ingested files ---
            new_files: List[Path] = []
            file_hashes: Dict[str, str] = {}  # {str(path): hash}

            for path in file_paths:
                file_hash = HashStore.hash_file(path)
                if self.hash_store.is_ingested(file_hash):
                    log.info("Skipping already-ingested file", path=str(path), hash=file_hash[:12])
                else:
                    new_files.append(path)
                    file_hashes[str(path)] = file_hash

            if not new_files:
                log.info("All files already ingested, nothing to do", namespace=namespace)
                return 0

            raw_docs, skipped = self._load_documents(new_files)
            if not raw_docs:
                raise ValueError("No readable text could be fetched from the files")

            if skipped:
                log.warning("Some files were skipped during ingestion", skipped=[str(p) for p in skipped])

            for doc in raw_docs:
                doc.page_content = clean_extracted_text(doc.page_content)

            chunks = self._chunk_documents(raw_docs)

            ids = self._generate_chunk_ids(chunks, file_hashes)
            self._upsert_to_pinecone(chunks, namespace, ids)

            # Register hashes only for successfully loaded files
            skipped_strs = {str(p) for p in skipped}
            for path in new_files:
                if str(path) not in skipped_strs:
                    self.hash_store.register(file_hashes[str(path)], path.name, namespace)

            log.info("Ingestion pipeline completed", namespace=namespace, chunk_count=len(chunks))
            return len(chunks)

        except Exception as e:
            log.error("Ingestion pipeline failed", error=str(e), namespace=namespace)
            raise CustomException("Pipeline execution failed", e) from e
