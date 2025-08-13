import logging
import os
import openai
import chromadb
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class VectorContextService:
    def __init__(self, db_path: str):
        logger.info(f"Initializing VectorContextService with DB path: {db_path}")
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="aura_project_context",
            metadata={"hnsw:space": "cosine"}
        )
        # We will get the API key from Railway's environment variables
        self.openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.info("Vector database connected and OpenAI client configured.")

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Helper function to call OpenAI's embedding API
        texts = [text.replace("\n", " ") for text in texts]
        try:
            response = await self.openai_client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"  # This is a powerful and cost-effective model
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Failed to get embeddings from OpenAI: {e}")
            return []

    async def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]]):
        if not documents:
            logger.warning("add_documents called with no documents.")
            return

        logger.info(f"Requesting embeddings for {len(documents)} documents from OpenAI...")
        embeddings = await self._get_embeddings(documents)

        if not embeddings:
            logger.error("Received no embeddings from OpenAI. Aborting add.")
            return

        ids = [f"{meta['file_path']}-{meta.get('node_type', 'file')}-{meta.get('node_name', '')}" for meta in metadatas]

        self.collection.upsert(  # Use upsert to avoid duplicates
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Successfully added/updated documents. Collection now has {self.collection.count()} items.")

    async def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        if self.collection.count() == 0:
            return []

        logger.info(f"Querying vector store for: '{query_text[:50]}...'")
        query_embedding = (await self._get_embeddings([query_text]))[0]

        if not query_embedding:
            return []

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