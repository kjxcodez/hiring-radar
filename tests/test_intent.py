"""Tests for Intent Classification Layer."""

from __future__ import annotations

from app.agent.intent import classify_intent_rule_based


def test_intent_classification_rule_based() -> None:
    """Verify rule-based classifications of common REPL commands."""
    res_greet = classify_intent_rule_based("hi")
    assert res_greet is not None
    assert res_greet.intent == "greeting"
    assert res_greet.confidence == 1.0

    res_help = classify_intent_rule_based("what can you do")
    assert res_help is not None
    assert res_help.intent == "help"

    res_apps = classify_intent_rule_based("show my applications")
    assert res_apps is not None
    assert res_apps.intent == "application_status"

    res_alerts = classify_intent_rule_based("list alerts")
    assert res_alerts is not None
    assert res_alerts.intent == "alerts"

    res_cos = classify_intent_rule_based("show companies")
    assert res_cos is not None
    assert res_cos.intent == "search_company"

    res_follow = classify_intent_rule_based("show more like the second one")
    assert res_follow is not None
    assert res_follow.intent == "follow_up"
