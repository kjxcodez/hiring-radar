## Description
Provide a concise explanation of what changed, why the change was made, and any key architectural decisions.

## Related Issues
Fixes #[Insert Issue Number]

## Checklist
Please review and check the following items before submitting your PR:

- [ ] My PR has a focused scope (implements a single capability or bug fix).
- [ ] I have verified that all unit tests pass locally (`python -m unittest discover tests`).
- [ ] I have updated/written unit tests covering the new changes.
- [ ] I have ran the local health check utility (`python scripts/health_check.py`) and verified status.
- [ ] I have not committed any sensitive credentials, configuration files, or database records (`.env`, `config.yaml`, `companies.json`, `applications.json`, `resumes/`, `output/`).
- [ ] Code style matches guidelines (Pydantic models, type hints, defensive AI exception-guarding).
