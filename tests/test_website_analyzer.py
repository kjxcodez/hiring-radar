"""Unit tests for the Website Analyzer."""

from __future__ import annotations

from app.intelligence.website import WebsiteAnalyzer


def test_website_analyzer_remote_policies():
    # 1. Remote
    res = WebsiteAnalyzer.analyze("We are a remote-first startup offering flexible work from anywhere.")
    assert res["remote_policy"] == "remote"

    # 2. Hybrid
    res = WebsiteAnalyzer.analyze("Requires split your time working 3 days from our Hybrid office.")
    assert res["remote_policy"] == "hybrid"

    # 3. Onsite
    res = WebsiteAnalyzer.analyze("Full time in-office role requiring daily commute to NYC.")
    assert res["remote_policy"] == "onsite"


def test_website_analyzer_mission_and_products():
    text = (
        "Our vision is to build a better future. "
        "Actually, Our mission is to simplify developer onboarding for modern software teams. "
        "We build a platform for developers to deploy APIs quickly."
    )
    res = WebsiteAnalyzer.analyze(text)
    assert res["mission"] == "Actually, Our mission is to simplify developer onboarding for modern software teams."

    assert res["products"] == "We build a platform for developers to deploy APIs quickly."
