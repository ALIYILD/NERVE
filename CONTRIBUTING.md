# Contributing

Thank you for contributing to NERVE-AWIM.

## Development checks

From the repository root with Python 3.10+ and Node.js available:

```bash
PYTHONPATH=src python -m unittest discover -s tests
node --test tests/test_checkpoint_discovery.cjs
```

Run both suites before opening a pull request and keep them passing.

## Pull requests

- Keep pull requests small and focused on one change.
- Do not commit secrets, credentials, or LLM/API key environment variables.
- Do not include patient data or personal data in code, tests, fixtures, docs,
  or issue/PR text.
- Prefer clear commit messages that explain why the change is needed.

## Scope reminders

This repository is research software. It is not connected to a downstream
clinical application by default, does not ship patient data, and is not
validated for clinical use. Keep those boundaries intact in contributions.
