"""
Database setup for Epstein Document Archive
Creates text_docs.sqlite and images.sqlite with proper schema
"""
import sqlite3
import os
from pathlib import Path


def setup_text_db(db_path: Path) -> None:
    """Create text_docs.sqlite with documents and content tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            checksum TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            page_number INTEGER,
            extracted_text TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_text ON content(extracted_text)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename)")
    
    conn.commit()
    conn.close()
    print(f"✓ Created text database: {db_path}")


def setup_images_db(db_path: Path) -> None:
    """Create images.sqlite with images, ocr_content, and descriptions tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL UNIQUE,
            checksum TEXT,
            processed INTEGER DEFAULT 0,
            source_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Ready for future OCR
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ocr_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            ocr_text TEXT,
            FOREIGN KEY (image_id) REFERENCES images(id)
        )
    """)
    
    # Ready for future AI descriptions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS descriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            description TEXT,
            FOREIGN KEY (image_id) REFERENCES images(id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ocr_text ON ocr_content(ocr_text)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_filename ON images(filename)")
    
    conn.commit()
    conn.close()
    print(f"✓ Created images database: {db_path}")


def init_databases(db_dir: Path) -> tuple:
    """Initialize both databases and return their paths."""
    db_dir.mkdir(parents=True, exist_ok=True)
    
    text_db = db_dir / "text_docs.sqlite"
    images_db = db_dir / "images.sqlite"
    
    setup_text_db(text_db)
    setup_images_db(images_db)
    
    return text_db, images_db


if __name__ == "__main__":
    # Test database creation
    db_dir = Path(__file__).parent.parent / "db"
    init_databases(db_dir)
