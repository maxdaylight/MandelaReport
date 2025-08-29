# Contributing to MandelaReport

Thank you for your interest in contributing to MandelaReport!

This document explains how to set up a development environment, run tests and linters, and make a clean pull request.

## Getting started (local development)

1. Create and activate a virtual environment (PowerShell):

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    ```

2. Run the test suite:

    ```powershell
    .\.venv\Scripts\python.exe -m pytest -q
    ```

3. Run linters and type checks:

    ```powershell
    .\.venv\Scripts\ruff.exe check . --fix
    .\.venv\Scripts\python.exe -m mypy --ignore-missing-imports src
    ```

## Pre-commit hooks

This repository uses pre-commit to run formatting/lint hooks automatically on commit. Install and enable hooks once per clone:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pre-commit
.\.venv\Scripts\python.exe -m pre_commit install
# Run hooks once across the repo
.\.venv\Scripts\python.exe -m pre_commit run --all-files
```

## Making changes

- Branch from `main` using a descriptive name: `git checkout -b feat/add-foo`.
- Keep changes small and focused.
- Run tests and linters locally; fix issues before opening a PR.
- Include tests for new behavior and update docs if needed.

## Contributing to MandelaReport

Thank you for your interest in contributing to MandelaReport!

This document explains how to set up a development environment, run tests and linters, and make a clean pull request.

## Getting started (local development)

Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Running tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Linters and type checks

```powershell
.\.venv\Scripts\ruff.exe check . --fix
.\.venv\Scripts\python.exe -m mypy --ignore-missing-imports src
```

## Pre-commit hooks

This repository uses pre-commit to run formatting/lint hooks automatically on commit. Install and enable hooks once per clone:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install pre-commit
.\.venv\Scripts\python.exe -m pre_commit install
# Run hooks once across the repo
.\.venv\Scripts\python.exe -m pre_commit run --all-files
```

## Making changes

- Branch from `main` using a descriptive name: `git checkout -b feat/add-foo`.
- Keep changes small and focused.
- Run tests and linters locally; fix issues before opening a PR.
- Include tests for new behavior and update docs if needed.

## Pull request checklist

- [ ] Branch up-to-date with `main`.
- [ ] Tests pass locally (`pytest`).
- [ ] Linting/formatting applied (pre-commit hooks ran).
- [ ] Added or updated documentation where applicable.
- [ ] Include a brief description and motivation in the PR body.

## License & contributor note

- This project is licensed CC BY-NC 4.0. By contributing you agree that your contribution will be licensed under the same terms. If you need a separate commercial license, contact the project owner.

- If you'd like to sign a contributor license agreement (CLA) or add DCO signatures, open an issue to discuss.

## Contact

For questions about contributing, contact: <maxdaylight@outlook.com>
