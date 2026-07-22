"""Resume parser and AI feature extractor converting document files to CandidateProfile."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from pypdf import PdfReader

from app.recommendation.profile import CandidateProfile

if TYPE_CHECKING:
    from app.ai.gateway import AiGateway


class ResumeParser:
    """Parses resume documents and uses the AI Gateway to build CandidateProfiles."""

    @staticmethod
    def extract_text(path: Path) -> str:
        """Extract plain text from PDF, DOCX, MD, and TXT resume files."""
        if not path.exists():
            raise FileNotFoundError(f"Resume file not found at: {path}")

        ext = path.suffix.lower()

        if ext in (".txt", ".md"):
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

        elif ext == ".docx":
            try:
                with zipfile.ZipFile(path) as docx:
                    xml_content = docx.read("word/document.xml")
                    root = ET.fromstring(xml_content)
                    
                    # Group by w:p (paragraph) tags to retain basic sentence structures
                    paragraphs = []
                    for elem in root.iter():
                        # Paragraph tag
                        if elem.tag.endswith("p"):
                            p_texts = []
                            for child in elem.iter():
                                if child.tag.endswith("t") and child.text:
                                    p_texts.append(child.text)
                            if p_texts:
                                paragraphs.append("".join(p_texts))
                    
                    return "\n".join(paragraphs)
            except Exception as exc:
                raise ValueError(f"Failed to parse DOCX resume at {path}: {exc}") from exc

        else:
            raise ValueError(
                f"Unsupported resume extension '{ext}'. Only .txt, .md, .pdf, and .docx files are supported."
            )

    @classmethod
    def parse(cls, path: Path, gateway: AiGateway) -> CandidateProfile:
        """Parse raw resume text and extract structured CandidateProfile via LLM."""
        raw_text = cls.extract_text(path)

        try:
            raw_response = gateway.complete(
                prompt_id="resume_parse.v1",
                user_content=raw_text,
                temperature=0.2,
                use_cache=True,
            )
            
            if not raw_response:
                raise ValueError("LLM returned empty candidate profile response.")

            # Cleanup markdown fences if present
            from app.ai import clean_json_content
            cleaned = clean_json_content(raw_response)

            data = json.loads(cleaned)
            return CandidateProfile.model_validate(data)

        except Exception as exc:
            logger.error("resume_parser: failed to parse profile via LLM - {exc}", exc=exc)
            # Graceful fallback to default/empty profile
            return CandidateProfile()
