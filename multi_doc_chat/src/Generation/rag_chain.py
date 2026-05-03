from typing import Dict, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from multi_doc_chat.logging import GLOBAL_LOGGER as log
from multi_doc_chat.exception.custom_exception import CustomException
from multi_doc_chat.config.config import get_settings
from multi_doc_chat.utils.config_loader import load_config
from multi_doc_chat.src.Retrieval_engine.retriever import PineconeRetriever
from multi_doc_chat.utils.chat_history import ChatHistoryManager


_SYSTEM_TEMPLATE = (
    "You are a helpful AI assistant. Answer the user's question using ONLY the "
    "document context provided below.\n"
    "If the answer is not found in the context, clearly state that the information "
    "is not available in the uploaded documents.\n\n"
    "Context:\n{context}"
)


class RAGChain:
    """
    Orchestrates retrieval → history loading → LLM generation → history saving.
    """

    def __init__(self):
        try:
            self.settings = get_settings()
            self.config = load_config()

            llm_cfg = self.config["llm"]["google"]
            self.llm = ChatGoogleGenerativeAI(
                model=llm_cfg["model_name"],
                google_api_key=self.settings.GEMINI_API_KEY.get_secret_value(),
                temperature=llm_cfg["temperature"],
                max_output_tokens=llm_cfg["max_output_token"],
            )

            self.retriever = PineconeRetriever()
            self.history_manager = ChatHistoryManager(
                mongodb_url=self.settings.MONGODB_URL.get_secret_value(),
                db_name=self.config["mongodb"]["db_name"],
            )

            log.info("RAGChain initialized")

        except Exception as e:
            log.error("Failed to initialize RAGChain", error=str(e))
            raise CustomException("RAGChain initialization failed", e) from e

    async def generate(self, query: str, session_id: str, user_id: str) -> Dict:
        try:
            docs = self.retriever.retrieve(query, user_id)
            context = "\n\n".join(doc.page_content for doc in docs)

            history_records = await self.history_manager.get_history(session_id)
            history_messages: List = []
            for record in history_records:
                if record["role"] == "human":
                    history_messages.append(HumanMessage(content=record["content"]))
                else:
                    history_messages.append(AIMessage(content=record["content"]))

            messages = [SystemMessage(content=_SYSTEM_TEMPLATE.format(context=context))]
            messages.extend(history_messages)
            messages.append(HumanMessage(content=query))

            response = self.llm.invoke(messages)
            answer = response.content

            await self.history_manager.save_exchange(session_id, query, answer)

            sources = list({
                doc.metadata.get("source", "unknown")
                for doc in docs
                if doc.metadata
            })

            log.info("Generation complete", session_id=session_id, user_id=user_id)
            return {"answer": answer, "sources": sources}

        except Exception as e:
            log.error("Generation failed", session_id=session_id, user_id=user_id, error=str(e))
            raise CustomException("Generation failed", e) from e
