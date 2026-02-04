"""
Epstein Document Archive - Main Pipeline
Extracts zips, classifies PDFs, and indexes to SQLite databases

Usage:
    python pipeline/sort_and_index.py
"""
import zipfile
import sqlite3
import shutil
import sys
from pathlib import Path
from datetime import datetime
import time

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db_setup import init_databases
from utils import (
    calculate_checksum,
    is_text_pdf,
    extract_pdf_text,
    get_file_type,
    safe_filename,
    pdf_first_page_contains
)


# Configuration
ZIP_SOURCE = Path(r"C:\Users\JonathanSMcFarland\epstein-files-downloader\zips")
PROJECT_ROOT = Path(r"C:\Users\JonathanSMcFarland\EpsteinLawyer")

RAW_DIR = PROJECT_ROOT / "raw"
TEXT_DOCS_DIR = PROJECT_ROOT / "text-docs"
IMAGES_DIR = PROJECT_ROOT / "images"
DB_DIR = PROJECT_ROOT / "db"

# Verbose progress settings
VERBOSE = True
CLASSIFY_PROGRESS_EVERY = 500
INDEX_TEXT_PROGRESS_EVERY = 50
INDEX_IMAGE_PROGRESS_EVERY = 200
BLANK_IMAGE_PROGRESS_EVERY = 200
NO_IMAGES_PHRASE = "No Images Produced"


def setup_directories() -> None:
    """Create output directories if they don't exist."""
    for directory in [RAW_DIR, TEXT_DOCS_DIR, IMAGES_DIR, DB_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory ready: {directory}")


def extract_all_zips() -> int:
    """Extract all zip files from source to raw/ directory."""
    if not ZIP_SOURCE.exists():
        print(f"ERROR: Zip source not found: {ZIP_SOURCE}")
        sys.exit(1)
    
    # If raw already has files, skip extraction to save time
    if any(RAW_DIR.iterdir()):
        print("\nRaw directory already contains files. Skipping zip extraction.")
        return 0

    zip_files = list(ZIP_SOURCE.glob("*.zip"))
    print(f"\nFound {len(zip_files)} zip files to extract")
    
    total_extracted = 0
    for zip_path in zip_files:
        print(f"  Extracting: {zip_path.name}...", end=" ")
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Extract to a subdirectory named after the zip
                extract_dir = RAW_DIR / zip_path.stem
                extract_dir.mkdir(exist_ok=True)
                zf.extractall(extract_dir)
                count = len(zf.namelist())
                total_extracted += count
                print(f"{count} files")
        except Exception as e:
            print(f"FAILED: {e}")
    
    print(f"✓ Total files extracted: {total_extracted}")
    return total_extracted


def classify_and_sort() -> tuple[int, int, int]:
    """
    Classify all files in raw/ and sort into text-docs/ or images/.
    Returns (text_count, image_pdf_count, image_file_count)
    """
    text_count = 0
    image_pdf_count = 0
    image_file_count = 0
    
    print("\nClassifying files...")
    
    # Walk through all extracted files
    all_files = [p for p in RAW_DIR.rglob("*") if p.is_file()]
    total_target = len(all_files)
    total_files = 0
    start_time = time.time()

    # If everything already classified, skip
    if total_target > 0 and (len(list(TEXT_DOCS_DIR.iterdir())) + len(list(IMAGES_DIR.iterdir())) >= total_target):
        print("\nClassification appears complete. Skipping classify step.")
        return 0, 0, 0
    for filepath in all_files:
        if not filepath.is_file():
            continue

        total_files += 1
        if VERBOSE and total_files % CLASSIFY_PROGRESS_EVERY == 0:
            elapsed = max(time.time() - start_time, 0.001)
            rate = total_files / elapsed
            remaining = max(total_target - total_files, 0)
            eta_seconds = int(remaining / rate) if rate > 0 else 0
            print(
                "  Processed {files}/{total} | Text PDFs: {text} | Scanned PDFs: {scanned} | Images: {images} | ETA: {eta}s".format(
                    files=total_files,
                    total=total_target,
                    text=text_count,
                    scanned=image_pdf_count,
                    images=image_file_count,
                    eta=eta_seconds
                )
            )
        
        file_type = get_file_type(filepath)
        
        # Generate unique filename to avoid collisions
        rel_path = filepath.relative_to(RAW_DIR)
        safe_name = safe_filename(str(rel_path).replace("\\", "_").replace("/", "_"))
        text_dest = TEXT_DOCS_DIR / safe_name
        image_dest = IMAGES_DIR / safe_name

        # Skip if already classified
        if text_dest.exists() or image_dest.exists():
            continue
        
        if file_type == "pdf":
            if is_text_pdf(filepath):
                # Text-extractable PDF
                shutil.copy2(filepath, text_dest)
                text_count += 1
            else:
                # Image/scanned PDF
                shutil.copy2(filepath, image_dest)
                image_pdf_count += 1
                
        elif file_type == "image":
            # Direct image files
            shutil.copy2(filepath, image_dest)
            image_file_count += 1
    
    print(f"✓ Text PDFs: {text_count}")
    print(f"✓ Image/Scanned PDFs: {image_pdf_count}")
    print(f"✓ Image files: {image_file_count}")
    
    return text_count, image_pdf_count, image_file_count


def index_text_documents(db_path: Path) -> int:
    """Index all text documents into SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    indexed = 0
    print("\nIndexing text documents...")
    
    text_files = list(TEXT_DOCS_DIR.glob("*.pdf"))
    total_target = len(text_files)
    start_time = time.time()

    # Skip if already indexed
    cursor.execute("SELECT COUNT(*) FROM documents")
    existing_docs = cursor.fetchone()[0]
    if total_target > 0 and existing_docs >= total_target:
        print("\nText documents already indexed. Skipping index step.")
        conn.close()
        return 0
    for pdf_path in text_files:
        # Check if already indexed
        cursor.execute("SELECT id FROM documents WHERE filepath = ?", (str(pdf_path),))
        if cursor.fetchone():
            continue
        
        checksum = calculate_checksum(pdf_path)
        
        # Check for duplicate by checksum
        cursor.execute("SELECT id FROM documents WHERE checksum = ?", (checksum,))
        if cursor.fetchone():
            print(f"  Skipping duplicate: {pdf_path.name}")
            continue
        
        # Insert document record
        cursor.execute(
            "INSERT INTO documents (filename, filepath, checksum) VALUES (?, ?, ?)",
            (pdf_path.name, str(pdf_path), checksum)
        )
        doc_id = cursor.lastrowid
        
        # Extract and index text content
        pages = extract_pdf_text(pdf_path)
        for page_num, text in pages.items():
            cursor.execute(
                "INSERT INTO content (document_id, page_number, extracted_text) VALUES (?, ?, ?)",
                (doc_id, page_num, text)
            )
        
        indexed += 1
        if VERBOSE and indexed % INDEX_TEXT_PROGRESS_EVERY == 0:
            elapsed = max(time.time() - start_time, 0.001)
            rate = indexed / elapsed
            remaining = max(total_target - indexed, 0)
            eta_seconds = int(remaining / rate) if rate > 0 else 0
            print(f"  Indexed {indexed}/{total_target} documents | ETA: {eta_seconds}s...")
            conn.commit()
    
    conn.commit()
    conn.close()
    print(f"✓ Indexed {indexed} text documents")
    return indexed


def index_images(db_path: Path) -> int:
    """Index all image files and scanned PDFs into SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    indexed = 0
    print("\nIndexing images...")
    
    image_files = [p for p in IMAGES_DIR.iterdir() if p.is_file()]
    total_target = len(image_files)
    start_time = time.time()

    # Skip if already indexed
    cursor.execute("SELECT COUNT(*) FROM images")
    existing_images = cursor.fetchone()[0]
    if total_target > 0 and existing_images >= total_target:
        print("\nImages already indexed. Skipping index step.")
        conn.close()
        return 0
    for filepath in image_files:
        if not filepath.is_file():
            continue
        
        # Check if already indexed
        cursor.execute("SELECT id FROM images WHERE filepath = ?", (str(filepath),))
        if cursor.fetchone():
            continue
        
        checksum = calculate_checksum(filepath)
        
        # Check for duplicate by checksum
        cursor.execute("SELECT id FROM images WHERE checksum = ?", (checksum,))
        if cursor.fetchone():
            print(f"  Skipping duplicate: {filepath.name}")
            continue
        
        # Determine source type
        source_type = "scanned_pdf" if filepath.suffix.lower() == ".pdf" else "image"
        
        cursor.execute(
            "INSERT INTO images (filename, filepath, checksum, source_type) VALUES (?, ?, ?, ?)",
            (filepath.name, str(filepath), checksum, source_type)
        )
        
        indexed += 1
        if VERBOSE and indexed % INDEX_IMAGE_PROGRESS_EVERY == 0:
            elapsed = max(time.time() - start_time, 0.001)
            rate = indexed / elapsed
            remaining = max(total_target - indexed, 0)
            eta_seconds = int(remaining / rate) if rate > 0 else 0
            print(f"  Indexed {indexed}/{total_target} images | ETA: {eta_seconds}s...")
            conn.commit()
    
    conn.commit()
    conn.close()
    print(f"✓ Indexed {indexed} images")
    return indexed


def cleanup_blank_images(db_path: Path) -> int:
    """Remove PDFs whose first page contains 'No Images Produced'."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT id, filepath FROM images")
    rows = cursor.fetchall()
    total_target = len(rows)
    if total_target == 0:
        conn.close()
        return 0

    print("\nCleaning up PDFs with 'No Images Produced'...")
    deleted = 0
    processed = 0
    start_time = time.time()

    for image_id, filepath_str in rows:
        processed += 1
        filepath = Path(filepath_str)
        if not filepath.exists():
            cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
            deleted += 1
            continue

        if filepath.suffix.lower() == ".pdf" and pdf_first_page_contains(filepath, NO_IMAGES_PHRASE):
            try:
                filepath.unlink(missing_ok=True)
            except Exception:
                pass
            cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
            deleted += 1
            continue

        if VERBOSE and processed % BLANK_IMAGE_PROGRESS_EVERY == 0:
            elapsed = max(time.time() - start_time, 0.001)
            rate = processed / elapsed
            remaining = max(total_target - processed, 0)
            eta_seconds = int(remaining / rate) if rate > 0 else 0
            print(f"  Scanned {processed}/{total_target} images | Deleted: {deleted} | ETA: {eta_seconds}s...")
            conn.commit()

    conn.commit()
    conn.close()
    print(f"✓ Deleted {deleted} PDFs containing '{NO_IMAGES_PHRASE}'")
    return deleted


def print_summary(text_db: Path, images_db: Path) -> None:
    """Print summary of indexed content."""
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print("="*60)
    
    # Text database stats
    conn = sqlite3.connect(text_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    doc_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM content")
    page_count = cursor.fetchone()[0]
    conn.close()
    
    # Images database stats
    conn = sqlite3.connect(images_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM images")
    img_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM images WHERE source_type = 'scanned_pdf'")
    scanned_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\nText Documents Database ({text_db}):")
    print(f"  - Documents: {doc_count}")
    print(f"  - Total pages indexed: {page_count}")
    
    print(f"\nImages Database ({images_db}):")
    print(f"  - Total entries: {img_count}")
    print(f"  - Scanned PDFs: {scanned_count}")
    print(f"  - Image files: {img_count - scanned_count}")
    
    print("\n" + "="*60)
    print("READY FOR QUERIES")
    print("="*60)
    print("\nSearch text documents:")
    print(f'  sqlite3 "{text_db}" "SELECT d.filepath, c.page_number, substr(c.extracted_text, 1, 200) FROM content c JOIN documents d ON c.document_id = d.id WHERE c.extracted_text LIKE \'%SEARCH_TERM%\' LIMIT 10;"')
    print("\nList all images:")
    print(f'  sqlite3 "{images_db}" "SELECT filename, source_type FROM images LIMIT 20;"')


def main():
    """Main pipeline execution."""
    start_time = datetime.now()
    print("="*60)
    print("EPSTEIN DOCUMENT ARCHIVE PIPELINE")
    print(f"Started: {start_time}")
    print("="*60)
    
    # Step 1: Setup directories
    setup_directories()
    
    # Step 2: Initialize databases
    text_db, images_db = init_databases(DB_DIR)
    
    # Step 3: Extract all zip files
    extract_all_zips()
    
    # Step 4: Classify and sort files
    classify_and_sort()
    
    # Step 5: Index text documents
    index_text_documents(text_db)
    
    # Step 6: Index images
    index_images(images_db)
    
    # Step 7: Cleanup blank images
    cleanup_blank_images(images_db)

    # Step 8: Print summary
    print_summary(text_db, images_db)
    
    elapsed = datetime.now() - start_time
    print(f"\nTotal time: {elapsed}")


if __name__ == "__main__":
    main()
