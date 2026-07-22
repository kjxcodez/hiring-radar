"""Technology detection and normalization engine."""

from __future__ import annotations

import re
from typing import Dict, List

# Normalized category mappings
TECH_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "languages": {
        "Python": [r"\bpython\b", r"\bpy\b"],
        "TypeScript": [r"\btypescript\b", r"\bts\b"],
        "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\bnode\.?js\b", r"\bnodejs\b"],
        "Go": [r"\bgolang\b", r"\bgo-lang\b", r"\bgo\s?lang\b"],
        "Rust": [r"\brust\b"],
        "Ruby": [r"\bruby\b", r"\brails\b"],
        "Java": [r"\bjava\b"],
        "Kotlin": [r"\bkotlin\b"],
        "C++": [r"\bc\+\+\b", r"\bcpp\b"],
        "Swift": [r"\bswift\b"],
    },
    "frameworks": {
        "React": [r"\breact\b", r"\breactjs\b", r"\breact\.js\b"],
        "Vue": [r"\bvue\b", r"\bvuejs\b", r"\bvue\.js\b"],
        "Angular": [r"\bangular\b", r"\bangularjs\b"],
        "Next.js": [r"\bnext\.?js\b", r"\bnextjs\b"],
        "Django": [r"\bdjango\b"],
        "Flask": [r"\bflask\b"],
        "FastAPI": [r"\bfastapi\b"],
        "Spring Boot": [r"\bspring\s?boot\b"],
    },
    "infrastructure": {
        "Docker": [r"\bdocker\b"],
        "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
        "Terraform": [r"\bterraform\b"],
        "Ansible": [r"\bansible\b"],
    },
    "cloud": {
        "AWS": [r"\baws\b", r"\bamazon web services\b", r"\bec2\b", r"\bs3\b"],
        "GCP": [r"\bgcp\b", r"\bgoogle cloud\b", r"\bbigquery\b"],
        "Azure": [r"\bazure\b"],
        "Vercel": [r"\bvercel\b"],
        "Heroku": [r"\bheroku\b"],
    },
    "databases": {
        "PostgreSQL": [r"\bpostgres\b", r"\bpostgresql\b"],
        "MySQL": [r"\bmysql\b"],
        "MongoDB": [r"\bmongodb\b", r"\bmongo\b"],
        "Redis": [r"\bredis\b"],
        "DynamoDB": [r"\bdynamodb\b"],
        "Elasticsearch": [r"\belasticsearch\b"],
        "SQLite": [r"\bsqlite\b"],
    },
    "ci_cd": {
        "GitHub Actions": [r"\bgithub actions\b", r"\bgithub ci\b"],
        "Jenkins": [r"\bjenkins\b"],
        "GitLab CI": [r"\bgitlab ci\b", r"\bgitlab\-ci\b"],
        "CircleCI": [r"\bcircleci\b"],
    },
    "ai_stack": {
        "OpenAI": [r"\bopenai\b", r"\bgpt\-\d\b", r"\bchatgpt\b"],
        "PyTorch": [r"\bpyt&?orch\b", r"\bpytorch\b"],
        "TensorFlow": [r"\btensorflow\b", r"\btf\b"],
        "LangChain": [r"\blangchain\b"],
        "Hugging Face": [r"\bhugging\s?face\b"],
        "LlamaIndex": [r"\bllamaindex\b"],
    },
}


class TechnologyDetector:
    """Scans and normalizes technology keywords from corporate descriptions and posts."""

    @staticmethod
    def detect(texts: List[str]) -> Dict[str, List[str]]:
        """Scan a list of texts for technology patterns.

        Returns:
            Dict containing lists of detected normalized tools grouped by category.
        """
        combined_text = "\n".join(texts).lower()
        results: Dict[str, List[str]] = {
            "languages": [],
            "frameworks": [],
            "infrastructure": [],
            "cloud": [],
            "databases": [],
            "ci_cd": [],
            "ai_stack": [],
        }

        for category, tech_map in TECH_PATTERNS.items():
            for normalized_name, patterns in tech_map.items():
                for pat in patterns:
                    if re.search(pat, combined_text):
                        if normalized_name not in results[category]:
                            results[category].append(normalized_name)
                        break  # Found match for this normalized tech, move to next

        # Sort for consistency
        for cat in results:
            results[cat].sort()

        return results
