# TUSAŞ Belge Analiz ve Soru-Cevap Sistemi

AI destekli, yerel işlemli, kurumsal düzeyde bir **Retrieval-Augmented Generation (RAG)** platformudur. Kullanıcılar PDF, resim ve metin formatlarındaki belgelerini yükleyerek; yapay zeka destekli analiz, akıllı chunking, hibrit arama, cross-encoder reranking ve yerel LLM (Ollama) tabanlı soru-cevaplama yapabilir.

---

## Özellikler

### Belge İşleme
- **Çoklu format desteği:** PDF (dijital + taranmış), JPG, PNG, BMP, TIFF, TXT, MD, CSV
- **Otomatik OCR:** Tesseract 5.x ile Türkçe + İngilizce dil paketi
- **Hibrit çıkarım:** Önce düz metin (PyMuPDF), başarısız olunca otomatik OCR devreye girer
- **Çoklu yükleme:** Aynı anda birden fazla dosya yükleme

### RAG Pipeline
- **Akıllı chunking:** tiktoken (`cl100k_base`) ile karakter/ token bazlı bölme, 600 karakter ideal parça boyu, %16 overlap
- **Vektör depolama:** ChromaDB + HNSW cosine similarity
- **Hibrit arama:** Vektör benzerliği + BM25-benzeri anahtar kelime skorlaması
- **Cross-encoder reranking:** `ms-marco-MiniLM-L-6-v2` ile yeniden sıralama
- **Bağlam sıkıştırma:** En alakalı parçaları öne çıkarma, context penceresini optimize etme

### LLM ve Hallucination Önleme
- **Yerel LLM:** Ollama ile `llama3.2:3b` (veya özelleştirilmiş model)
- **Sıfır sıcaklık:** `temperature=0.0` ile deterministik çıktı
- **Prompt engineering:** "Yalnızca bağlam" kuralı, kaynak zorunluluğu, Türkçe zorunluluğu
- **Bilgi yoksa net mesaj:** Belgede olmayan bilgiler üretilmez
- **Kaynak numaralandırma:** `[1]`, `[2]` ile şeffaf atıf

### Kullanıcı Arayüzü
- **Responsive tasarım:** Mobil, tablet, masaüstü uyumlu
- **Sürükle-bırak yükleme:** Dosya yükleme alanı
- **Belge listesi:** Yüklenen dosyalar, chunk sayısı, durum (yeni/cache)
- **Seçmeli arama:** Sadece istediğiniz belgelerde arama
- **Kaynak gösterimi:** Cevabın hangi dosyadan geldiği
- **Anlık metrikler:** Yanıt süresi, belge sayısı, toplam parça sayısı
- **Marka uyumu:** TUSAŞ renk paleti ve logosu

### Güvenlik ve Gizlilik
- **Tamamen yerel işleme:** Hiçbir veri harici sunuculara gönderilmez
- **Kalıcı depolama:** ChromaDB lokal dosya sisteminde
- **Hash kontrolü:** Aynı dosya tekrar yüklenmez
- **Geçici dosya yönetimi:** Yükleme sırasında temp dosyalar otomatik silinir

---

## Mimari

```
┌─────────────────┐    HTTP/JSON     ┌──────────────────┐
│   Frontend      │◄───────────────►│   FastAPI        │
│   (HTML/JS)     │                 │   Backend        │
└─────────────────┘                 └────────┬─────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
          ┌─────────────────┐   ┌───────────────────┐   ┌──────────────────┐
          │ Document        │   │ RAG Pipeline      │   │ Ollama LLM       │
          │ Processor       │   │                   │   │ (llama3.2:3b)   │
          │ (OCR, PDF, TXT) │   │ Chunker           │   └──────────────────┘
          └─────────────────┘   │ Retriever         │
                                │ Compressor        │
                                │ LLM Generator     │
                                └─────────┬─────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          │               │               │
                          ▼               ▼               ▼
                  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
                  │ ChromaDB    │ │ Sentence    │ │ Cross-      │
                  │ (Vektör DB) │ │ Transformer │ │ Encoder     │
                  │             │ │ Embedding   │ │ Reranker    │
                  └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Teknoloji Yığını

| Katman | Teknoloji | Amaç |
|--------|-----------|------|
| Backend | FastAPI + Uvicorn | API sunucusu, async request handling |
| Frontend | HTML5 + Vanilla JS + CSS3 | Responsive arayüz, sürükle-bırak |
| OCR | Tesseract 5.x + pdf2image + Pillow | Taranmış belgelerden metin çıkarımı |
| PDF | PyMuPDF (fitz) | Dijital PDF metin çıkarımı |
| Embedding | SentenceTransformers (`all-MiniLM-L6-v2`) | Metin vektörleştirme |
| Vektör DB | ChromaDB (HNSW, cosine) | Semantic arama |
| Reranker | CrossEncoder (`ms-marco-MiniLM-L-6-v2`) | Relevance sıralama |
| LLM | Ollama (`llama3.2:3b`) | Yerel metin üretimi |
| Chunking | tiktoken (`cl100k_base`) | Token-aware metin bölme |
| Diğer | python-dotenv, requests, torch | Konfigürasyon, HTTP, CUDA desteği |

---

## Kurulum

### Gereksinimler
- Python 3.12+
- Node.js (opsiyonel, frontend statik dosya olarak sunulur)
- Ollama (LLM için)
- Tesseract OCR (Windows'ta önerilen)
- NVIDIA GPU + CUDA 11.8 (opsiyonel, hızlandırma için)

### Adım 1: Deposu Klonlayın
```bash
git clone <repository-url>
cd tusas-doc-qa
```

### Adım 2: Sanal Ortam Oluşturun
```bash
python -m venv venv
venv\Scripts\activate   # Windows
# veya
source venv/bin/activate   # Linux/macOS
```

### Adım 3: Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### Adım 4: Ollama Kurulumu
1. [Ollama](https://ollama.ai) indirin ve kurun
2. Modeli çekin:
   ```bash
   ollama pull llama3.2:3b
   ollama serve   # Windows'ta servis olarak çalışır
   ```

### Adım 5: Tesseract OCR (Windows)
1. [Tesseract at UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) indirin
2. Kurulum sırasında **Türkçe** ve **İngilizce** dil paketlerini seçin
3. `.env.example` dosyasını `.env` olarak kopyalayın ve gerekirse `TESSERACT_CMD` yolunu ayarlayın:
   ```
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

### Adım 6: Çevre Değişkenleri
```bash
cp .env.example .env
```
Gerekli değerleri `.env` dosyasında düzenleyin.

---

## Çalıştırma

### Yerel Geliştirme
```bash
# Sanal ortam aktif değilse:
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Linux/macOS

# Sunucuyu başlat:
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
# veya Windows için:
run.bat
```

### Docker
```bash
docker build -t tusas-doc-qa .
docker run -p 8000:8000 tusas-doc-qa
```

Tarayıcıda açın: `http://localhost:8000`

---

## Kullanım

1. **Belge Yükleme:** Sol panelden PDF, TXT, MD, CSV, JPG, PNG, BMP, TIFF dosyalarını sürükleyip bırakın veya seçin.
2. **Belge Seçimi:** Arama yapmak istediğiniz belgeleri işaretleyin.
3. **Soru Sorma:** Sağ panelde doğal dilde soru sorun.
4. **Kaynak İnceleme:** Cevabın hangi belgeden geldiğini kaynak chip'lerden görün.

---

## API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/health` | Sistem sağlık kontrolü |
| GET | `/` | Frontend arayüzü |
| POST | `/api/documents/upload` | Belge yükle |
| GET | `/api/documents` | Yüklenen belgeleri listele |
| DELETE | `/api/documents/{file_id}` | Belge sil |
| DELETE | `/api/documents` | Tüm belgeleri temizle |
| POST | `/api/query` | Soru sor (sync) |
| POST | `/api/query/stream` | Soru sor (streaming) |

---

## Proje Yapısı

```
tusas-doc-qa/
├── backend/
│   └── main.py                 # FastAPI uygulaması, endpoint'ler
├── core/
│   ├── config.py               # Konfigürasyon ve .env yönetimi
│   ├── logging.py              # Loglama yapılandırması
│   └── exceptions.py           # Özel hata sınıfları
├── rag/
│   ├── pipeline.py             # RAG pipeline, DocumentStore
│   ├── chunker.py              # Metin bölme (tiktoken)
│   ├── retriever.py            # ChromaDB, embedding, hibrit arama, reranking
│   ├── compressor.py           # Bağlamsal sıkıştırma (cross-encoder)
│   └── llm.py                  # Ollama entegrasyonu, prompt engineering
├── utils/
│   └── document_processor.py   # OCR, PDF, metin çıkarımı
├── frontend/
│   ├── index.html              # Tek sayfa uygulama (SPA)
│   └── assets/
│       └── tusas-logo.svg      # Marka logosu
├── data/                       # Yüklenen belgeler (geçici)
├── chroma_db/                  # Vektör veritabanı (kalıcı)
├── logs/                       # Uygulama logları
├── requirements.txt            # Python bağımlılıkları
├── Dockerfile                  # Konteyner imajı
├── .env.example                # Konfigürasyon şablonu
├── run.bat                     # Windows başlatıcı
├── run.sh                      # Linux/macOS başlatıcı
├── README.md                   # Bu dosya
├── DEVLOG.md                   # Geliştirme süreci kaydı
└── TESTING.md                  # Test senaryoları ve sonuçları
```

---

## Konfigürasyon

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API adresi |
| `OLLAMA_MODEL` | `llama3.2:3b` | Kullanılacak LLM modeli |
| `OLLAMA_TIMEOUT` | `180` | LLM istek zaman aşımı (saniye) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding modeli |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Reranker modeli |
| `CHUNK_SIZE` | `600` | Chunk boyutu (token/karakter) |
| `CHUNK_OVERLAP` | `100` | Chunk çakışma boyutu |
| `TOP_K` | `10` | Son aşamada seçilecek parça sayısı |
| `HYBRID_TOP_K` | `30` | Hibrit aramada ilk adım parça sayısı |
| `LLM_TEMPERATURE` | `0.0` | LLM sıcaklık değeri (0 = deterministik) |
| `LLM_NUM_CTX` | `2048` | LLM bağlam penceresi |
| `LLM_NUM_PREDICT` | `512` | LLM maksimum üretim token'ı |
| `TESSERACT_CMD` | (otomatik) | Tesseract executable yolu (Windows) |

---

## Lisans

Bu proje TUSAŞ (Türk Havacılık ve Uzay Sanayii A.Ş.) teknik değerlendirme kapsamında geliştirilmiştir.
