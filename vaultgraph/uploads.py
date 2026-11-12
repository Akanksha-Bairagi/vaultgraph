"""Upload validation: allow-listed types, magic-byte check, size/page caps, no executable content ever stored raw."""
import io
import os

from . import config
from .errors import Invalid

ALLOWED = (".pdf", ".txt", ".md")
MAX_TEXT_CHARS = 200_000


def safe_title(filename: str) -> str:
    base = os.path.basename((filename or "upload").replace("\\", "/"))
    return "".join(ch for ch in base if ch.isprintable())[:200] or "upload"


def extract_text(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if not name.endswith(ALLOWED):
        raise Invalid("Unsupported file type. Upload a .pdf, .txt or .md file.")
    if not data:
        raise Invalid("The file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise Invalid(f"File too large (limit {config.MAX_UPLOAD_BYTES // 1024} KB).")
    if name.endswith(".pdf"):
        if not data[:1024].lstrip().startswith(b"%PDF-"):
            raise Invalid("This file is not a valid PDF.")
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise Invalid("Encrypted PDFs are not supported.")
            if len(reader.pages) > config.MAX_PDF_PAGES:
                raise Invalid(f"PDF has too many pages (limit {config.MAX_PDF_PAGES}).")
            text = "\n\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Invalid:
            raise
        except Exception:
            raise Invalid("Could not read this PDF (it may be corrupted).") from None
    else:
        if b"\x00" in data:
            raise Invalid("Text files must not contain binary data.")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise Invalid("Text files must be UTF-8 encoded.") from None
    text = text.replace("\x00", "").strip()
    if not text:
        raise Invalid("No extractable text found (scanned PDFs need OCR, which is not supported).")
    if len(text) > MAX_TEXT_CHARS:
        raise Invalid(f"Document too long ({len(text):,} characters; limit {MAX_TEXT_CHARS:,}).")
    return text
