"""Corporate growth, engineering culture, and technology adoption signal detector."""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from app.models import Company


class SignalDetector:
    """Analyzes organizational metrics to classify startup maturity and culture."""

    @staticmethod
    def detect(company: Company, github_stars: int = 0) -> Dict[str, any]:
        """Detect and classify corporate maturity, AI adoption, and culture signals."""
        results = {
            "funding_stage": "Unknown",
            "startup_maturity": "mid",
            "enterprise_score": 0.0,
            "engineering_culture": [],
            "oss_friendliness": 0.0,
            "ai_adoption": 0.0,
        }

        # 1. Determine Startup Maturity & Enterprise Score
        size = (company.company_size or "").lower().strip()
        if any(w in size for w in ["10,000+", "5000+", "1000-5000"]):
            results["startup_maturity"] = "enterprise"
            results["enterprise_score"] = 0.9
        elif any(w in size for w in ["501-1000", "201-500"]):
            results["startup_maturity"] = "late"
            results["enterprise_score"] = 0.6
        elif any(w in size for w in ["11-50", "51-200"]):
            results["startup_maturity"] = "mid"
            results["enterprise_score"] = 0.3
        elif any(w in size for w in ["1-10"]):
            results["startup_maturity"] = "early"
            results["enterprise_score"] = 0.1

        # 2. Detect Funding Stage
        desc = (company.description or "").lower()
        if "series a" in desc:
            results["funding_stage"] = "Series A"
        elif "series b" in desc:
            results["funding_stage"] = "Series B"
        elif "series c" in desc or "series d" in desc:
            results["funding_stage"] = "Late Stage Venture"
        elif "seed" in desc:
            results["funding_stage"] = "Seed"
        elif "ipo" in desc or "public" in desc:
            results["funding_stage"] = "Public"
        elif "bootstrapped" in desc:
            results["funding_stage"] = "Bootstrapped"

        # 3. Detect Engineering Culture Tags
        combined_text = (
            desc + "\n" + "\n".join(j.job_title for j in company.jobs)
        ).lower()

        culture_map = {
            "Open Source": ["open source", "oss", "github"],
            "Remote-First": ["remote first", "remote-first", "fully remote"],
            "Agile": ["agile", "scrum", "sprints"],
            "TDD": ["tdd", "unit tests", "testing-driven"],
            "Hackathons": ["hackathon", "shipit"],
            "Continuous Delivery": ["cicd", "continuous delivery", "automated deployment"],
        }
        for culture_tag, keywords in culture_map.items():
            if any(w in combined_text for w in keywords):
                results["engineering_culture"].append(culture_tag)

        # 4. OSS Friendliness (derived from GitHub stars)
        if github_stars >= 5000:
            results["oss_friendliness"] = 1.0
        elif github_stars >= 500:
            results["oss_friendliness"] = 0.7
        elif github_stars >= 50:
            results["oss_friendliness"] = 0.4
        elif github_stars > 0:
            results["oss_friendliness"] = 0.2

        # 5. AI Adoption (ratio of AI/ML roles relative to total roles)
        ai_roles = 0
        ai_keywords = ["ai", "ml", "machine learning", "deep learning", "llm", "nlp", "vision", "openai"]
        for j in company.jobs:
            title = j.job_title.lower()
            if any(w in title for w in ai_keywords):
                ai_roles += 1

        if company.jobs:
            results["ai_adoption"] = round(ai_roles / len(company.jobs), 2)

        return results
