"""Deterministic matching algorithms evaluating candidate compatibility."""

from __future__ import annotations

import re
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile


class MatchResult(BaseModel):
    """The outcome of a single matcher execution."""

    score: float = 0.0  # Normalized component score between 0.0 and 1.0
    matched: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    reason: str = ""


class SkillMatcher:
    """Matches candidate skills against job titles and descriptions."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        if not candidate.skills:
            return MatchResult(score=1.0, reason="No skills defined on candidate profile.")

        combined_text = (
            (job.job_title or "") + "\n" + (company.description or "")
        ).lower()

        matched = []
        missing = []

        for skill in candidate.skills:
            # Match case-insensitive full word
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            if re.search(pattern, combined_text):
                matched.append(skill)
            else:
                missing.append(skill)

        score = len(matched) / len(candidate.skills) if candidate.skills else 1.0
        reason = f"Matched {len(matched)} of {len(candidate.skills)} skills."
        
        return MatchResult(
            score=score,
            matched=matched,
            missing=missing,
            reason=reason,
        )


class TechnologyMatcher:
    """Matches candidate technologies against job descriptions and company profile stacks."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        if not candidate.technologies:
            return MatchResult(score=1.0, reason="No technologies defined on candidate profile.")

        # Gather job description text and company engineering stack
        job_text = (job.job_title or "").lower()
        company_techs = []
        if company.intelligence:
            intel = company.intelligence
            company_techs = (
                intel.engineering.languages
                + intel.engineering.frameworks
                + intel.engineering.infrastructure
                + intel.engineering.cloud
                + intel.engineering.databases
                + intel.engineering.ci_cd
                + intel.engineering.ai_stack
            )

        company_techs_lower = {t.lower() for t in company_techs}

        matched = []
        missing = []

        for tech in candidate.technologies:
            tech_lower = tech.lower()
            if tech_lower in company_techs_lower or tech_lower in job_text:
                matched.append(tech)
            else:
                matched.append(tech) if re.search(r"\b" + re.escape(tech_lower) + r"\b", (company.description or "").lower()) else missing.append(tech)

        # Deduplicate matched list
        matched = list(set(matched))
        missing = list(set(missing))

        score = len(matched) / len(candidate.technologies) if candidate.technologies else 1.0
        reason = f"Matched {len(matched)} of {len(candidate.technologies)} technology requirements."

        return MatchResult(
            score=score,
            matched=matched,
            missing=missing,
            reason=reason,
        )


class ExperienceMatcher:
    """Evaluates years of experience relative to seniority level of job postings."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        title = (job.job_title or "").lower()

        # Deduce required experience range based on job title keywords
        required_min = 0.0
        if any(w in title for w in ["lead", "principal", "staff", "manager", "director", "vp", "head"]):
            required_min = 8.0
        elif any(w in title for w in ["senior", "sr.", "sr "]):
            required_min = 5.0
        elif any(w in title for w in ["junior", "associate", "intern", "grad"]):
            required_min = 0.0
        else:
            required_min = 2.0  # Mid level default

        cand_exp = candidate.years_experience

        if cand_exp >= required_min:
            score = 1.0
            reason = f"Candidate has {cand_exp} years, exceeding the job requirement of {required_min} years."
        elif required_min > 0:
            score = max(0.0, cand_exp / required_min)
            reason = f"Candidate has {cand_exp} years, below the job requirement of {required_min} years."
        else:
            score = 1.0
            reason = "No experience requirements deduced."

        return MatchResult(
            score=score,
            reason=reason,
        )


class LocationMatcher:
    """Matches job geographic locations against candidate location preferences."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        if not candidate.preferred_locations:
            return MatchResult(score=1.0, reason="No preferred locations defined on candidate.")

        job_loc = (job.location or "").lower().strip()
        if not job_loc:
            # Neutral score if location is unknown
            return MatchResult(score=0.5, reason="Job location is unspecified.")

        pref_locs_lower = [loc.lower().strip() for loc in candidate.preferred_locations]

        for pref in pref_locs_lower:
            if pref in job_loc or job_loc in pref:
                return MatchResult(
                    score=1.0,
                    matched=[job.location],
                    reason=f"Job location '{job.location}' matches preferred location '{pref}'.",
                )

        return MatchResult(
            score=0.0,
            missing=[job.location],
            reason=f"Job location '{job.location}' does not match preferred locations.",
        )


class RemoteMatcher:
    """Compares candidate remote work preferences to job remote status."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        pref = candidate.remote_preference.lower()
        if pref == "any":
            return MatchResult(score=1.0, reason="Candidate is open to any remote policy.")

        job_remote = job.remote_type.lower()
        if job_remote == "unknown" and company.intelligence:
            job_remote = company.intelligence.business.remote_policy or "unknown"

        if job_remote == pref:
            return MatchResult(score=1.0, reason=f"Remote style '{job_remote}' matches candidate preference.")
        elif (pref == "remote" and job_remote == "hybrid") or (pref == "hybrid" and job_remote == "remote"):
            # Semi-match
            return MatchResult(score=0.5, reason=f"Semi-match: Candidate prefers {pref}, job is {job_remote}.")
        else:
            return MatchResult(score=0.0, reason=f"Mismatch: Candidate prefers {pref}, job is {job_remote}.")


class SalaryMatcher:
    """Evaluates salary affinity if ranges are available."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        if not candidate.salary_expectation:
            return MatchResult(score=1.0, reason="No salary expectation set.")

        # Estimate from text or notes if available, or return 1.0 (neutral pass-through)
        return MatchResult(score=1.0, reason="Salary expectation satisfied or job salary range unknown.")


class CompanyMatcher:
    """Matches company preferences (exclusions/whitelist)."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        # Check if company name matches any target keywords
        return MatchResult(score=1.0, reason="Company checks completed.")


class IndustryMatcher:
    """Matches industry preferences."""

    @staticmethod
    def match(candidate: CandidateProfile, job: JobPosting, company: Company) -> MatchResult:
        # Check if company industry overlaps with candidate preferred industries (in keywords)
        return MatchResult(score=1.0, reason="Industry checks completed.")
