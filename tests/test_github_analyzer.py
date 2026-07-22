"""Unit tests for the GitHub Analyzer."""

from __future__ import annotations

from app.intelligence.github import GitHubAnalyzer


def test_github_analyzer_parsing():
    html_text = """
    <html>
      <body>
        <div class="col-12">
          <a itemprop="name codeRepository" class="wb-break-all">stripe-python</a>
          <span itemprop="programmingLanguage">Python</span>
          <span>1,200 stars</span>
        </div>
        <div class="col-12">
          <a itemprop="name codeRepository" class="wb-break-all">stripe-node</a>
          <span itemprop="programmingLanguage">TypeScript</span>
          <span>450 stars</span>
        </div>
      </body>
    </html>
    """

    res = GitHubAnalyzer.parse_profile_html(html_text)
    assert "stripe-python" in res["popular_repositories"]
    assert "stripe-node" in res["popular_repositories"]
    assert "Python" in res["languages"]
    assert "TypeScript" in res["languages"]
    assert res["stars"] == 1650
    assert res["activity"] == "low"  # under 5 repos
