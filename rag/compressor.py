from typing import List
from sentence_transformers import CrossEncoder
from core.config import TOP_K, DEBUG, RERANKER_MODEL
from core.logging import logger


class ContextualCompressor:
    def __init__(self):
        self.reranker = None

    def _get_reranker(self):
        if self.reranker is None:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.reranker = CrossEncoder(RERANKER_MODEL, device=device)
        return self.reranker

    def compress(self, query: str, chunks: List[str], metadatas: List[dict], top_k: int = TOP_K) -> tuple[list[str], list[dict]]:
        if not chunks:
            return [], []
        
        reranker = self._get_reranker()
        if not reranker:
            return chunks[:top_k], metadatas[:top_k]

        try:
            pairs = [[query, chunk] for chunk in chunks]
            scores = reranker.predict(pairs)
            ranked = sorted(zip(scores, chunks, metadatas), reverse=True)
            compressed = [doc for _, doc, _ in ranked[:top_k]]
            compressed_meta = [meta for _, _, meta in ranked[:top_k]]
            logger.info(f"Bağlamsal sıkıştırma tamamlandı. {len(chunks)} -> {len(compressed)} parça.")
            return compressed, compressed_meta
        except Exception as e:
            logger.warning(f"Bağlamsal sıkıştırma başarısız: {e}")
            return chunks[:top_k], metadatas[:top_k]

compressor = ContextualCompressor()
