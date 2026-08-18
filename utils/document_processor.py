import re
import uuid
import os
import shutil
from pathlib import Path
from typing import Tuple, Optional

import fitz
import tiktoken
from pdf2image import convert_from_path
from PIL import Image
import torch
from core.config import DATA_DIR, OCR_BACKEND, OCR_GPU, OCR_LANGS
from core.logging import logger


def _resolve_tesseract_cmd():
    env_path = os.getenv("TESSERACT_CMD")
    if env_path and Path(env_path).exists():
        return env_path
    which = shutil.which("tesseract")
    if which:
        return which
    windows_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if Path(windows_default).exists():
        return windows_default
    return None


_tesseract_cmd = _resolve_tesseract_cmd()
_easyocr_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader
    try:
        import easyocr
        use_gpu = OCR_GPU and torch.cuda.is_available()
        langs = [lang.strip() for lang in OCR_LANGS.split(",") if lang.strip()]
        _easyocr_reader = easyocr.Reader(langs, gpu=use_gpu)
        logger.info(f"EasyOCR başlatıldı: diller={langs}, gpu={use_gpu}")
        return _easyocr_reader
    except Exception as e:
        logger.warning(f"EasyOCR başlatılamadı: {e}")
        return None


if _tesseract_cmd:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
    logger.info(f"Tesseract bulundu: {_tesseract_cmd}")
else:
    logger.warning("Tesseract bulunamadı. OCR işlevleri için EasyOCR kullanılacak.")


def ensure_data_dir():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file) -> str:
    ensure_data_dir()
    file_id = str(uuid.uuid4())
    ext = Path(uploaded_file.name).suffix.lower()
    filename = f"{file_id}{ext}"
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\r", "\n", text)
    text = text.lstrip("\ufeff")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _ocr_image_easyocr(image_path: str) -> str:
    reader = _get_easyocr_reader()
    if reader is None:
        return ""
    try:
        results = reader.readtext(image_path, paragraph=True, detail=0)
        return "\n".join(results)
    except Exception as e:
        logger.error(f"EasyOCR hatası: {e}")
        return ""


def _ocr_image_tesseract(image_path: str) -> str:
    if not _tesseract_cmd:
        return ""
    try:
        image = Image.open(image_path)
        return pytesseract.image_to_string(image, lang="tur+eng")
    except Exception as e:
        logger.error(f"Tesseract OCR hatası: {e}")
        return ""


def _ocr_image(image_path: str) -> str:
    if OCR_BACKEND == "easyocr":
        text = _ocr_image_easyocr(image_path)
        if text.strip():
            return text
        return ""
    if OCR_BACKEND == "tesseract":
        return _ocr_image_tesseract(image_path)
    if OCR_BACKEND == "auto":
        text = _ocr_image_easyocr(image_path)
        if text.strip():
            return text
        return _ocr_image_tesseract(image_path)
    return ""


def extract_text_from_pdf(filepath: str) -> str:
    text = ""
    try:
        doc = fitz.open(filepath)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
        doc.close()
    except Exception as e:
        logger.error(f"PDF metin çıkarım hatası: {e}")
        text = ""
    return text


def extract_text_from_image(filepath: str) -> str:
    return clean_text(_ocr_image(filepath))


def extract_text_from_pdf_with_ocr(filepath: str) -> str:
    text = extract_text_from_pdf(filepath)
    if text.strip():
        return text
    text = ""
    try:
        images = convert_from_path(filepath)
        for idx, image in enumerate(images):
            tmp_path = os.path.join(DATA_DIR, f"ocr_temp_{uuid.uuid4()}_{idx}.png")
            image.save(tmp_path)
            text += _ocr_image(tmp_path) + "\n"
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    except Exception as e:
        logger.error(f"PDF OCR hatası: {e}")
    return text


def extract_text_from_file(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        return clean_text(extract_text_from_pdf_with_ocr(filepath))
    elif ext in [".txt", ".md", ".csv"]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return clean_text(f.read())
        except Exception as e:
            logger.error(f"Text okuma hatası: {e}")
            return ""
    elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        return clean_text(extract_text_from_image(filepath))
    return ""
