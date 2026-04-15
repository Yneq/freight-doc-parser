# 🚢 Freight Document Parser

A local, zero-cost document parsing tool for freight logistics.  
Upload PDFs (Invoice, Sea Waybill, Notice of Arrival) and automatically extract key fields using **FastAPI + pdfplumber + Ollama (llama3.2)**.

---
## Demo

<img src="assets/demo.gif" width="700"/>


## Features

- **PDF text extraction** via pdfplumber (fast, accurate for text-based PDFs)
- **OCR fallback** via PyMuPDF + pytesseract (for scanned documents)
- **Local LLM parsing** via Ollama llama3.2 — no API cost, fully offline
- **Regex fallback** when Ollama is unavailable
- **Batch upload** up to 10 files at once
- **Two output modes**: Key Fields only, or Full Parse
- **Built-in web UI** served directly from FastAPI

## Extracted Fields

| Field | Description |
|-------|-------------|
| MBL No. / Invoice No. | Master Bill of Lading or Invoice number |
| Container No(s). | All container numbers in the document |
| Total Amount | Total charges with currency |
| HBL No. | House Bill of Lading number |
| ETA | Estimated Time of Arrival |
| Port of Loading / Discharge | Origin and destination ports |
| Vessel / Voyage | Ship name and voyage number |
| Commodity | Cargo description |
| Charges Breakdown | Itemized charge list |

---

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **PDF Parsing**: pdfplumber, PyMuPDF
- **OCR**: pytesseract + Pillow
- **LLM**: Ollama (llama3.2) — local inference
- **Validation**: Pydantic v2
- **Frontend**: Vanilla HTML/CSS/JS (no framework)

---

## Getting Started

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- tesseract-ocr (optional, for scanned PDFs)
```bash
# Install tesseract on macOS
brew install tesseract
```

### Installation
```bash
git clone https://github.com/Yneq/freight-doc-parser
cd freight-doc-parser

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Pull the LLM model
```bash
ollama pull llama3.2
```

### Run
```bash
uvicorn app.main:app --reload --port 8000
```

Open your browser at **http://127.0.0.1:8000**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/parse` | Parse single file, all fields |
| POST | `/api/documents/parse-batch` | Parse multiple files, all fields |
| POST | `/api/documents/parse/key-fields` | Parse single file, key fields only |
| POST | `/api/documents/parse-batch/key-fields` | Parse multiple files, key fields only |
| GET | `/api/documents/health` | Check API + Ollama status |

Interactive API docs available at **http://127.0.0.1:8000/docs**

### Example Request
```bash
curl -X POST http://127.0.0.1:8000/api/documents/parse/key-fields \
  -F "file=@invoice.pdf"
```

### Example Response
```json
{
  "success": true,
  "filename": "NV15357_CHN.pdf",
  "key_fields": {
    "filename": "NV15357_CHN.pdf",
    "mbl_or_invoice_no": "YMJAW490498450",
    "container_nos": ["FFAU1289797"],
    "total_amount": "785.00",
    "currency": "USD"
  }
}
```

---

## Project Structure
```
freight-doc-parser/
├── app/
│   ├── main.py                        # FastAPI app entry point
│   ├── routers/
│   │   └── documents.py               # API endpoints
│   ├── services/
│   │   ├── pdf_extractor.py           # pdfplumber + OCR fallback
│   │   └── llm_parser.py              # Ollama + regex fallback
│   └── schemas/
│       └── document.py                # Pydantic models
├── static/
│   └── index.html                     # Web UI
├── requirements.txt
├── .env.example
└── .gitignore
```

## Parsing Flow
```
Upload PDF / Image
       ↓
pdf_extractor.py
  ├─ pdfplumber → text-based PDF ✓
  └─ OCR fallback → scanned PDF / image
       ↓
llm_parser.py
  ├─ Ollama llama3.2 → structured JSON
  └─ Regex fallback → Ollama offline
       ↓
ParsedDocument (Pydantic)
       ↓
JSON API Response
```

---

## Roadmap

- [ ] Export results to CSV / Excel
- [ ] PostgreSQL storage (SQLAlchemy 2.0)
- [ ] Claude Vision API for low-quality scans
- [ ] Traditional Chinese document support
- [ ] Async batch processing for faster throughput

---

## License

MIT
