"""Tests for transcript exporting UI utilities."""

from __future__ import annotations

from pathlib import Path
from app.ui.export import export_transcript_markdown, export_transcript_json, export_transcript_html


def test_transcript_exports(tmp_path: Path) -> None:
    """Verify HTML, Markdown, and JSON export utilities write files correctly."""
    history = [
        {"role": "user", "content": "Search jobs"},
        {"role": "assistant", "content": "I found 5 jobs."}
    ]
    
    md_file = tmp_path / "export.md"
    json_file = tmp_path / "export.json"
    html_file = tmp_path / "export.html"
    
    export_transcript_markdown(history, md_file)
    export_transcript_json(history, json_file)
    export_transcript_html(history, html_file)
    
    assert md_file.exists()
    assert "# Hiring Radar" in md_file.read_text(encoding="utf-8")
    
    assert json_file.exists()
    assert '"role": "user"' in json_file.read_text(encoding="utf-8")
    
    assert html_file.exists()
    assert "<html" in html_file.read_text(encoding="utf-8")
