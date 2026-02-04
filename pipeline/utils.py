"""
Utility functions for Epstein Document Archive
- Checksum calculation
- PDF classification (text vs image/scanned)
- File extraction helpers
"""
import hashlib
import subprocess
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Literal

from PIL import Image


def calculate_checksum(filepath: Path, algorithm: str = "md5") -> str:
    """Calculate file checksum for deduplication."""
    hash_func = hashlib.new(algorithm)
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def resolve_poppler_binary(binary_name: str) -> str:
    """Resolve poppler binary from PATH or default install location."""
    # Prefer PATH
    path_binary = shutil.which(binary_name)
    if path_binary:
        return path_binary

    # Fallback to default Windows install
    default_path = Path(r"C:\Program Files\poppler\Library\bin") / binary_name
    if default_path.exists():
        return str(default_path)

    return binary_name  # Let subprocess raise if not found


def render_pdf_first_page(pdf_path: Path) -> Image.Image | None:
    """Render the first page of a PDF to a PIL image using pdftoppm."""
    try:
        pdftoppm = resolve_poppler_binary("pdftoppm")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_prefix = Path(temp_dir) / "page"
            subprocess.run(
                [
                    pdftoppm,
                    "-f", "1",
                    "-l", "1",
                    "-singlefile",
                    "-png",
                    str(pdf_path),
                    str(output_prefix)
                ],
                capture_output=True,
                timeout=60
            )
            output_file = output_prefix.with_suffix(".png")
            if not output_file.exists():
                return None
            return Image.open(output_file)
    except Exception:
        return None


def is_blank_image(filepath: Path, black_threshold: int = 10, black_ratio: float = 0.98) -> bool:
    """Detect near-blank images by measuring percentage of black pixels."""
    image = None
    if filepath.suffix.lower() == ".pdf":
        image = render_pdf_first_page(filepath)
    else:
        try:
            image = Image.open(filepath)
        except Exception:
            return False

    if image is None:
        return False

    try:
        grayscale = image.convert("L")
        histogram = grayscale.histogram()
        total_pixels = sum(histogram)
        black_pixels = sum(histogram[: black_threshold + 1])
        if total_pixels == 0:
            return False
        return (black_pixels / total_pixels) >= black_ratio
    except Exception:
        return False


def is_text_pdf(pdf_path: Path, char_threshold: int = 100, max_pages: int = 5) -> bool:
    """
    Classify PDF as text-extractable or image/scanned.
    
    Uses pdftotext to extract up to max_pages. If character count > threshold,
    it's a text PDF. Otherwise, it's likely scanned/image-based.
    
    Args:
        pdf_path: Path to PDF file
        char_threshold: Minimum chars to classify as text PDF (default 100)
        max_pages: Number of pages to scan (default 5)
    
    Returns:
        True if text-extractable, False if image/scanned
    """
    try:
        total_chars = 0
        # Extract up to max_pages and sum characters
        pdftotext = resolve_poppler_binary("pdftotext")
        for page_num in range(1, max_pages + 1):
            result = subprocess.run(
                [pdftotext, "-f", str(page_num), "-l", str(page_num), str(pdf_path), "-"],
                capture_output=True,
                timeout=30
            )
            # Decode safely to avoid UnicodeDecodeError from Windows cp1252
            output_text = result.stdout.decode("utf-8", errors="ignore")
            total_chars += len(output_text.strip())
            if total_chars > char_threshold:
                return True
        return total_chars > char_threshold
    except FileNotFoundError:
        print("ERROR: pdftotext not found. Install poppler-utils.")
        print("See README.md for installation instructions.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        # If it times out, treat as image (might be huge scanned doc)
        return False
    except Exception as e:
        print(f"Warning: Could not classify {pdf_path}: {e}")
        return False


def extract_pdf_text(pdf_path: Path) -> dict[int, str]:
    """
    Extract text from all pages of a PDF.
    
    Returns:
        Dict mapping page_number -> extracted_text
    """
    pages = {}
    try:
        # First get page count
        pdfinfo = resolve_poppler_binary("pdfinfo")
        result = subprocess.run(
            [pdfinfo, str(pdf_path)],
            capture_output=True,
            timeout=30
        )
        page_count = 1
        info_text = result.stdout.decode("utf-8", errors="ignore")
        for line in info_text.split("\n"):
            if line.startswith("Pages:"):
                page_count = int(line.split(":")[1].strip())
                break
        
        # Extract each page
        for page_num in range(1, page_count + 1):
            pdftotext = resolve_poppler_binary("pdftotext")
            result = subprocess.run(
                [pdftotext, "-f", str(page_num), "-l", str(page_num), str(pdf_path), "-"],
                capture_output=True,
                timeout=60
            )
            text = result.stdout.decode("utf-8", errors="ignore").strip()
            if text:
                pages[page_num] = text
                
    except FileNotFoundError:
        print("ERROR: pdftotext/pdfinfo not found. Install poppler-utils.")
        sys.exit(1)
    except Exception as e:
        print(f"Warning: Could not extract text from {pdf_path}: {e}")
    
    return pages


def get_file_type(filepath: Path) -> Literal["pdf", "image", "other"]:
    """Determine file type based on extension."""
    ext = filepath.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    elif ext in [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp"]:
        return "image"
    else:
        return "other"


def safe_filename(filename: str) -> str:
    """Create safe filename by replacing problematic characters."""
    # Replace characters that might cause issues
    for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
        filename = filename.replace(char, '_')
    return filename
