"""Resume parser helper to extract raw text content from TXT and PDF formats."""

from __future__ import annotations

from pathlib import Path
from pypdf import PdfReader


def load_resume_text(path: Path) -> str:
    """Load text content from a PDF or plain text resume.

    Supports .txt and .pdf file formats (case-insensitive extension check).
    Raises ValueError for unsupported formats.
    """
    if not path.exists():
        raise FileNotFoundError(f"Resume file not found at: {path}")

    ext = path.suffix.lower()
    if ext == ".txt":
        return path.read_text(encoding="utf-8")
    elif ext == ".pdf":
        try:
            reader = PdfReader(path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except Exception as exc:
            raise ValueError(f"Failed to parse PDF resume at {path}: {exc}") from exc
    else:
        raise ValueError(
            f"Unsupported resume file extension: '{ext}'. Only .txt and .pdf files are supported."
        )
