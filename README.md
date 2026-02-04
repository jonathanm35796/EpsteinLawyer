# Epstein Document Archive

A Python pipeline to extract, classify, and index PDF documents from the Epstein files archive.

**Created:** 2026-02-03  
**Author:** Jonathan + Sales Tax

---

## Overview

This pipeline:
1. **Extracts** 12 zip files containing PDF documents
2. **Classifies** each PDF as text-extractable or image/scanned (without viewing)
3. **Indexes** text PDFs into a searchable SQLite database
4. **Stores** image/scanned PDFs and images in a separate database for future OCR

### Token Safety
- Images never enter the context window
- Only extracted TEXT is stored in SQLite
- Queries return filepath + snippet
- Images analyzed only if deliberately chosen (one at a time)

---

## Prerequisites

### Install Poppler (Required)

Poppler provides `pdftotext` and `pdfinfo` for PDF text extraction.

**Windows (using Chocolatey):**
```powershell
# Install Chocolatey first if you don't have it:
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Then install poppler:
choco install poppler -y
```

**Windows (Manual):**
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\Program Files\poppler`
3. Add `C:\Program Files\poppler\Library\bin` to your PATH

**Verify installation:**
```powershell
pdftotext -v
```

### Install Tesseract (Optional - for future OCR)

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
├── db/
│   ├── text_docs.sqlite     # Searchable text database
│   └── images.sqlite        # Image metadata database
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Run the Pipeline

```powershell
cd C:\Users\JonathanSMcFarland\EpsteinLawyer
python pipeline/sort_and_index.py
```

This will:
- Extract all zips from `C:\Users\JonathanSMcFarland\epstein-files-downloader\zips`
- Classify each PDF (text vs image)
- Index text documents into `db/text_docs.sqlite`
- Store image references in `db/images.sqlite`

---

## Web Search UI (Flask)

Install dependencies:
```powershell
pip install -r requirements.txt
```

Run the web app:
```powershell
set APP_USER=bros
set APP_PASS=homies
python app.py
```

Then open:
```
http://127.0.0.1:8080
```

---

## Internet Access (Tunnel + Basic Auth)

### Option 1: Ngrok (Recommended)
1) Install ngrok: https://ngrok.com/download
2) Start the app (as above)
3) In a new terminal, run:
```powershell
ngrok http 8080
```
4) Use the forwarded HTTPS URL provided by ngrok
5) Browser will prompt for **Basic Auth** (username/password above)

### Option 2: Cloudflare Tunnel
You can also use Cloudflare Tunnel if you prefer a free persistent URL.
Let me know and I’ll add the full steps.

---

## Querying the Database

### Search Text Documents

```powershell
# Search for a term (e.g., "flight")
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\text_docs.sqlite" "SELECT d.filepath, c.page_number, substr(c.extracted_text, 1, 300) FROM content c JOIN documents d ON c.document_id = d.id WHERE c.extracted_text LIKE '%flight%' LIMIT 10;"
```

### List All Text Documents

```powershell
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\text_docs.sqlite" "SELECT id, filename FROM documents LIMIT 20;"
```

### List All Images

```powershell
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\images.sqlite" "SELECT filename, source_type FROM images LIMIT 20;"
```

### Get Full Page Content

```powershell
# Get document ID first, then:
sqlite3 "C:\Users\JonathanSMcFarland\EpsteinLawyer\db\text_docs.sqlite" "SELECT extracted_text FROM content WHERE document_id = 1 AND page_number = 1;"
```

---

## Database Schema

### text_docs.sqlite

```sql
-- Document metadata
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    filepath TEXT UNIQUE,
    checksum TEXT,
    created_at TIMESTAMP
);

-- Page content (searchable)
CREATE TABLE content (
    id INTEGER PRIMARY KEY,
    document_id INTEGER,
    page_number INTEGER,
    extracted_text TEXT
);

-- Full-text search index
CREATE INDEX idx_content_text ON content(extracted_text);
```

### images.sqlite

```sql
-- Image/scanned PDF metadata
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    filepath TEXT UNIQUE,
    checksum TEXT,
    processed INTEGER DEFAULT 0,
    source_type TEXT  -- 'scanned_pdf' or 'image'
);

-- Ready for future OCR
CREATE TABLE ocr_content (
    id INTEGER PRIMARY KEY,
    image_id INTEGER,
    ocr_text TEXT
);

-- Ready for future AI descriptions
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

## Future Extensions

1. **OCR Processing**: Run Tesseract on scanned PDFs
2. **AI Descriptions**: Generate descriptions for images
3. **Full-Text Search**: Upgrade to SQLite FTS5 for faster searches
4. **Web Interface**: Build a simple search UI

---

## Troubleshooting

### "pdftotext not found"
Install poppler (see Prerequisites above) and ensure it's in your PATH.

### "Permission denied"
Run PowerShell as Administrator or check file permissions.

### "Zip file not found"
Verify the zip files exist at:
`C:\Users\JonathanSMcFarland\epstein-files-downloader\zips`

---

## License

For research and educational purposes only.
