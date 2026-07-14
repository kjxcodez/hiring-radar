# resume — AI resume matching compatibility and parser module

from app.resume.parser import load_resume_text
from app.resume.score import score_company

__all__ = ["load_resume_text", "score_company"]
