"""Resume version registry.

Manages discovery and resolution of resume variants located under the resumes/ directory.
"""

from __future__ import annotations

from pathlib import Path


def list_resume_versions() -> list[str]:
    """Return list of available resume stems under the resumes/ directory."""
    resumes_dir = Path("resumes")
    if not resumes_dir.exists():
        return []

    stems = set()
    for ext in ("*.pdf", "*.txt"):
        for p in resumes_dir.glob(ext):
            if p.is_file():
                stems.add(p.stem)
    return sorted(list(stems))


def resolve_resume_version(label: str) -> Path:
    """Resolve a resume version label to a file Path.

    Raises ValueError if no matching file can be resolved.
    """
    resumes_dir = Path("resumes")
    
    # 1. Try direct file matching
    # If the user supplied an extension or a specific filename in resumes/
    direct_path = resumes_dir / label
    if direct_path.exists() and direct_path.is_file():
        return direct_path

    # 2. Try matching stem to PDF or TXT
    pdf_path = resumes_dir / f"{label}.pdf"
    if pdf_path.exists() and pdf_path.is_file():
        return pdf_path

    txt_path = resumes_dir / f"{label}.txt"
    if txt_path.exists() and txt_path.is_file():
        return txt_path

    # 3. Fail with clear list of available versions
    versions = list_resume_versions()
    versions_str = ", ".join(f"'{v}'" for v in versions) if versions else "None found"
    raise ValueError(
        f"Resume version '{label}' not found under resumes/ directory.\n"
        f"Available versions: {versions_str}"
    )
