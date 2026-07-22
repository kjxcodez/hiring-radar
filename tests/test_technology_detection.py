"""Unit tests for the Technology Detection Engine."""

from __future__ import annotations

from app.intelligence.technologies import TechnologyDetector


def test_technology_detection_languages():
    texts = [
        "We are looking for a Python developer who knows Go Lang.",
        "Must be proficient in TS (TypeScript) and React."
    ]
    detected = TechnologyDetector.detect(texts)

    assert "Python" in detected["languages"]
    assert "Go" in detected["languages"]
    assert "TypeScript" in detected["languages"]
    assert "React" in detected["frameworks"]


def test_technology_detection_infrastructure_and_cloud():
    texts = [
        "Infrastructure is built on AWS and managed via Kubernetes/k8s.",
        "We use GitHub Actions for our CI/CD pipelines."
    ]
    detected = TechnologyDetector.detect(texts)

    assert "AWS" in detected["cloud"]
    assert "Kubernetes" in detected["infrastructure"]
    assert "GitHub Actions" in detected["ci_cd"]


def test_technology_detection_ai_stack():
    texts = [
        "Building solutions using OpenAI GPT-4 models, PyTorch, and LangChain."
    ]
    detected = TechnologyDetector.detect(texts)

    assert "OpenAI" in detected["ai_stack"]
    assert "PyTorch" in detected["ai_stack"]
    assert "LangChain" in detected["ai_stack"]
