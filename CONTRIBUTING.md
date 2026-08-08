# Contributing

Thank you for contributing.

1. Create a branch from `main`.
2. Create and activate a Python 3.10+ virtual environment.
3. Install development dependencies with `python -m pip install -e ".[dev]"`.
4. Add or update focused tests in `tests/` for every behavior change.
5. Run `python -m unittest discover -s tests -v` before opening a pull request.
6. Describe the behavior change, tests, and any network or data-handling implications in the pull request.

Do not commit credentials, personal information, proprietary reports, converted report output, or large binary artifacts. See [DATA_POLICY.md](DATA_POLICY.md).
