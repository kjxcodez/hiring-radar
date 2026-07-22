"""Website content parser for business and culture indicators."""

from __future__ import annotations

import re
from typing import Dict, Optional


class WebsiteAnalyzer:
    """Analyzes company homepage and career site contents to extract metadata."""

    @staticmethod
    def analyze(html_or_text: Optional[str]) -> Dict[str, Optional[str]]:
        """Extract mission, products, and remote policy indicators from raw text."""
        results: Dict[str, Optional[str]] = {
            "mission": None,
            "products": None,
            "remote_policy": "unknown",
        }

        if not html_or_text:
            return results

        # Normalize spaces and lowercase for regex scanning
        cleaned = re.sub(r"\s+", " ", html_or_text).strip()
        cleaned_lower = cleaned.lower()

        # 1. Detect remote policy
        if any(w in cleaned_lower for w in ["remote-first", "remote first", "fully remote", "work from anywhere"]):
            results["remote_policy"] = "remote"
        elif any(w in cleaned_lower for w in ["hybrid working", "hybrid work", "hybrid model", "split your time"]):
            results["remote_policy"] = "hybrid"
        elif any(w in cleaned_lower for w in ["in-office", "on-site", "office-first", "commute to"]):
            results["remote_policy"] = "onsite"

        # 2. Extract Mission Statement
        # Search for typical mission sentence templates
        mission_regexes = [
            r"([^.!?]*\bour mission is to\b[^.!?]*[.!?])",
            r"([^.!?]*\bwe exist to\b[^.!?]*[.!?])",
            r"([^.!?]*\bour vision is to\b[^.!?]*[.!?])",
            r"([^.!?]*\baims to simplify\b[^.!?]*[.!?])",
        ]
        for pattern in mission_regexes:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                results["mission"] = match.group(1).strip()
                break

        # 3. Extract Products/Offerings
        product_regexes = [
            r"([^.!?]*\bplatform for\b[^.!?]*[.!?])",
            r"([^.!?]*\bsoftware that\b[^.!?]*[.!?])",
            r"([^.!?]*\bthe easiest way to\b[^.!?]*[.!?])",
            r"([^.!?]*\bhelps developers\b[^.!?]*[.!?])",
        ]
        for pattern in product_regexes:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                results["products"] = match.group(1).strip()
                break

        return results
