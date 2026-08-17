import re
from typing import List, Optional

import tiktoken
from core.config import CHUNK_SIZE, CHUNK_OVERLAP, DEBUG
from core.logging import logger


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\r", "\n", text)
    text = text.lstrip("\ufeff")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> List[str]:
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        encoding = None

    text = clean_text(text)
    if not text:
        return []

    if encoding:
        tokens = encoding.encode(text)
        chunks = []
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            start += chunk_size - chunk_overlap
        return [c.strip() for c in chunks if c.strip()]
    else:
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - chunk_overlap
        return [c.strip() for c in chunks if c.strip()]
