"""User Profile updates, fact learning, and conflict resolutions."""

from __future__ import annotations

import re
from app.memory.models import UserProfile, Preferences
from app.memory.store import global_memory_store


def learn_from_user_query(text: str) -> None:
    """Analyze query and update evolving profile or preferences heuristically."""
    profile = global_memory_store.load_profile()
    prefs = global_memory_store.load_preferences()
    
    normalized = text.lower()
    
    if "remote only" in normalized or "only want remote" in normalized or "prefers remote" in normalized:
        profile.remote_preference = True
    elif "onsite" in normalized or "hybrid" in normalized:
        profile.remote_preference = False
        
    stack_keywords = ["python", "javascript", "react", "typescript", "node", "rust", "go", "java", "aws", "docker"]
    for tech in stack_keywords:
        if tech in normalized:
            if tech not in profile.tech_stack:
                profile.tech_stack.append(tech)
                
    salary_match = re.search(r"salary\s*(?:expectations?|requirements?)?\s*(?:above|over|expects|of|is|at)\s*([$€£\d\w\-+]+)", normalized)
    if salary_match:
        val = salary_match.group(1).strip()
        profile.preferred_salary = val
        prefs.preferences["salary"] = val
        
    location_keywords = ["europe", "germany", "berlin", "london", "usa", "us", "india", "bangalore"]
    for loc in location_keywords:
        if f"in {loc}" in normalized:
            if loc not in profile.preferred_locations:
                profile.preferred_locations.append(loc)
                
    global_memory_store.save_profile(profile)
    global_memory_store.save_preferences(prefs)
