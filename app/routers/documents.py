"""
documents.py
FastAPI router：處理文件上傳、解析、以及 key fields 輸出。
"""

import logging
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document import (
    KeyFields,
    KeyFieldsResponse,
    ParseResponse,
)
from app.services.llm_parser import parse_with_llm
from app.services.pdf_extractor import extract_text_from_image, extract_text_from_pdf

from starlette.datastructures import Headers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


# ── 共用解析邏輯 ─────────────────────────────────────────
async def _parse_file(file: UploadFile) -> ParseResponse:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支援的檔案類型: {file.content_type}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="檔案超過 20MB 上限")

    filename = file.filename or "unknown"

    try:
        if file.content_type == "application/pdf":
            raw_text, method = extract_text_from_pdf(file_bytes, filename)
        else:
            raw_text, method = extract_text_from_image(file_bytes, filename)

        if not raw_text:
            return ParseResponse(
                success=False,
                filename=filename,
                error="無法抽取文字，請確認檔案正常",
            )

        parsed = await parse_with_llm(raw_text, filename)
        parsed.extraction_method = f"{method}+{parsed.extraction_method}"

        return ParseResponse(success=True, filename=filename, data=parsed)

    except Exception as e:
        logger.error(f"解析失敗 {filename}: {e}", exc_info=True)
        return ParseResponse(success=False, filename=filename, error=str(e))


# ── Endpoints ────────────────────────────────────────────

@router.post("/parse", response_model=ParseResponse)
async def parse_document(file: UploadFile = File(...)):
    """上傳單一文件，回傳完整解析結果（所有欄位）"""
    return await _parse_file(file)


@router.post("/parse-batch", response_model=List[ParseResponse])
async def parse_documents_batch(files: List[UploadFile] = File(...)):
    """批次上傳，回傳完整解析結果列表"""
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="一次最多 10 個檔案")
    results = []
    for f in files:
        results.append(await _parse_file(f))
    return results


@router.post("/parse/key-fields", response_model=KeyFieldsResponse)
async def parse_key_fields(file: UploadFile = File(...)):
    """
    上傳單一文件，只回傳三個關鍵欄位：
    - MBL No. or Invoice No.
    - Container No(s).
    - Total Amount
    """
    result = await _parse_file(file)

    if not result.success or not result.data:
        return KeyFieldsResponse(
            success=False,
            filename=result.filename,
            error=result.error,
        )

    d = result.data

    # MBL 優先，沒有才用 Invoice No.
    mbl_or_invoice = d.mbl_no or d.invoice_no

    key = KeyFields(
        filename=result.filename,
        mbl_or_invoice_no=mbl_or_invoice,
        container_nos=d.container_nos,
        total_amount=d.total_amount,
        currency=d.currency,
    )

    return KeyFieldsResponse(success=True, filename=result.filename, key_fields=key)


@router.post("/parse-batch/key-fields", response_model=List[KeyFieldsResponse])
async def parse_batch_key_fields(files: List[UploadFile] = File(...)):
    """
    批次上傳，只回傳每份文件的三個關鍵欄位。
    這是最常用的 endpoint。
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="一次最多 10 個檔案")

    results = []
    for f in files:
        # 重新讀取（file 已被 _parse_file 消耗，需要複製）
        file_bytes = await f.read()

        # 建立一個假的 UploadFile wrapper
        from io import BytesIO
        from fastapi import UploadFile as FUploadFile
        import starlette.datastructures

        fake = starlette.datastructures.UploadFile(
            filename=f.filename,
            file=BytesIO(file_bytes),
            size=len(file_bytes),
            headers=Headers({"content-type": f.content_type}),  # ✅
        )


        result = await _parse_file(fake)

        if not result.success or not result.data:
            results.append(KeyFieldsResponse(
                success=False, filename=result.filename, error=result.error
            ))
            continue

        d = result.data
        key = KeyFields(
            filename=result.filename,
            mbl_or_invoice_no=d.mbl_no or d.invoice_no,
            container_nos=d.container_nos,
            total_amount=d.total_amount,
            currency=d.currency,
        )
        results.append(KeyFieldsResponse(
            success=True, filename=result.filename, key_fields=key
        ))

    return results


@router.get("/health")
async def health():
    import httpx
    ollama_status = "offline"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                ollama_status = f"online (models: {', '.join(models)})"
    except Exception:
        pass
    return {"status": "ok", "ollama": ollama_status}