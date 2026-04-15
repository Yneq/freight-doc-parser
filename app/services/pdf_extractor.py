"""
pdf_extractor.py
負責從 PDF 或圖片抽取純文字。
流程：
1. pdfplumber 抽文字型 PDF
2. 文字太少時 fallback 到 PyMuPDF + pytesseract OCR
"""

import io
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 50


def extract_text_from_pdf(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """回傳 (extracted_text, method_used)"""
    try:
        import pdfplumber

        text = ""
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"

        text = text.strip()
        if len(text) >= MIN_TEXT_LENGTH:
            logger.info(f"[pdf_text] {filename}: {len(text)} chars")
            return text, "pdf_text"

        logger.info(f"[pdf_text] {filename}: too short, fallback OCR")
    except Exception as e:
        logger.warning(f"[pdf_text] failed: {e}")

    return _ocr_fallback(file_bytes, filename)


def extract_text_from_image(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    return _ocr_fallback(file_bytes, filename)


def _ocr_fallback(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    try:
        import pytesseract
        from PIL import Image

        if filename.lower().endswith(".pdf"):
            import fitz

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            all_text = []
            for page in doc:
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                all_text.append(pytesseract.image_to_string(img, lang="eng"))
            text = "\n".join(all_text).strip()
        else:
            img = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(img, lang="eng").strip()

        logger.info(f"[ocr] {filename}: {len(text)} chars")
        return text, "ocr"
    except Exception as e:
        logger.error(f"[ocr] failed: {e}")
        return "", "ocr_failed"