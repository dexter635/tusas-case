import uuid
import os
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from core.config import DATA_DIR
from core.logging import logger
from rag.chunker import chunk_text
from rag.retriever import add_documents_to_vectorstore, query_vectorstore, clear_vectorstore
from rag.compressor import compressor


class Document:
    def __init__(self, file_id: str, filename: str, text: str, chunks: List[str], metadata: Dict):
        self.file_id = file_id
        self.filename = filename
        self.text = text
        self.chunks = chunks
        self.metadata = metadata
        self.created_at = datetime.now()
        self.chunk_count = len(chunks)

    def to_dict(self):
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "file_hash": self.metadata.get("file_hash"),
        }


class DocumentStore:
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

    def add_document(self, filename: str, text: str, metadata: Optional[Dict] = None) -> Document:
        file_id = str(uuid.uuid4())
        chunks = chunk_text(text)
        metadata = metadata or {"source": filename}
        doc = Document(file_id=file_id, filename=filename, text=text, chunks=chunks, metadata=metadata)
        self.documents[file_id] = doc
        add_documents_to_vectorstore(file_id, chunks, [metadata] * len(chunks))
        logger.info(f"Belge eklendi: {filename} ({len(chunks)} parça)")
        return doc

    def get_document(self, file_id: str) -> Optional[Document]:
        return self.documents.get(file_id)

    def list_documents(self) -> List[Dict]:
        return [doc.to_dict() for doc in self.documents.values()]

    def clear(self):
        self.documents.clear()
        clear_vectorstore()
        logger.info("Tüm belgeler temizlendi.")


class RAGPipeline:
    def __init__(self, doc_store: DocumentStore):
        self.doc_store = doc_store

    def query(self, question: str, top_k: int = 4) -> Dict:
        logger.info(f"Soru alındı: {question[:100]}...")
        
        chunks, metadatas = query_vectorstore(question, top_k=top_k)
        if not chunks:
            return {
                "answer": "Yüklenmiş belge bulunamadı veya ilgili içerik bulunamadı.",
                "sources": [],
                "chunks": [],
            }

        sources = [m.get("source", "Bilinmiyor") for m in metadatas]
        
        compressed_chunks, compressed_meta = compressor.compress(question, chunks, metadatas, top_k=top_k)
        compressed_sources = [m.get("source", "Bilinmiyor") for m in compressed_meta]
        
        from rag.llm import generate_answer
        answer = generate_answer(question, compressed_chunks, compressed_sources)
        
        logger.info(f"Yanıt üretildi. Kaynak sayısı: {len(set(sources))}")
        
        return {
            "answer": answer,
            "sources": list(set(sources)),
            "chunks": compressed_chunks,
        }

    def query_stream(self, question: str, top_k: int = 4):
        logger.info(f"Streaming soru alındı: {question[:100]}...")
        
        chunks, metadatas = query_vectorstore(question, top_k=top_k)
        if not chunks:
            yield "Yüklenmiş belge bulunamadı veya ilgili içerik bulunamadı."
            return

        sources = [m.get("source", "Bilinmiyor") for m in metadatas]
        compressed_chunks, compressed_meta = compressor.compress(question, chunks, metadatas, top_k=top_k)
        compressed_sources = [m.get("source", "Bilinmiyor") for m in compressed_meta]
        
        from rag.llm import generate_answer_stream
        yield from generate_answer_stream(question, compressed_chunks, compressed_sources)

doc_store = DocumentStore()
rag_pipeline = RAGPipeline(doc_store)
