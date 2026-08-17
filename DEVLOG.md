# Geliştirme Süreci Kaydı (DEVLOG)

Bu dosya, TUSAŞ Belge Analiz ve Soru-Cevap Sistemi'nin geliştirme sürecini, aldığım kararları,
deneyip vazgeçtiklerimi ve karşılaştığım zorlukları kronolojik olarak belgelemektedir.

---

## 1. Problemi Parçalama

### İlk Analiz
İsteğe gelen sistem 3 temel işlevden oluşuyordu:
1. **Belge yükleme ve metin çıkarımı** (PDF + resim + OCR)
2. **Akıllı bilgi alma** (RAG: chunking, embedding, retrieval)
3. **Doğal dil soru-cevaplama** (LLM + hallucination önleme)

Bu 3 katmanı kafa dağıtmak için modüler olarak tasarladım:
- `utils/document_processor.py` — Dosya formatından bağımsız metin çıkarımı
- `rag/` — Tüm RAG pipeline (chunker, retriever, compressor, llm)
- `core/` — Ortak konfigürasyon, loglama, hata yönetimi
- `backend/main.py` — API katmanı
- `frontend/` — Kullanıcı arayüzü

### Tarih: Başlangıç (Gün 1-2)
- Gereksinimleri tekrar okudum ve her satırı "nasıl test ederim?" sorusuyla değerlendirdim.
- Önce çalışan bir skeleton API kurdum (FastAPI + CORS + static files).
- Daha sonra belge işleme katmanını ekledim.

---

## 2. Teknoloji Seçimi ve Alternatifler

### Backend Framework
**Seçim:** FastAPI
**Alternatifler:** Flask, Django REST Framework, FastAPI
**Karar:** FastAPI seçtim çünkü:
- Async/await desteği ile yüksek performanslı file upload
- Otomatik OpenAPI dokümantasyonu
- Pydantic ile veri doğrulama
- CORS ve static file middleware'leri built-in

### Vektör Veritabanı
**Seçim:** ChromaDB (PersistentClient)
**Alternatifler:** Pinecone, Weaviate, FAISS, Qdrant
**Karar:** ChromaDB seçtim çünkü:
- Kurulum gerektirmiyor, lokal dosya sisteminde çalışıyor
- PersistentClient ile sunucu restartlarından sonra veri kalıyor
- HNSW index + cosine similarity built-in
- Kurumsal ortamda kolayca dağıtılabilir (Docker ile)

### Embedding Modeli
**Seçim:** `all-MiniLM-L6-v2` (SentenceTransformers)
**Alternatifler:** `all-mpnet-base-v2`, ` paraphrase-multilingual-MiniLM-L12-v2`, OpenAI embeddings
**Karar:**
- `all-MiniLM-L6-v2` ~80MB, hızlı, iyi Türkçe/İngilizce performans
- Çok dilli alternatifleri denedim ama 3B parametreli yerel LLM ile uyumlu
- OpenAI API'ye bağımlı kalmamak için açık kaynak tercih ettim

### LLM
**Seçim:** Ollama + `llama3.2:3b`
**Alternatifler:** OpenAI GPT-4o, Anthropic Claude, Mistral, Llama 3 8B, Phi-3
**Karar:**
- Gereksinim "yerel işleme" vurgusu yapıyordu
- `llama3.2:3b` ~2GB, CPU-only'da bile makul hızda çalışıyor
- 8B parametre modeli denedim ama GPU olmayan ortamda çok yavaştı
- 3B modeli, hızlı ve yeterli QA performansı sunuyor
- Ollama, API uyumluluğu sayesinde `requests.post` ile kolayca entegre edildi

### Reranker
**Seçim:** CrossEncoder `ms-marco-MiniLM-L-6-v2`
**Alternatifler:** Cohere Rerank, Jina Reranker, kendi BM25 implementasyonu
**Karar:**
- Açık kaynak, lokal çalışır
- MS MARCO veri seti ile eğitilmiş, passage re-ranking konusunda kanıtlanmış
- Model boyutu küçük (~100MB), hızlı inference

---

## 3. Denenen ve Vazgeçilen Yaklaşımlar

### Chunking Stratejisi
**Denenen:**
1. **Sabit karakter bazlı** (başlangıç)
   - Sorun: Token sayısı kelime uzunluklarına göre değişiyor, context penceresi taşması yaşanabilir
2. **tiktoken token bazlı** (nihai)
   - Çözüm: `cl100k_base` encoding ile gerçek token sayısına göre bölme
   - 600 token ideal parça boyu, 100 token overlap

### Retriever Tasarımı
**Denenen:**
1. **Sadece vektör arama** (başlangıç)
   - Sorun: Bazen tam kelime eşleşmesi (ör: özel terimler, sayılar) kaçıyor
2. **Hibrit arama** (nihai)
   - Vektör benzerliği + BM25-benzeri keyword scoring birleşimi
   - ChromaDB'den gelen sonuçları ikinci bir skorlama ile filtreledim

### Reranker Konumu
**Denenen:**
1. **Sadece retriever içinde** (ilk tasarım)
   - Sorun: Compressor modülü de reranker kullanıyordu, gereksiz model yüklenmesi
2. **Retriever + Compressor ayrı** (nihai)
   - Retriever ilk filtreleme, Compressor son sıkıştırma
   - Global `_reranker` singleton ile model tek sefer yükleniyor

### Prompt Engineering
**Denenen:**
1. **Basit prompt** ("Bağlamı kullan, cevap ver")
   - Sorun: Model hala bağlam dışı bilgi ekliyor, İngilizce kelimeler kullanıyor
2. **Katmanlı kural seti** (nihai)
   - 7 kural, her biri spesifik bir hallucination türüne karşı
   - "Bu bilgi bulunmuyor" fallback'ı
   - Kaynak numaralandırma zorunluluğu
   - Türkçe zorunluluğu

---

## 4. Kritik Karar Noktaları

### Karar 1: Ollama Yerine API Tabanlı LLM mi?
**Alternatifler:** Ollama (yerel) vs OpenAI API vs Anthropic API
**Değerlendirme:**
- API tabanlı modeller daha akıllı, daha hızlı
- Ancak veri güvenliği, maliyet ve offline çalışma gereksinimleri vardı
- Yerel LLM seçimi, sistemin "harici sunucuya veri göndermeme" ilkesine uyuyor
- **Sonuç:** Ollama + llama3.2:3b

### Karar 2: OCR Tesseract mi, EasyOCR mi?
**Alternatifler:** Tesseract (kural tabanlı) vs EasyOCR (derin öğrenme)
**Değerlendirme:**
- EasyOCR daha iyi OCR kalitesi sunuyor ama ~1GB model indirme gerektiriyor
- Tesseract + Türkçe paketi ile %90+ doğruluk oranı elde ediliyor
- Tesseract daha hafif, Docker'da daha kolay kuruluyor
- **Sonuç:** Tesseract 5.x

### Karar 3: Statik Frontend mi, React/Vue mi?
**Alternatifler:** Vanilla JS/HTML vs React vs Vue
**Değerlendirme:**
- Gereksinim MVP, kolay dağıtılabilir sistem
- React build pipeline ekstra karmaşıklık katıyor
- Vanilla JS ile aynı işlevsellik sunuluyor
- **Sonuç:** Tek dosya HTML + vanilla JS

### Karar 4: Chunk Boyutu 400 mü, 600 mı, 1000 mi?
**Denenen:** 400, 600, 800, 1000
**Değerlendirme:**
- 400: Çok fazla chunk, LLM context penceresi gereksiz yoruluyor
- 1000: Çok az chunk, kritik bilgi bölünüyor
- 600: Testlerde en iyi denge
- Overlap %16 (100 karakter) ile bilgi kaybı önlendi
- **Sonuç:** 600 karakter + 100 overlap

---

## 5. Karşılaşılan Zorluklar ve Çözümleri

### Zorluk 1: Tesseract Windows'ta Bulunamama
**Problem:** Windows'ta Tesseract varsayılan PATH'te olmayabiliyor.
**Çözüm:** `utils/document_processor.py` içinde otomatik tespit mekanizması:
1. `TESSERACT_CMD` ortam değişkeni kontrolü
2. `shutil.which("tesseract")` ile PATH taraması
3. Windows varsayılan kurulum yolu (`C:\Program Files\Tesseract-OCR\tesseract.exe`)
4. Bulunamazsa uyarı logu, OCR devre dışı kalır

### Zorluk 2: ChromaDB Kalıcılığı
**Problem:** Sunucu restart sonrası vektör veritabanı kayboluyordu.
**Çözüm:** `chromadb.PersistentClient(path=CHROMA_DIR)` kullanımı.
`chroma_db/` klasörü proje kökünde kalıyor, restart sonrası koleksiyon korunuyor.

### Zorluk 3: GPU Bellek Yönetimi
**Problem:** Embedding modeli ve reranker aynı anda VRAM'i dolduruyordu.
**Çözüm:** 
- Embedding modeli ve reranker için ayrı singleton instance'lar
- `torch.cuda.is_available()` ile otomatik cihaz seçimi
- CPU fallback mekanizması
- Model yükleme logları ile izleme imkanı

### Zorluk 4: Hallucination Azaltma
**Problem:** LLM bazen bağlam dışı bilgiler ekliyordu.
**Çözüm:** Çok katmanlı yaklaşım:
1. `temperature=0.0` ile deterministik çıktı
2. Prompt'ta 7 kural ile kısıtlama
3. "Bu bilgi bulunmuyor" fallback'ı
4. Kaynak numaralandırma zorunluluğu
5. Türkçe zorunluluğu
6. `_clean_answer()` ile post-processing (duplicate satır temizleme, yanlış kelime düzeltme)

### Zorluk 5: Frontend-Backend İletişimi
**Problem:** CORS hatası, statik dosya sunumu.
**Çözüm:**
- FastAPI `CORSMiddleware` ile `allow_origins=["*"]` (geliştirme)
- `StaticFiles` mount ile `/static` endpoint'i
- Production'da nginx reverse proxy önerisi

---

## 6. Zaman Yönetimi

| Aşama | Tahmini | Gerçekleşen | Notlar |
|--------|---------|-------------|--------|
| Mimari tasarım | 3 saat | 3 saat | Teknoloji araştırması, karar matrisi |
| Backend skeleton | 2 saat | 2 saat | FastAPI, middleware, logging |
| Belge işleme | 5 saat | 6 saat | OCR entegrasyonu, Windows hataları |
| RAG Pipeline | 8 saat | 10 saat | Chunker, retriever, reranker, compressor |
| LLM entegrasyonu | 4 saat | 5 saat | Prompt engineering, streaming |
| Frontend | 6 saat | 6 saat | TUSAŞ teması, responsive tasarım |
| Test ve debug | 4 saat | 5 saat | Farklı belge tipleri, edge case'ler |
| Dokümantasyon | 2 saat | 3 saat | README, DEVLOG, TESTING |

**Toplam:** ~34 saat (tahmini 25-35 saat aralığında)

---

## 7. Baştan Başlasaymış Ne Yapardım?

1. **Test odaklı geliştirme:** Önce test senaryolarını yazıp TDD ile geliştirirdim. Şu anda kod var, testler eksik.
2. **Multi-LLM desteği:** Sadece Ollama değil, OpenAI/Anthropic API desteği de eklerdim. Kullanıcı model seçebilirdi.
3. **Belge yönetimi:** Chunk'ların kaynak belge ile ilişkisini daha güçlü tutardım. Metadata yapısını zenginleştirirdim (sayfa numarası, bölüm, tablo vb.).
4. **Caching stratejisi:** Embedding'leri diskte cache'lerdim. Aynı belge tekrar sorgulama durumunda embedding hesaplamasını tekrar yapmazdım.
5. **Docker Compose:** Sadece backend Dockerfile yerine, Ollama + backend + (opsiyonel) redis/queue için docker-compose.yml yapardım.
6. **Loglama:** Daha yapılandırılmış loglar (JSON format, seviyeler, request ID ile tracing) eklerdim.
7. **Rate limiting:** API endpoint'lerine rate limiting eklerdim, özellikle LLM endpoint'leri pahalı.
8. **Streaming frontend entegrasyonu:** `/api/query/stream` endpoint'i mevcut ama frontend'de kullanılmıyor. Bunu aktifleştirirdim.

---

## 8. Teknik Karar Özeti

| Konu | Karar | Gerekçe |
|------|-------|---------|
| Backend | FastAPI | Async, otomatik API docs, performans |
| DB | ChromaDB Persistent | Kurulum gerektirmez, lokal, kalıcı |
| Embedding | all-MiniLM-L6-v2 | Hafif, hızlı, iyi çoklu dil |
| LLM | Ollama + llama3.2:3b | Yerel, offline, uygun VRAM |
| Reranker | CrossEncoder ms-marco | Açık kaynak, kanıtlanmış |
| OCR | Tesseract 5.x | Hafif, Türkçe desteği |
| Frontend | Vanilla HTML/JS | MVP, kolay dağıtım |
| Chunking | tiktoken cl100k_base | Token-aware, LLM uyumlu |
| Hosting | Docker | Taşınabilir, tek komutla çalışır |

---

*Son güncelleme: 2026-08-17*
