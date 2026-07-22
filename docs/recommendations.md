# AI Candidate Matching, Job Scoring & Recommendation Engine

This document details the design, scoring methodology, and CLI details for the job recommendation system implemented in Phase 2.3.

---

## 1. Recommendation Pipeline

```
  Resume File / Profile Input
            │
            ▼
┌───────────────────────┐
│     Resume Parser     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  CandidateProfile     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  Scoring & Matchers   │ (Deterministic scores 0.0 - 1.0)
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   Recommendation      │ (Weights configured in weights.py)
│    Scorer (0-100)     │
└───────────┬───────────┘
            │
            ├──────────────────────┐
            ▼                      ▼
┌───────────────────────┐  ┌──────────────┐
│  AI Match Explainer   │  │ Cache System │
└───────────┬───────────┘  └──────┬───────┘
            │                     │ (Candidate + Company + Job Fingerprints)
            └──────────┬──────────┘
                       │
                       ▼
┌───────────────────────┐
│  Recommendations Repo │ (output/recommendations.json)
└───────────────────────┘
```

---

## 2. Matchers & Deterministic Scoring

To ensure reproducibility, matching logic is completely deterministic:

* **`SkillMatcher`**: Case-insensitive full-word overlap between candidate skills and job titles/descriptions.
* **`TechnologyMatcher`**: Evaluates overlap between candidate's technology stack and normalized company/job engineering signals.
* **`ExperienceMatcher`**: Decides required experience based on seniority tags in job titles (e.g. Senior = 5+ years, Lead/Manager = 8+ years) and compares candidate experience.
* **`LocationMatcher`**: Computes string matches against candidate's location list.
* **`RemoteMatcher`**: Matches remote style ("remote", "hybrid", "onsite") against candidate's preference.

The overall matching score is calculated via configured component weights in `app/recommendation/weights.py`:

$$Score = \frac{\sum (Score_i \times Weight_i)}{\sum Weight_i} \times 100$$

AI is only called afterwards to construct justifications and explanations, never influencing the core rating.

---

## 3. Explanations & Roadmaps

Matches call the OpenRouter API with prompt `recommend_explain.v1` to build:
- **`why_fit`**: Natural language match summaries.
- **`strengths` / `weaknesses`**: Pros and cons lists.
- **`resume_improvements`**: Tailoring recommendations.
- **`study_roadmap`**: Learning directions for missing skills.

---

## 4. Cache System

Avoids repeated LLM explanation calls. Calculated from:
- `Candidate profile fingerprint` (Pydantic json schema)
- `Company fingerprint`
- `Job fingerprint`
- `Knowledge Graph checksum`
- `Intelligence checksum`

---

## 5. Background Integration

Subscribes to workflow completion. When the `"intelligence"` job finishes, the background runtime enqueues `"recommend_job"` automatically.

---

## 6. CLI Usage

```bash
# Parse resume and match jobs
hiring-radar recommend resume path/to/resume.pdf

# List top ranked matches
hiring-radar recommend top [--limit 5]

# Show match details and AI explanation for a company
hiring-radar recommend company stripe

# Show details by ranked index
hiring-radar recommend explain 1

# Wipe caches and rebuild recommendations
hiring-radar recommend refresh
```
