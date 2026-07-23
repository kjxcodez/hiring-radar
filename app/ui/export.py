"""Transcript exporting utilities for REPL conversations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any


def export_transcript_markdown(history: List[Dict[str, Any]], output_path: Path) -> None:
    """Export conversation transcript as a clean Markdown file."""
    lines = ["# Hiring Radar Agent Conversation Transcript\n"]
    for idx, msg in enumerate(history, 1):
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content") or ""
        
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            content += f"\n*(Tool Calls requested: {', '.join(t.get('function', {}).get('name', 'unknown') for t in tool_calls)})*"
            
        lines.append(f"### {idx}. {role}\n{content}\n")
        
    output_path.write_text("\n".join(lines), encoding="utf-8")


def export_transcript_json(history: List[Dict[str, Any]], output_path: Path) -> None:
    """Export conversation transcript as a structured JSON file."""
    output_path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def export_transcript_html(history: List[Dict[str, Any]], output_path: Path) -> None:
    """Export conversation transcript as a formatted HTML document."""
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<title>Hiring Radar Agent Transcript</title>",
        "<style>",
        "body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; background-color: #fafafa; }",
        "h1 { border-bottom: 2px solid #ccc; padding-bottom: 10px; color: #333; }",
        ".message { margin-bottom: 20px; padding: 15px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        ".user { background-color: #e3f2fd; border-left: 5px solid #2196f3; }",
        ".assistant { background-color: #f5f5f5; border-left: 5px solid #9e9e9e; }",
        ".tool { background-color: #fff9c4; border-left: 5px solid #fbc02d; font-family: monospace; }",
        ".system { background-color: #ede7f6; border-left: 5px solid #673ab7; }",
        ".role { font-weight: bold; margin-bottom: 5px; color: #444; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Hiring Radar Agent Transcript</h1>"
    ]
    
    for msg in history:
        role = msg.get("role", "unknown")
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            content += f"<br><i>[Tool Calls: {', '.join(t.get('function', {}).get('name', 'unknown') for t in tool_calls)}]</i>"
            
        html_lines.append(f'<div class="message {role}">')
        html_lines.append(f'  <div class="role">{role.upper()}</div>')
        html_lines.append(f'  <div class="content">{content}</div>')
        html_lines.append('</div>')
        
    html_lines.extend(["</body>", "</html>"])
    output_path.write_text("\n".join(html_lines), encoding="utf-8")
