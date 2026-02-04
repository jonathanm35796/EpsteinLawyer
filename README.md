# Epstein Document Archive

A Python pipeline and Flask UI to extract, classify, index, and query the Epstein files archive.

**Created:** 2026-02-03  
**Author:** Jonathan + Sales Tax

---

## Overview

This project:
1. **Extracts** zip archives containing PDFs and images.
2. **Classifies** PDFs into text vs scanned/image-based without viewing contents.
3. **Indexes** text PDFs into a searchable SQLite database.
4. **Stores** scanned PDFs/images in a separate database for OCR/vision later.
5. **Exposes** a Flask UI + REST API for querying and AI integration.

### Token Safety
- Images never enter the context window.
- Only extracted TEXT is stored in SQLite.
- Queries return filepath + snippet.
- Images are analyzed only if deliberately chosen (one at a time).

---

## Prerequisites

### Python Dependencies

```powershell
pip install -r requirements.txt
```

### Poppler (Required)

Poppler provides `pdftotext` and `pdfinfo` for PDF text extraction.

**Windows (Chocolatey):**
```powershell
# Install Chocolatey if needed
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Poppler
choco install poppler -y
```

**Windows (Manual):**
1. Download: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler`
3. Add `C:\Program Files\poppler\Library\bin` to your PATH

**Verify:**
```powershell
pdftotext -v
```

### Tesseract (Optional, for future OCR)
```powershell
choco install tesseract -y
```

---

## Project Structure

```
C:\Users\JonathanSMcFarland\EpsteinLawyer\
├── pipeline/
│   ├── sort_and_index.py    # Main pipeline script
│   ├── db_setup.py          # Database schema setup
│   └── utils.py             # Helper functions
├── raw/                     # Extracted files from zips
├── text-docs/               # Text-extractable PDFs
├── images/                  # Scanned PDFs + image files
├── icons/                   # UI icons
├── db/
│   ├── text_docs.sqlite     # Searchable text database
│   └── images.sqlite        # Image metadata database
├── app.py                   # Flask UI + REST API
├── requirements.txt
└── README.md
```

---

## Quick Start (Pipeline)

```powershell
cd C:\Users\JonathanSMcFarland\EpsteinLawyer
python pipeline/sort_and_index.py
```

**What it does:**
- Extracts zips from `C:\Users\JonathanSMcFarland\epstein-files-downloader\zips`
- Classifies PDFs as text vs image/scanned
- Indexes text into `db/text_docs.sqlite`
- Stores image metadata in `db/images.sqlite`

---

## Web UI (Flask)

### Run the app
```powershell
set APP_USER=bros
set APP_PASS=homies
python app.py
```

Open:
```
http://127.0.0.1:8080
```

### Notes
- Basic Auth is enabled (uses APP_USER/APP_PASS).
- Search results now use **doc_id-based links** (no raw Windows paths).

---

## REST API (for AI tools)

All endpoints require Basic Auth.

### 1) Search
```
GET /api/search?q=bill+gates&page=1&per_page=50
```
Response:
```json
{
  "query": "bill gates",
  "total_results": 3,
  "page": 1,
  "per_page": 50,
  "results": [
    {
      "doc_id": 12345,
      "filepath": "...EFTA02730265.pdf",
      "page": 1,
      "snippet": "..."
    }
  ]
}
```

### 2) Batch Search
```
POST /api/search/batch
```
Body:
```json
{ "names": ["bill gates", "ghislaine maxwell"] }
```
Response:
```json
{
  "results": {
    "bill gates": [ ... ],
    "ghislaine maxwell": [ ... ]
  }
}
```

### 3) Stats
```
GET /api/stats
```
Response:
```json
{
  "total_docs": 1234,
  "total_pages": 45678,
  "total_images": 890
}
```

### 4) Full Text by Document
```
GET /api/text/<doc_id>
```
Response:
```json
{
  "doc_id": 12345,
  "filepath": "...EFTA02730265.pdf",
  "pages": [
    { "page": 1, "text": "..." },
    { "page": 2, "text": "..." }
  ]
}
```

---

## Direct SQLite Queries

### Search Text Documents
```powershell
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\text_docs.sqlite" "SELECT d.filepath, c.page_number, substr(c.extracted_text, 1, 300) FROM content c JOIN documents d ON c.document_id = d.id WHERE c.extracted_text LIKE '%flight%' LIMIT 10;"
```

### List Documents
```powershell
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\text_docs.sqlite" "SELECT id, filename FROM documents LIMIT 20;"
```

### List Images
```powershell
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\images.sqlite" "SELECT filename, source_type FROM images LIMIT 20;"
```

---

## Database Schema

### text_docs.sqlite
```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    filepath TEXT UNIQUE,
    checksum TEXT,
    created_at TIMESTAMP
);

CREATE TABLE content (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    page_number INTEGER,
    extracted_text TEXT
);

CREATE INDEX idx_content_text ON content(extracted_text);
```

### images.sqlite
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    filepath TEXT UNIQUE,
    checksum TEXT,
    processed INTEGER DEFAULT 0,
    source_type TEXT
);

CREATE TABLE ocr_content (
    id INTEGER PRIMARY KEY,
    image_id INTEGER,
    ocr_text TEXT
);

CREATE TABLE descriptions (
    id INTEGER PRIMARY KEY,
    image_id INTEGER,
    description TEXT
);
```

---

## Workflow

```
ZIP FILES → EXTRACT → CLASSIFY → SORT → INDEX
                          ↓
                    text? ─────→ text-docs/ → text_docs.sqlite
                          ↓
                    image? ────→ images/    → images.sqlite
```

---

## Troubleshooting

### "pdftotext not found"
Install Poppler and ensure `pdftotext` is in your PATH.

### "Zip file not found"
Verify zips exist at:
`C:\Users\JonathanSMcFarland\epstein-files-downloader\zips`

---

## License

For research and educational purposes only.