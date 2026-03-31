import os
import time
import uuid
import hashlib
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from multi_doc_chat.utils.model_loader import ModelLoader
from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException
from multi_doc_chat.config.config import get_settings
from multi_doc_chat.utils.text_cleaner import clean_extracted_text

class PineconeIngestor:
    """
    Process the doc and upsert it into the pinecone vector database.
    """
    def __init__(self, index_name: str = "Multi-Doc-Chat"):
        try:
            self.settings = get_settings()
            self.index_name = index_name

            # API keys
            self.embedding_api_key = self.settings.EMBEDDING_API_KEY.get_secret_value()
            self.pinecone_api_key = self.settings.PINECONE_API_KEY.get_secret_value()

            # Models
            self.embeddings_model = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001", 
                google_api_key=self.settings.EMBEDDING_API_KEY.get_secret_value()
            )

            # Chunking
            self.chunk_size = 1000
            self.chunk_overlap = 250

            log.info("PineconeIngestor initiallized", index_name = self.index_name)

        except Exception as e:
            log.error("Failed to initialize Pinecone Ingestion", error = str(e))
            raise CustomException("Ingestor Initialization error", e) from e
        
    def _load_documents(self,file_paths: List[Path]) -> List[Document]:
        docs = []
        for path in file_paths:
            ext = path.suffix.lower()
            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(str(path))
                elif ext == ".txt":
                    loader = TextLoader(str(path))
                else:
                    log.warning(f"Unsupported ext {ext}")
                    continue
                
                docs.extend(loader.load())

            except Exception as e:
                log.error(f"Failed to load {path.prefix} file", path = str(path), error = str(e))
                continue
        log.info("Documents loaded into memory", total_pages = len(docs))
        return docs
    
    def _chunk_documents(self,docs: List[Document]) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size = self.chunk_size,
            chunk_overlap = self.chunk_overlap
        )

        chunks = splitter.split_documents(docs)
        log.info("Documents split into chunks", chunk_count = len(chunks))
        return chunks

    def _upsert_to_pinecone(self, chunks: List[Document], namespace: str) -> None:
        PineconeVectorStore.from_documents(
            documents=chunks,
            embedding=self.embeddings_model,
            index_name = self.index_name,
            namespace = namespace,
            pinecone_api_key = self.pinecone_api_key
        )
        log.info("Documents upserted to the vector database", namespace = namespace, index = self.index_name)

    def process_documents(self, file_paths: List[Path], session_id: Optional[str] = None) -> int:
        """
        The main orchestration pipeline. Takes Saved files and pushes them to Pinecone. Return the number of chunks.
        """
        namespace = session_id or f"session_{uuid.uuid4().hex[:8]}"
        log.info("Starting ingestion pipeline", namespace = namespace, file_count = len(file_paths))

        try:
            # load document
            raw_docs = self._load_documents(file_paths)
            if not raw_docs:
                raise ValueError("No readable text could be fetched from the files")
            
            # cleaning the text
            for doc in raw_docs:
                doc.page_content = clean_extracted_text(doc.page_content)

            # Chunking the docs
            chunks = self._chunk_documents(raw_docs)
            
            # Upsert to Pinecone
            self._upsert_to_pinecone(chunks, namespace)

            log.info("Ingestion Pipeline completed", namespace = namespace, chunk_count = len(chunks))
            return len(chunks)

        except Exception as e:
            log.error("Ingestion pipeline failed", error = str(e), namespace = namespace)
            raise CustomException("Pipeline execution failed", e) from e
        