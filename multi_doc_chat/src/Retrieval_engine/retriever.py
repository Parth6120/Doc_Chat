from typing import List

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException
from multi_doc_chat.config.config import get_settings
from multi_doc_chat.utils.config_loader import load_config


class PineconeRetriever:
    """
    Retrieves relevant document chunks from Pinecone for a given query and session namespace.
    """

    def __init__(self):
        try:
            self.settings = get_settings()
            self.config = load_config()

            embedding_cfg = self.config["embedding_model"]
            self.embeddings_model = GoogleGenerativeAIEmbeddings(
                model=embedding_cfg["model_name"],
                output_dimensionality=embedding_cfg["output_dimensionality"],
                google_api_key=self.settings.EMBEDDING_API_KEY.get_secret_value(),
            )

            retriever_cfg = self.config["retriever"]
            self.search_type = retriever_cfg["search_type"]
            self.top_k = retriever_cfg["top_k"]
            self.fetch_k = retriever_cfg["fetch_k"]
            self.lambda_mult = retriever_cfg["lambda_mult"]

            index_name = self.config["pinecone"]["index_name"]
            self.pinecone_index = Pinecone(
                api_key=self.settings.PINECONE_API_KEY.get_secret_value()
            ).Index(index_name)

            log.info("PineconeRetriever initialized", search_type=self.search_type, top_k=self.top_k)

        except Exception as e:
            log.error("Failed to initialize PineconeRetriever", error=str(e))
            raise CustomException("Retriever initialization failed", e) from e

    def retrieve(self, query: str, user_id: str) -> List[Document]:
        try:
            store = PineconeVectorStore(
                index=self.pinecone_index,
                embedding=self.embeddings_model,
                namespace=user_id,
            )

            if self.search_type == "mmr":
                docs = store.max_marginal_relevance_search(
                    query,
                    k=self.top_k,
                    fetch_k=self.fetch_k,
                    lambda_mult=self.lambda_mult,
                )
            else:
                docs = store.similarity_search(query, k=self.top_k)

            log.info("Retrieval complete", query_preview=query[:60], user_id=user_id, results=len(docs))
            return docs

        except Exception as e:
            log.error("Retrieval failed", user_id=user_id, error=str(e))
            raise CustomException("Retrieval failed", e) from e
