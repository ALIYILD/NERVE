# Changelog

## 0.1.0

- Initial installable packaging for the existing `src/nerve_awim` layout (PEP 621 / setuptools).
- Optional extras: `auth` (PyJWT with crypto) and `mcp`, matching repository pins.
- Editable and wheel installs expose the package without setting `PYTHONPATH`.
