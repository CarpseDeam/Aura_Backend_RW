import re
from pathlib import Path
from typing import List, Dict, Any


class ChunkingService:
    """
    Smart chunking service for breaking documents into optimal pieces for RAG.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        print("[ChunkingService] Initialized.")

    def chunk_document(self, content: str, file_path_str: str) -> List[Dict[str, Any]]:
        if not content or not content.strip():
            return []
        file_path = Path(file_path_str)
        chunks = self._chunk_generic_text(content, file_path)
        print(f"[ChunkingService] Chunked '{file_path.name}' into {len(chunks)} pieces.")
        return chunks

    def _get_unique_file_prefix(self, file_path: Path) -> str:
        relevant_parts = file_path.parts[-4:]
        sanitized_path = "_".join(relevant_parts)
        return sanitized_path.replace(file_path.suffix, '').replace('.', '_')

    def _chunk_generic_text(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        chunks = []
        file_prefix = self._get_unique_file_prefix(file_path)
        text_chunks = self._split_text_by_size(content)
        for i, chunk_text in enumerate(text_chunks):
            chunks.append(self._create_chunk(
                chunk_text,
                chunk_id=f"{file_prefix}_generic_{i}",
                file_path=file_path
            ))
        return chunks

    def _split_text_by_size(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap
        return chunks

    def _create_chunk(self, content: str, chunk_id: str, file_path: Path) -> Dict[str, Any]:
        return {
            'id': chunk_id,
            'content': content.strip(),
            'metadata': {
                'source': file_path.name,
                'full_path': str(file_path)
            }
        }