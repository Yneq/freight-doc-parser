from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class DocumentType(str, Enum):
    INVOICE = "invoice"
    SEA_WAYBILL = "sea_waybill"
    NOTICE_OF_ARRIVAL = "notice_of_arrival"
    BILL_OF_LADING = "bill_of_lading"
    UNKNOWN = "unknown"


class ParsedDocument(BaseModel):
    document_type: DocumentType = DocumentType.UNKNOWN
    invoice_no: Optional[str] = None
    mbl_no: Optional[str] = None
    hbl_no: Optional[str] = None
    booking_no: Optional[str] = None
    container_nos: List[str] = []
    total_amount: Optional[str] = None
    currency: Optional[str] = None
    vessel_voyage: Optional[str] = None
    port_of_loading: Optional[str] = None
    port_of_discharge: Optional[str] = None
    eta: Optional[str] = None
    commodity: Optional[str] = None
    raw_charges: List[dict] = []
    extraction_method: str = "unknown"
    confidence: str = "high"
    raw_text_preview: Optional[str] = None


class ParseResponse(BaseModel):
    success: bool
    filename: str
    data: Optional[ParsedDocument] = None
    error: Optional[str] = None


class KeyFields(BaseModel):
    filename: str
    mbl_or_invoice_no: Optional[str] = None
    container_nos: List[str] = []
    total_amount: Optional[str] = None
    currency: Optional[str] = None


class KeyFieldsResponse(BaseModel):
    success: bool
    filename: str
    key_fields: Optional[KeyFields] = None
    error: Optional[str] = None