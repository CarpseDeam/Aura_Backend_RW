# VectorContextService.py
import logging
import openai
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.db import crud
from pathlib import Path
import ast
from .chunking_service import ChunkingService

logger = logging.getLogger(__name__)


class VectorContextService:
    def __init__(self, user_db_session: Session, user_id: int):
        logger.info(f"Initializing VectorContextService for user {user_id}")
        self.client = None
        self.collection = None
        self.project_root: Path | None = None
        self.db_session = user_db_session
        self.user_id = user_id
        self.openai_client = None

    def load_for_project(self, project_path: Path):
        """
        Loads or creates the vector database for a specific project.
        This version has been modified to ALWAYS use a local, file-based
        persistent database within the backend's own volume. This eliminates
        the need for a separate ChromaDB service and removes inter-service
        networking issues.
        """
        self.project_root = project_path

        # The RAG database will live inside the user's project directory,
        # which is already on the persistent volume.
        rag_db_path = project_path / ".rag_db"

        logger.info(f"Using local file-based vector database for project at: {rag_db_path}")
        self.client = chromadb.PersistentClient(
            path=str(rag_db_path),
            settings=Settings(anonymized_telemetry=False)
        )

        # Collection name is still unique per project.
        collection_name = f"aura_project_{self.user_id}_{project_path.name.replace(' ', '_').replace('.', '_')}"

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Vector database loaded. Collection '{self.collection.name}' has {self.collection.count()} items.")


    def _ensure_project_loaded(self):
        """Checks if a project's vector DB is loaded before performing an operation."""
        if not self.collection or not self.client or not self.project_root:
            raise RuntimeError("VectorContextService has not been loaded for a project. Call load_for_project() first.")

    def _initialize_openai_client(self):
        self._ensure_project_loaded()
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
        self._ensure_project_loaded()
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
        self._ensure_project_loaded()
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

    async def reindex_file(self, file_path: Path, content: str):
        """Deletes old chunks for a file and indexes the new content."""
        self._ensure_project_loaded()
        relative_path_str = str(file_path.relative_to(self.project_root))

        logger.info(f"Re-indexing file: {relative_path_str}")
        try:
            self.collection.delete(where={"file_path": relative_path_str})
            logger.info(f"Deleted old vector chunks for file. Collection count: {self.collection.count()}")
        except Exception as e:
            logger.error(f"Error deleting chunks from ChromaDB for {relative_path_str}: {e}")

        documents = []
        metadatas = []
        try:
            tree = ast.parse(content)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    source_code = ast.unparse(node)
                    node_type = "function" if isinstance(node, ast.FunctionDef) else "class"
                    documents.append(source_code)
                    metadatas.append({
                        "file_path": relative_path_str, "node_type": node_type, "node_name": node.name,
                    })
        except SyntaxError:
            logger.warning(f"File {relative_path_str} is not valid Python. Indexing as plain text.")
            chunker = ChunkingService()
            text_chunks = chunker.chunk_document(content, str(file_path))
            for i, chunk in enumerate(text_chunks):
                documents.append(chunk['content'])
                metadatas.append({
                    "file_path": relative_path_str, "node_type": "text_chunk", "node_name": f"chunk_{i}",
                })
        except Exception as e:
            logger.error(f"Failed to parse file {relative_path_str} with AST: {e}")
            return

        if not documents:
            logger.info(f"No functions or classes found in {relative_path_str}. Nothing new to index.")
            return

        await self.add_documents(documents, metadatas)
        logger.info(f"Successfully re-indexed {len(documents)} chunks for file: {relative_path_str}")

    # --- NEW METHOD FOR FULL PROJECT SCAN ---
    async def reindex_entire_project(self):
        """Scans the entire project directory, indexing all compatible files."""
        self._ensure_project_loaded()
        logger.info(f"Starting full re-index of project: {self.project_root}")

        self.client.delete_collection(name=self.collection.name)
        self.collection = self.client.get_or_create_collection(name=self.collection.name)
        logger.info("Cleared existing collection for a full re-index.")

        ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', 'rag_db', 'node_modules'}

        all_files = [p for p in self.project_root.rglob('*') if
                     p.is_file() and not any(part in ignore_dirs for part in p.relative_to(self.project_root).parts)]

        for file_path in all_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                await self.reindex_file(file_path, content)
            except Exception as e:
                logger.warning(f"Could not read or process file {file_path} during full re-index: {e}")

        logger.info(f"Full project re-index complete. Collection now has {self.collection.count()} items.")