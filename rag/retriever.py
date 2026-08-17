from typing import List, Tuple, Optional
import torch
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
from core.config import CHROMA_DIR, EMBEDDING_MODEL, RERANKER_MODEL, TOP_K, HYBRID_TOP_K
from core.logging import logger


_embedding_model = None
_reranker = None
_chroma_collection = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Embedding model yükleniyor... Cihaz: {device}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=device)
        logger.info("Embedding model yüklendi.")
    return _embedding_model


def get_reranker():
    global _reranker
    if _reranker is None:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Reranker model yükleniyor... Cihaz: {device}")
        try:
            _reranker = CrossEncoder(RERANKER_MODEL, device=device)
            logger.info("Reranker model yüklendi.")
        except Exception as e:
            logger.warning(f"Reranker yüklenemedi: {e}")
            _reranker = None
    return _reranker


def get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is None:
        logger.info("Chroma koleksiyonu başlatılıyor...")
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _chroma_collection = client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("Chroma koleksiyonu hazır.")
    return _chroma_collection


def add_documents_to_vectorstore(doc_id: str, chunks: List[str], metadatas: List[dict]):
    collection = get_chroma_collection()
    model = get_embedding_model()
    logger.info(f"{len(chunks)} parça embedding ve kaydediliyor...")
    embeddings = model.encode(chunks, batch_size=64, show_progress_bar=False).tolist()
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    collection.add(documents=chunks, embeddings=embeddings, metadatas=metadatas, ids=ids)
    logger.info(f"{len(chunks)} parça başarıyla kaydedildi.")


def _bm25_like_search(query: str, documents: List[str], metadatas: List[dict], top_k: int = 20) -> Tuple[List[str], List[dict], List[float]]:
    query_terms = set(query.lower().split())
    scored = []
    for idx, chunk in enumerate(documents):
        text = chunk.lower()
        score = sum(text.count(term) for term in query_terms)
        if score > 0:
            scored.append((score, idx))
    scored.sort(reverse=True)
    
    results = []
    result_meta = []
    result_scores = []
    for score, idx in scored[:top_k]:
        results.append(documents[idx])
        result_meta.append(metadatas[idx])
        result_scores.append(float(score))
    return results, result_meta, result_scores


def query_vectorstore(query: str, top_k: int = TOP_K) -> Tuple[List[str], List[dict]]:
    collection = get_chroma_collection()
    model = get_embedding_model()
    
    query_embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=HYBRID_TOP_K)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        logger.info("Vektör araması sonucu boş.")
        return [], []

    bm25_docs, bm25_meta, bm25_scores = _bm25_like_search(query, documents, metadatas, top_k=top_k * 2)
    seen = set()
    hybrid_docs = []
    hybrid_meta = []
    
    for doc, meta in zip(bm25_docs, bm25_meta):
        key = (doc, meta.get("source", ""))
        if key not in seen:
            seen.add(key)
            hybrid_docs.append(doc)
            hybrid_meta.append(meta)
    
    for doc, meta in zip(documents, metadatas):
        key = (doc, meta.get("source", ""))
        if key not in seen and len(hybrid_docs) < HYBRID_TOP_K:
            seen.add(key)
            hybrid_docs.append(doc)
            hybrid_meta.append(meta)

    reranker = get_reranker()
    if reranker and hybrid_docs:
        try:
            pairs = [[query, doc] for doc in hybrid_docs]
            rerank_scores = reranker.predict(pairs)
            ranked = sorted(zip(rerank_scores, hybrid_docs, hybrid_meta), reverse=True)
            hybrid_docs = [doc for _, doc, _ in ranked[:top_k]]
            hybrid_meta = [meta for _, _, meta in ranked[:top_k]]
            logger.info(f"Reranking tamamlandı. En iyi {top_k} parça seçildi.")
        except Exception as e:
            logger.warning(f"Reranking başarısız: {e}")
            hybrid_docs = hybrid_docs[:top_k]
            hybrid_meta = hybrid_meta[:top_k]
    else:
        hybrid_docs = hybrid_docs[:top_k]
        hybrid_meta = hybrid_meta[:top_k]

    return hybrid_docs, hybrid_meta


def clear_vectorstore():
    global _chroma_collection
    _chroma_collection = None
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(name="documents")
        logger.info("Vektör deposu temizlendi.")
    except Exception:
        pass
