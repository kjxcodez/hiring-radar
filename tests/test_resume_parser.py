"""Unit tests for the Resume Parser and docx/pdf text extraction."""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from app.recommendation.resume import ResumeParser


def test_resume_parser_txt_and_md(tmp_path: Path):
    txt_path = tmp_path / "resume.txt"
    txt_path.write_text("Hello Python Developer", encoding="utf-8")
    assert ResumeParser.extract_text(txt_path) == "Hello Python Developer"

    md_path = tmp_path / "resume.md"
    md_path.write_text("# Python Developer", encoding="utf-8")
    assert ResumeParser.extract_text(md_path) == "# Python Developer"


def test_resume_parser_docx(tmp_path: Path):
    docx_path = tmp_path / "resume.docx"
    with zipfile.ZipFile(docx_path, "w") as docx:
        xml_text = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            '  <w:body>\n'
            '    <w:p>\n'
            '      <w:r>\n'
            '        <w:t>Full Stack Engineer</w:t>\n'
            '      </w:r>\n'
            '    </w:p>\n'
            '  </w:body>\n'
            '</w:document>'
        )
        docx.writestr("word/document.xml", xml_text)

    assert ResumeParser.extract_text(docx_path) == "Full Stack Engineer"


def test_resume_parser_ai_enrichment():
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "skills": ["python", "fastapi"],'
        '  "technologies": ["aws"],'
        '  "years_experience": 4.5,'
        '  "preferred_roles": ["backend developer"],'
        '  "preferred_locations": ["SF"],'
        '  "remote_preference": "remote",'
        '  "salary_expectation": 140000,'
        '  "seniority": "senior",'
        '  "education": ["BS CS"],'
        '  "languages": ["English"],'
        '  "keywords": ["fastapi"],'
        '  "career_goals": ["lead systems"]'
        "}"
    )

    # Use a dummy text file to trigger the parser
    dummy_path = Path("tests/dummy.txt")
    if not dummy_path.parent.exists():
         dummy_path.parent.mkdir(parents=True)
    dummy_path.write_text("Experienced programmer")

    cand = ResumeParser.parse(dummy_path, mock_gateway)

    assert "python" in cand.skills
    assert cand.years_experience == 4.5
    assert cand.remote_preference == "remote"

    # Clean up
    if dummy_path.exists():
        dummy_path.unlink()
