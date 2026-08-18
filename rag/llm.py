import re
import requests
from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL, LLM_TEMPERATURE, LLM_NUM_CTX, OLLAMA_TIMEOUT, LLM_NUM_PREDICT, OLLAMA_NUM_GPU
from core.logging import logger


def _build_prompt(question: str, context_chunks: list[str], source_files: list[str]) -> str:
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        source = source_files[i] if i < len(source_files) else "Bilinmiyor"
        context_parts.append(f"[{i+1}] Kaynak: {source}\n{chunk}")
    context = "\n\n".join(context_parts)

    prompt = f"""Sen TUSAŞ belge analiz asistanısın. Aşağıdaki kurallara KESİNLİKLE uy:
1. YALNIZCA BAĞLAM'daki bilgiyi kullan. Bağlamda olmayan hiçbir bilgiyi ekleme, varsayma veya uydurma.
2. Cevap bağlamda tamamen yoksa sadece "Bu bilgi verilen belgelerde bulunmuyor." de. Hiçbir şey ekleme.
3. Cevabı oluştururken bağlamdaki tam ifadeleri, terimleri ve sayıları koru. Yorumlama yapma.
4. Eğer aynı bilgi birden fazla parçada geçiyorsa, bunu birleştirerek tekrar etme.
5. Her önemli bilgi için mutlaka [1], [2] gibi kaynak numarası belirt. Kaynağı belirtmediğin bilgi verme.
6. Türkçe cevap ver. İngilizce kelime veya ifade kullanma.
7. Net, öz, doğru ve bağlama sadık kal. Gereksiz genellemelerden kaçın.

BAĞLAM PARÇALARI:
{context}

SORU: {question}

CEVAP:"""
    return prompt


def _clean_answer(answer: str) -> str:
    answer = answer.strip()
    if not answer:
        return answer

    answer = re.sub(r'followinglar\s*:\s*', 'şunlar:', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\brequireddir\b', 'gerekir', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\binclude:\s*', '', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\brequired\b', 'gerekli', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\bfollowing\b', 'şunlar', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\bvalorizasyonun\b', 'değerleme', answer, flags=re.IGNORECASE)
    answer = re.sub(r'\bsunmak required\b', 'sunmak gerekir', answer, flags=re.IGNORECASE)

    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    seen = set()
    cleaned = []
    for line in lines:
        normalized = re.sub(r'\s+', ' ', line).strip()
        if normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)

    text = "\n".join(cleaned)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def generate_answer(question: str, context_chunks: list[str], source_files: list[str]) -> str:
    prompt = _build_prompt(question, context_chunks, source_files)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": LLM_TEMPERATURE, "num_ctx": LLM_NUM_CTX, "num_predict": LLM_NUM_PREDICT, "num_gpu": OLLAMA_NUM_GPU},
    }
    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        answer = _clean_answer(data.get("response", ""))
        logger.info(f"LLM yanıtı üretildi. Uzunluk: {len(answer)} karakter")
        return answer
    except requests.exceptions.ConnectionError:
        logger.error("Ollama bağlantı hatası")
        return "Hata: Ollama servisine bağlanılamıyor. Lütfen Ollama'nın çalıştığından emin olun."
    except Exception as e:
        logger.error(f"LLM hatası: {e}")
        return f"Hata: {str(e)}"


def generate_answer_stream(question: str, context_chunks: list[str], source_files: list[str]):
    prompt = _build_prompt(question, context_chunks, source_files)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": LLM_TEMPERATURE, "num_ctx": LLM_NUM_CTX, "num_predict": LLM_NUM_PREDICT, "num_gpu": OLLAMA_NUM_GPU},
    }
    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT, stream=True)
        resp.raise_for_status()
        buffer = ""
        for line in resp.iter_lines(decode_unicode=True):
            if line:
                import json
                data = json.loads(line)
                if "response" in data:
                    buffer += data["response"]
                    yield buffer
        if not buffer:
            yield buffer
    except Exception as e:
        logger.error(f"Streaming LLM hatası: {e}")
        yield f"Hata: {str(e)}"
