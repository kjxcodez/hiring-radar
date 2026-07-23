"""Loader for task-specific LLM routing policies."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskPolicy(BaseModel):
    provider: str
    model: Optional[str] = None


class RoutingPolicies(BaseModel):
    routing: dict[str, TaskPolicy] = Field(default_factory=dict)


def load_routing_policies(path: Path = Path("routing.yaml")) -> RoutingPolicies:
    """Load routing policies from routing.yaml or return defaults."""
    if not path.exists():
        defaults = {
            "intent_classifier": TaskPolicy(provider="local"),
            "query_analysis": TaskPolicy(provider="local"),
            "planner": TaskPolicy(provider="google", model="gemini-2.5-flash"),
            "recommendation_summary": TaskPolicy(provider="google", model="gemini-2.5-flash"),
            "company_research": TaskPolicy(provider="google", model="gemini-2.5-flash"),
            "resume_analysis": TaskPolicy(provider="google", model="gemini-2.5-flash"),
            "diagnostics": TaskPolicy(provider="local")
        }
        return RoutingPolicies(routing=defaults)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        policies = {}
        routing_data = data.get("routing", {})
        for task, pol in routing_data.items():
            policies[task] = TaskPolicy(
                provider=pol.get("provider", "google"),
                model=pol.get("model")
            )
        return RoutingPolicies(routing=policies)
    except Exception as exc:
        logger.warning("Failed to load routing policies: %s. Using default.", exc)
        return load_routing_policies(Path("non_existent_file.yaml"))
