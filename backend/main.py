import sys
from pathlib import Path
import hashlib
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import time
import uuid
import os
import json

from core.config import APP_NAME, APP_VERSION, DATA_DIR, CHROMA_DIR, TOP_K
from core.logging import logger
from rag.pipeline import rag_pipeline, doc_store
from rag.retriever import query_vectorstore
from rag.chunker import chunk_text
from utils.document_processor import extract_text_from_file

app = FastAPI(title=APP_NAME, version=APP_VERSION)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).resolve().parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


def _file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _clear_directory_contents(path: str):
    p = Path(path)
    if not p.exists():
        return
    for item in p.iterdir():
        if item.is_dir():
            import shutil
            shutil.rmtree(item)
        else:
            item.unlink()


@app.on_event("startup")
async def startup_cleanup():
    _clear_directory_contents(DATA_DIR)
    _clear_directory_contents(CHROMA_DIR)
    logger.info("Başlangıç: data/ ve chroma_db/ klasörleri temizlendi.")


@app.on_event("shutdown")
async def shutdown_cleanup():
    _clear_directory_contents(DATA_DIR)
    _clear_directory_contents(CHROMA_DIR)
    logger.info("Kapatma: data/ ve chroma_db/ klasörleri temizlendi.")


@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}


@app.get("/", response_class=HTMLResponse)
async def root():
    index_file = frontend_path / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return HTMLResponse("<h1>TUSAŞ Belge Analiz Sistemi</h1><p>Frontend bulunamadı.</p>")


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    start = time.time()
    logger.info(f"Yükleme başladı: {file.filename}")
    
    try:
        temp_path = os.path.join(DATA_DIR, f"temp_{uuid.uuid4()}_{file.filename}")
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        file_hash = _file_hash(temp_path)
        existing_docs = doc_store.list_documents()
        for doc in existing_docs:
            if doc.get("file_hash") == file_hash:
                os.remove(temp_path)
                logger.info(f"Cache hit: {file.filename} zaten mevcut.")
                return {
                    "filename": doc["filename"],
                    "file_id": doc["file_id"],
                    "chunk_count": doc["chunk_count"],
                    "duration": 0,
                    "status": "cache_hit",
                }
        
        text = extract_text_from_file(temp_path)
        if not text.strip():
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail="Belgeden metin çıkarılamadı.")
        
        final_path = os.path.join(DATA_DIR, f"{uuid.uuid4()}_{file.filename}")
        os.rename(temp_path, final_path)
        
        metadata = {"source": file.filename, "file_hash": file_hash}
        doc = doc_store.add_document(file.filename, text, metadata=metadata)
        duration = time.time() - start
        logger.info(f"Yükleme tamamlandı: {file.filename} ({duration:.2f}s)")
        
        return {
            "filename": doc.filename,
            "file_id": doc.file_id,
            "chunk_count": doc.chunk_count,
            "duration": round(duration, 2),
            "status": "uploaded",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yükleme hatası: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents():
    return {"documents": doc_store.list_documents()}


@app.delete("/api/documents/{file_id}")
async def delete_document(file_id: str):
    try:
        doc = doc_store.get_document(file_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Belge bulunamadı.")

        doc_store.documents.pop(file_id, None)
        from rag.retriever import clear_vectorstore, add_documents_to_vectorstore
        clear_vectorstore()

        for remaining_doc in doc_store.documents.values():
            add_documents_to_vectorstore(
                remaining_doc.file_id,
                remaining_doc.chunks,
                [remaining_doc.metadata] * len(remaining_doc.chunks),
            )

        logger.info(f"Belge silindi: {file_id}")
        return {"status": "deleted", "file_id": file_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Silme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents")
async def clear_documents():
    doc_store.clear()
    return {"status": "cleared"}


@app.post("/api/query")
async def query(request: dict):
    start = time.time()
    question = request.get("question", "").strip()
    top_k = int(request.get("top_k", TOP_K))
    selected_docs = request.get("selected_docs", [])
    
    if not question:
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")
    
    try:
        if selected_docs:
            from rag.retriever import get_chroma_collection, get_embedding_model
            collection = get_chroma_collection()
            model = get_embedding_model()
            where_filter = {"source": {"$in": selected_docs}} if selected_docs else None
            results = collection.query(
                query_embeddings=model.encode([question]).tolist(),
                n_results=top_k * 3,
                where=where_filter
            )
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            
            if documents:
                from rag.compressor import compressor
                compressed_chunks, compressed_meta = compressor.compress(question, documents, metadatas, top_k=top_k)
                compressed_sources = [m.get("source", "Bilinmiyor") for m in compressed_meta]
                from rag.llm import generate_answer
                answer = generate_answer(question, compressed_chunks, compressed_sources)
                duration = time.time() - start
                return {
                    "answer": answer,
                    "sources": list(set(compressed_sources)),
                    "chunks": compressed_chunks,
                    "duration": round(duration, 2),
                }
        
        result = rag_pipeline.query(question, top_k=top_k)
        duration = time.time() - start
        result["duration"] = round(duration, 2)
        logger.info(f"Soru cevaplandı: {question[:50]}... ({duration:.2f}s)")
        return result
    except Exception as e:
        logger.error(f"Sorgu hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query/stream")
async def query_stream(request: dict):
    question = request.get("question", "").strip()
    top_k = int(request.get("top_k", TOP_K))
    
    if not question:
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")
    
    async def generate():
        try:
            for chunk in rag_pipeline.query_stream(question, top_k=top_k):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming hatası: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
