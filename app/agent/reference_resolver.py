"""Contextual reference resolver resolving follow-up pronouns to session entities."""

from __future__ import annotations

import re
from typing import Any, Optional
from app.agent.session import AgentSession


def resolve_references(query: str, session: AgentSession) -> tuple[str, dict[str, Any]]:
    """Resolve follow-up references using session state and return the updated query and resolved entities.

    Example: "Show more like the second one"
    Returns: ("Show more like Wealthfront", {"company_name": "Wealthfront"})
    """
    resolved_query = query
    resolved_entities = {}
    
    q = query.lower()

    # 1. Match indexed references (e.g. "second one", "the 2nd recommendation", "number 3")
    index_map = {
        "first": 0, "1st": 0,
        "second": 1, "2nd": 1,
        "third": 2, "3rd": 2,
        "fourth": 3, "4th": 3,
        "fifth": 4, "5th": 4,
    }
    
    matched_idx = None
    for pattern, idx in index_map.items():
        if re.search(r'\b(the\s+)?' + pattern + r'(\s+one|\s+recommendation|\s+company|\s+job)?\b', q):
            matched_idx = idx
            break
            
    if matched_idx is not None and session.last_recommendations:
        if 0 <= matched_idx < len(session.last_recommendations):
            rec = session.last_recommendations[matched_idx]
            co_name = rec.get("company_name") or rec.get("name")
            if co_name:
                resolved_entities["company_name"] = co_name
                resolved_query = re.sub(
                    r'\b(the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)(\s+one|\s+recommendation|\s+company|\s+job)?\b',
                    co_name,
                    query,
                    flags=re.IGNORECASE
                )
                return resolved_query, resolved_entities

    # 2. Match general previous references (e.g. "that one", "previous company", "the last one")
    if any(w in q for w in ("that one", "previous company", "the last one", "last company")):
        if session.discussed_companies:
            last_co = session.discussed_companies[-1]
            resolved_entities["company_name"] = last_co
            resolved_query = re.sub(
                r'\b(that\s+one|the\s+previous\s+company|the\s+last\s+one|last\s+company)\b',
                last_co,
                query,
                flags=re.IGNORECASE
            )
            return resolved_query, resolved_entities

    return resolved_query, resolved_entities
