"""
llm_parser.py
把抽出的純文字餵給 Ollama（llama3.2），要求回傳結構化 JSON。
Ollama 離線時自動切換 regex fallback。
"""

import json
import logging
import re
from typing import Optional

import httpx

from app.schemas.document import DocumentType, ParsedDocument

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"

SYSTEM_PROMPT = """You are a freight document parser. Extract specific fields from shipping documents.
Always respond with ONLY valid JSON, no markdown, no explanation.

Required JSON structure:
{
  "document_type": "invoice|sea_waybill|notice_of_arrival|bill_of_lading|unknown",
  "invoice_no": "string or null",
  "mbl_no": "string or null",
  "hbl_no": "string or null",
  "booking_no": "string or null",
  "container_nos": ["array of container numbers"],
  "total_amount": "string or null (numeric only, e.g. '785.00')",
  "currency": "string or null (e.g. 'USD')",
  "vessel_voyage": "string or null",
  "port_of_loading": "string or null",
  "port_of_discharge": "string or null",
  "eta": "string or null",
  "commodity": "string or null",
  "raw_charges": [{"name": "charge name", "amount": "amount string"}]
}
Priority rules:
1. Invoice No must NEVER match shipping line patterns (YM, ONEY, ZIM)
2. If conflict, prefer explicit label "Invoice"

Rules:
- container_nos: patterns like XXXX1234567 (4 uppercase letters + 7 digits)
- mbl_no: Master Bill of Lading number
- hbl_no: House Bill of Lading number
- total_amount: numeric string only, no currency symbol
- If not found, use null / []
- Return ONLY the JSON object

You MUST extract values strictly from the document text.

Rules:
1. Do NOT guess values
2. Do NOT swap fields
3. Invoice number usually starts with "INV", "NV", "INVOICE"
4. MBL number usually looks like shipping line code (e.g. YMJAW, ZIMU, ONEY, etc.)
5. If uncertain, return null

If a value appears in multiple contexts, choose the label closest to it in the document.
"""


async def parse_with_llm(raw_text: str, filename: str) -> ParsedDocument:
    try:
        result = await _call_ollama(raw_text)
        if result:
            result["extraction_method"] = "llm"

            doc = _dict_to_parsed_doc(result)
            doc = validate_fields(doc)

            return doc
            result["raw_text_preview"] = raw_text[:300]
            return _dict_to_parsed_doc(result)
    except Exception as e:
        logger.warning(f"[llm] Ollama failed: {e}, using regex fallback")

    return _regex_fallback(raw_text)


async def _call_ollama(text: str) -> Optional[dict]:
    payload = {
        "model": MODEL,
        "prompt": f"Parse this freight document and return JSON only:\n\n{text[:4000]}",
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()

    raw = resp.json().get("response", "")
    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)


def _regex_fallback(text: str) -> ParsedDocument:
    logger.info("[regex] Using regex fallback parser")
    doc = ParsedDocument(extraction_method="regex", confidence="medium")
    doc.raw_text_preview = text[:300]

    # Container No: 4 大寫字母 + 7 位數字
    containers = re.findall(r"\b([A-Z]{4}\d{7})\b", text)
    doc.container_nos = list(set(containers))

    # MBL / Waybill No.
    mbl_patterns = [
        r"MBL\s*[:#]?\s*([A-Z0-9]{8,20})",
        r"(?:SEA WAYBILL NO|WAYBILL NO|B/L NO)\.?\s*[:#]?\s*([A-Z0-9]{8,20})",
        r"BILL OF LADING\s*[:#]?\s*([A-Z0-9]{8,20})",
        r"\b(YMJ[A-Z0-9]{10,})\b",
        r"\b(ONE[A-Z0-9]{10,})\b",
        r"\b(ZIMU[A-Z0-9]{8,})\b",
    ]
    for pat in mbl_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            doc.mbl_no = m.group(1)
            break

    # HBL
    hbl_m = re.search(r"HBL\s*[:#]?\s*([A-Z0-9]+)", text, re.IGNORECASE)
    if hbl_m:
        doc.hbl_no = hbl_m.group(1)

    # Invoice No.
    inv_m = re.search(r"Invoice\s*(?:Number|No\.?)\s*[:#]?\s*(NV\d+|\w+)", text, re.IGNORECASE)
    if inv_m:
        doc.invoice_no = inv_m.group(1)

    # Total Amount
    total_patterns = [
        r"Total\s+\$?([\d,]+\.?\d*)",
        r"TOTAL COLLECT\s+USD?\s*([\d,]+\.?\d*)",
        r"ADJUSTED COLLECT\s+USD?\s*([\d,]+\.?\d*)",
    ]
    for pat in total_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            doc.total_amount = m.group(1).replace(",", "")
            doc.currency = "USD"
            break

    # ETA
    eta_m = re.search(r"ETA\s*[:#]?\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if eta_m:
        doc.eta = eta_m.group(1)

    # Port of Loading
    pol_m = re.search(r"Port of Loading\s*[:#]?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if pol_m:
        doc.port_of_loading = pol_m.group(1).strip()

    # Document type
    if doc.invoice_no or "INVOICE" in text.upper():
        doc.document_type = DocumentType.INVOICE
    elif "NOTICE OF ARRIVAL" in text.upper():
        doc.document_type = DocumentType.NOTICE_OF_ARRIVAL
    elif "SEA WAYBILL" in text.upper():
        doc.document_type = DocumentType.SEA_WAYBILL
    elif "BILL OF LADING" in text.upper():
        doc.document_type = DocumentType.BILL_OF_LADING

    return doc


def _dict_to_parsed_doc(d: dict) -> ParsedDocument:
    try:
        doc_type = DocumentType(d.get("document_type", "unknown"))
    except ValueError:
        doc_type = DocumentType.UNKNOWN

    raw_charges = d.get("raw_charges", [])
    if not isinstance(raw_charges, list):
        raw_charges = []

    return ParsedDocument(
        document_type=doc_type,
        invoice_no=d.get("invoice_no"),
        mbl_no=d.get("mbl_no"),
        hbl_no=d.get("hbl_no"),
        booking_no=d.get("booking_no"),
        container_nos=d.get("container_nos") or [],
        total_amount=d.get("total_amount"),
        currency=d.get("currency"),
        vessel_voyage=d.get("vessel_voyage"),
        port_of_loading=d.get("port_of_loading"),
        port_of_discharge=d.get("port_of_discharge"),
        eta=d.get("eta"),
        commodity=d.get("commodity"),
        raw_charges=raw_charges,
        extraction_method=d.get("extraction_method", "llm"),
        confidence="high",
        raw_text_preview=d.get("raw_text_preview"),
    )

# def is_mbl(value: str) -> bool:
#     return any(x in value.upper() for x in ["YM", "ONEY", "ZIM", "MAEU"])

# def is_invoice(value: str) -> bool:
#     return value.upper().startswith(("INV", "NV", "IN"))

# def validate_fields(d):
#     if d.invoice_no and is_mbl(d.invoice_no):
#         logger.warning(f"invoice misclassified as mbl: {d.invoice_no}")
#         d.invoice_no = None
#     return d