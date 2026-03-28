from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from functools import lru_cache
from typing import Optional

from multi_doc_chat.logging import GLOBAL_LOGGER as log

class ApiSettings(BaseSettings):
    GEMINI_API_KEY : SecretStr
    PINECONE_API_KEY : SecretStr
    EMBEDDING_API_KEY : SecretStr

    model_config = SettingsConfigDict(
        env_file= '.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

@lru_cache()
def get_settings() -> ApiSettings:
    log.info("Loading API settings from environment ...")
    return ApiSettings()