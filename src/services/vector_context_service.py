# src/services/vector_context_service.py
import logging
import openai
import chromadb
from chromadb.config import Settings  # <-- IMPORT THE SETTINGS CLASS
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.db import crud

logger = logging.getLogger(__name__)


class VectorContextService:
    def __init__(self, db_path: str, user_db_session: Session, user_id: int):
        logger.info(f"Initializing VectorContextService with DB path: {db_path}")

        # --- THE FIX: Disable telemetry to prevent log spam and errors ---
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name="aura_project_context",
            metadata={"hnsw:space": "cosine"}
        )
        self.db_session = user_db_session
        self.user_id = user_id
        self.openai_client = None  # Will be initialized on demand

    def _initialize_openai_client(self):
        if self.openai_client:
            return True
        api_key = crud.get_decrypted_key_for_provider(self.db_session, self.user_id, "openai")
        if not api_key:
            logger.error(f"OpenAI API key not found for user {self.user_id}. Cannot create embeddings.")
            return False
        self.openai_client = openai.AsyncOpenAI(api_key=api_key)
        return True

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not self._initialize_openai_client():
            return []

        texts = [text.replace("\n", " ") for text in texts]
        try:
            response = await self.openai_client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Failed to get embeddings from OpenAI: {e}")
            return []

    async def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]]):
        if not documents:
            logger.warning("add_documents called with no documents.")
            return

        embeddings = await self._get_embeddings(documents)

        if not embeddings:
            logger.error("Received no embeddings from OpenAI. Aborting add.")
            return

        ids = [f"{meta['file_path']}-{meta.get('node_type', 'file')}-{meta.get('node_name', '')}" for meta in metadatas]

        self.collection.upsert(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Successfully added/updated documents. Collection now has {self.collection.count()} items.")

    async def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        if self.collection.count() == 0:
            return []

        query_embedding_list = await self._get_embeddings([query_text])
        if not query_embedding_list:
            return []

        query_embedding = query_embedding_list[0]

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        retrieved_docs = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                retrieved_docs.append({
                    "document": doc,
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
        return retrieved_docs