"""GitHub repository analyzer extracting open-source statistics."""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from selectolax.parser import HTMLParser


class GitHubAnalyzer:
    """Extracts activity, star counts, and stack indicators from GitHub HTML/API responses."""

    @staticmethod
    def parse_profile_html(html_text: Optional[str]) -> Dict[str, any]:
        """Scrape repositories, language stats, and star counts from profile page HTML."""
        results = {
            "popular_repositories": [],
            "stars": 0,
            "languages": [],
            "activity": "medium",
            "contributors": 0,
        }

        if not html_text:
            return results

        parser = HTMLParser(html_text)

        # 1. Scrape repository names and descriptions
        repos = []
        for el in parser.css('a[itemprop="name codeRepository"], a.wb-break-all'):
            name = el.text(strip=True)
            if name and name not in repos:
                repos.append(name)
        results["popular_repositories"] = repos[:10]

        # 2. Extract Languages from page
        languages = []
        for el in parser.css('[itemprop="programmingLanguage"]'):
            lang = el.text(strip=True)
            if lang and lang not in languages:
                languages.append(lang)
        results["languages"] = languages[:5]

        # 3. Estimate stars and contributors from HTML heuristics if available
        # (Otherwise use reasonable defaults)
        star_matches = re.findall(r"([\d,]+)\s*star", html_text, re.IGNORECASE)
        total_stars = 0
        for match in star_matches:
            try:
                total_stars += int(match.replace(",", ""))
            except ValueError:
                pass
        results["stars"] = min(total_stars, 100000)  # Sanity cap

        # 4. Infer activity level based on count of repositories
        if len(repos) >= 15:
            results["activity"] = "high"
        elif len(repos) >= 5:
            results["activity"] = "medium"
        else:
            results["activity"] = "low"

        # Contributors default
        results["contributors"] = len(repos) * 3  # rough proxy

        return results
