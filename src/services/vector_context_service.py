# src/services/vector_context_service.py
import logging
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.db import crud
from pathlib import Path
import ast
from .chunking_service import ChunkingService

logger = logging.getLogger(__name__)


class VectorContextService:
    def __init__(self):
        logger.info(f"Initializing VectorContextService")
        self.client = None
        self.collection = None
        self.project_root: Path | None = None
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        logger.info("Using Hugging Face SentenceTransformer for embeddings.")

    def load_for_project(self, project_path: Path, user_id: int):
        """
        Loads or creates the vector database for a specific project.
        The user_id is now passed in at load time to ensure the correct context.
        """
        self.project_root = project_path
        rag_db_path = project_path / ".rag_db"

        logger.info(f"Using local file-based vector database for project at: {rag_db_path}")
        self.client = chromadb.PersistentClient(
            path=str(rag_db_path),
            settings=Settings(anonymized_telemetry=False)
        )

        collection_name = f"aura_project_{user_id}_{project_path.name.replace(' ', '_').replace('.', '_')}"

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Vector database loaded. Collection '{self.collection.name}' has {self.collection.count()} items.")

    def _ensure_project_loaded(self):
        if not self.collection or not self.client or not self.project_root:
            raise RuntimeError("VectorContextService has not been loaded for a project. Call load_for_project() first.")

    async def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]]):
        self._ensure_project_loaded()
        if not documents:
            logger.warning("add_documents called with no documents.")
            return

        ids = [f"{meta['file_path']}-{meta.get('node_type', 'file')}-{meta.get('node_name', '')}" for meta in metadatas]

        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Successfully added/updated documents. Collection now has {self.collection.count()} items.")

    async def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        self._ensure_project_loaded()
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query_text],
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

    async def reindex_entire_project(self):
        self._ensure_project_loaded()
        logger.info(f"Starting full re-index of project: {self.project_root}")

        try:
            self.client.delete_collection(name=self.collection.name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection.name,
                embedding_function=self.embedding_function
            )
            logger.info("Cleared existing collection for a full re-index.")
        except Exception:
            logger.info("Could not delete collection (it may not exist). Proceeding.")

        ignore_dirs = {'.git', '.venv', 'venv', '__pycache__', '.rag_db', 'node_modules'}
        all_files = [p for p in self.project_root.rglob('*') if
                     p.is_file() and not any(part in ignore_dirs for part in p.relative_to(self.project_root).parts)]

        for file_path in all_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                await self.reindex_file(file_path, content)
            except Exception as e:
                logger.warning(f"Could not read or process file {file_path} during full re-index: {e}")

        logger.info(f"Full project re-index complete. Collection now has {self.collection.count()} items.")
