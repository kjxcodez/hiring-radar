"""Hiring analytics computing seniority, department, and velocity distributions."""

from __future__ import annotations

from typing import Dict, List
from app.models import JobPosting


class HiringAnalyzer:
    """Analyzes a company's job postings to compile organizational trends."""

    @staticmethod
    def analyze(jobs: List[JobPosting]) -> Dict[str, any]:
        """Compute seniority, department, location, and velocity distributions.

        Args:
            jobs: List of JobPosting models for a company.
        """
        results = {
            "hiring_velocity": "stable",
            "open_roles": len(jobs),
            "departments": [],
            "seniority_distribution": {"Junior": 0.0, "Mid-level": 0.0, "Senior": 0.0, "Lead/Manager": 0.0},
            "geographic_distribution": [],
        }

        if not jobs:
            return results

        # 1. Determine velocity
        if len(jobs) >= 8:
            results["hiring_velocity"] = "growing"
        elif len(jobs) <= 1:
            results["hiring_velocity"] = "declining"
        else:
            results["hiring_velocity"] = "stable"

        # 2. Extract departments and seniority counts
        dept_counts = {"Engineering": 0, "Product": 0, "Design": 0, "Sales/Marketing": 0, "Operations/HR": 0}
        seniority_counts = {"Junior": 0, "Mid-level": 0, "Senior": 0, "Lead/Manager": 0}
        geographies = set()

        for j in jobs:
            title = (j.job_title or "").lower().strip()
            
            # Geography
            if j.location:
                geographies.add(j.location.strip())

            # Seniority
            if any(w in title for w in ["junior", "associate", "intern", "grad"]):
                seniority_counts["Junior"] += 1
            elif any(w in title for w in ["lead", "principal", "staff", "manager", "director", "vp", "head"]):
                seniority_counts["Lead/Manager"] += 1
            elif any(w in title for w in ["senior", "sr.", "sr "]):
                seniority_counts["Senior"] += 1
            else:
                seniority_counts["Mid-level"] += 1

            # Department
            if any(w in title for w in ["engineer", "developer", "architect", "programmer", "tech lead"]):
                dept_counts["Engineering"] += 1
            elif any(w in title for w in ["product manager", "pm", "product owner"]):
                dept_counts["Product"] += 1
            elif any(w in title for w in ["designer", "ux", "ui", "creative"]):
                dept_counts["Design"] += 1
            elif any(w in title for w in ["sales", "marketing", "growth", "account", "sdr", "ae"]):
                dept_counts["Sales/Marketing"] += 1
            else:
                dept_counts["Operations/HR"] += 1

        # Calculate percentages for seniority
        total = len(jobs)
        results["seniority_distribution"] = {
            k: round(v / total, 2) for k, v in seniority_counts.items()
        }

        # Select departments with at least 1 job
        results["departments"] = sorted([
            dept for dept, count in dept_counts.items() if count > 0
        ])

        results["geographic_distribution"] = sorted(list(geographies))

        return results
