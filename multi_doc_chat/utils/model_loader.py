import os
import sys
# import json

from dotenv import load_dotenv
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException
from multi_doc_chat.config.config import get_settings


from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

class ModelLoader:
    def __init__(self):
        if os.getenv("ENV", "local").lower() != "production":
            load_dotenv()
            log.info("Running in local mode: .env loaded")
        else:
            log.info("Running in PRODUCTION mode")

        settings = get_settings()
        
        self.gemini_api_key = settings.GEMINI_API_KEY.get_secret_value()
        self.embedding_api_key = settings.EMBEDDING_API_KEY.get_secret_value()
        self.pinecone_api_key = settings.PINECONE_API_KEY.get_secret_value()

        self.config = load_config()
        log.info("YAML config loaded", config_keys = list(self.config.keys()))

    def load_embeddings(self):
        """
        load and return embedding model
        """
        try:
            model_name = self.config["embedding_model"]["model_name"]
            log.info("Loading embedding model", model = model_name)
            return GoogleGenerativeAIEmbeddings(model=model_name,
                                                google_api_key=self.embedding_api_key)

        except Exception as e:
            log.error("Error loading embedding model", error = str(e))
            raise CustomException ("Failed to load embedding model", sys)
        
    def load_llm(self):
        """
        load and return llm model
        """
        llm_block = self.config["llm"]

        llm_config = llm_block
        provider = llm_config.get("provider")
        model_name = llm_config.get("model_name")
        temperature = llm_config.get("temperature", 0.2)
        max_tokens = llm_config.get("max_output_tokens", 2048)

        log.info("Loading LLM", provider = provider, model = model_name)

        try:
            if provider == "google":
                return ChatGoogleGenerativeAI(
                    model = model_name,
                    google_api_key = self.gemini_api_key,
                    temperature = temperature,
                    max_output_tokens = max_tokens
                )

        except Exception as e:
            log.error("Error loading LLM model", error = str(e))
            raise CustomException("Failed to load LLM model", sys)

# if __name__ == "__main__":
#     loader = ModelLoader()

#     embeddings = loader.load_embeddings()
#     llm = loader.load_llm()

#     print("Embedding model loaded:", embeddings)
#     print("LLM loaded:", llm)


       

