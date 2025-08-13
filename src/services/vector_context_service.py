# services/vector_context_service.py
"""
Manages the vector database for project-wide context (RAG).
"""
import logging
import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# The model for generating embeddings. This runs locally.
# The first time this is run, it will download the model (a few hundred MB).
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'


class VectorContextService:
    """
    Handles the creation, storage, and retrieval of vector embeddings for
    code snippets and other project context.
    """

    def __init__(self, db_path: str):
        try:
            logger.info(f"Initializing VectorContextService with DB path: {db_path}")
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

            # Set up the ChromaDB client and collection for the specific project path
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_or_create_collection(
                name="aura_project_context",
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            logger.info(f"Vector database connected/created at '{db_path}'.")
            logger.info(f"Current collection contains {self.collection.count()} documents.")

        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformer or ChromaDB: {e}", exc_info=True)
            raise

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]]):
        """
        Adds or updates documents in the vector store.

        Args:
            documents: A list of text chunks (e.g., function code).
            metadatas: A list of dictionaries with info about each chunk (e.g., file path, type).
        """
        if not documents:
            logger.warning("add_documents called with no documents to add.")
            return

        logger.info(f"Generating embeddings for {len(documents)} new documents...")
        embeddings = self.embedding_model.encode(documents, show_progress_bar=True)

        # Generate unique IDs based on metadata to allow for upserting
        ids = [f"{meta['file_path']}-{meta.get('node_type', 'file')}-{meta.get('node_name', '')}" for meta in metadatas]

        logger.info(f"Adding {len(documents)} documents to the vector collection...")
        self.collection.add(
            embeddings=embeddings.tolist(),  # Convert numpy array to list
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Successfully added documents. Collection now has {self.collection.count()} items.")

    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries the vector store for relevant documents.

        Args:
            query_text: The user's prompt or question.
            n_results: The number of results to return.

        Returns:
            A list of the most relevant documents and their metadata.
        """
        if self.collection.count() == 0:
            logger.warning("Query attempted on an empty collection.")
            return []

        logger.info(f"Querying vector store for text: '{query_text[:50]}...'")
        query_embedding = self.embedding_model.encode(query_text).tolist()

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        # Unpack the results into a cleaner format
        retrieved_docs = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                retrieved_docs.append({
                    "document": doc,
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })

        logger.info(f"Retrieved {len(retrieved_docs)} documents from vector store.")
        return retrieved_docs