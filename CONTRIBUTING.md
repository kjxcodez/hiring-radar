# Contributing to Hiring Radar

Thank you for your interest in contributing to Hiring Radar! As an open-source local-first tool, community contributions are essential to help grow and maintain the platform.

Before contributing, please read our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming and inclusive environment.

---

## 1. Development Setup

To configure your local development environment:
1. Follow the step-by-step setup guides in the [Quickstart section of the README](README.md#quickstart) to clone the repository, activate your virtual environment, and install dependencies.
2. Install the package in editable mode so you can invoke the `hiring-radar` script directly:
   ```bash
   pip install -e .
   ```

---

## 2. Running Tests

Hiring Radar uses Python's built-in `unittest` framework for its test suite. Please verify that all tests pass locally before submitting a pull request:

```bash
# Run the entire test suite
python -m unittest discover tests
```

*Note: Do not run `pytest` commands unless explicitly added, as the codebase is built and tested natively on the Python standard `unittest` library.*

---

## 3. Code Style & Architecture Expectations

We maintain clean, defensive, and typed code to preserve the platform's stability.

- **Type Hints**: All function parameters, return values, and module members should use explicit Python type annotations.
- **Data Schemas**: Always define or extend schemas using Pydantic models (located in [app/models.py](app/models.py)). Avoid using raw untyped dictionaries for core records representation.
- **Defensive AI Integration Rules**: Since AI calls to OpenRouter can fail due to network interruptions, timeouts, or rate limits, we enforce a strict coding convention:
  - **Never raise unhandled exceptions from an AI-calling function.**
  - Always wrap remote API requests inside `try/except` blocks, log the warnings or details using `loguru`, and return a safe default fallback value (e.g. empty ratings or placeholder descriptions) so the main execution flow remains unblocked.
  - See implementations in [app/enrich/ai.py](app/enrich/ai.py), [app/enrich/research.py](app/enrich/research.py), or [app/resume/score.py](app/resume/score.py) for reference patterns.

---

## 4. Adding a New Discovery Source

Discovery sources query public API platforms or scrape job feeds to list hiring companies. Adding a new crawler is a common contribution path:

1. **Implement the crawler**: Create your crawler file in the `app/discover/` directory. Use [app/discover/greenhouse.py](app/discover/greenhouse.py) or [app/discover/lever.py](app/discover/lever.py) as a reference pattern.
2. **Register the source**: Add your new crawler function to the `SOURCE_REGISTRY` mapping located inside [app/discover/__init__.py](app/discover/__init__.py) so it is automatically discovered by the `discover` CLI command.
3. **Verify parsing outputs**: Ensure your crawler returns a list of Pydantic `Company` objects containing valid `JobPosting` details and stable `dedupe_key` attributes.

---

## 5. Pull Request Expectations

When preparing a pull request:
- **Keep PRs Scoped**: Focus each PR on a single, isolated capability, bug fix, or crawler. Avoid bundling unrelated changes.
- **Add Tests**: Write clean unit tests inside the `tests/` directory verifying your newly added crawler logic or utilities.
- **Git Hygiene**:
  - Never commit configurations or databases. The following files are gitignored and must never be checked in:
    - Secrets (`.env`)
    - Local configurations (`config.yaml`)
    - Databases (`output/companies.json`, `output/applications.json`)
    - Resumes (`resumes/`) or generated static output profiles.

---

## 6. Feedback & Issue Reporting

- **Bug Reports**: If you find an error or crash, please submit a detailed ticket on the GitHub Issues page using the Bug Report template.
- **Feature Requests**: If you want to suggest new job sources or enrichment models, open a ticket outlining your proposed design on the GitHub Issues page.
