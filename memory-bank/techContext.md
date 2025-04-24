# Tech Context

This document details the technologies, development setup, and dependencies for ledger-parsita.

## Technologies Used

- Python: The primary programming language.

## Development Setup

- The project uses `devenv.nix` for managing the development environment and dependencies.
- VS Code is the recommended editor, with relevant Python extensions.

## Dependencies

- Dependencies are managed via `devenv.nix`.
- `parsita` is used for parsing.
- **No new major dependencies are anticipated for the initial capital gains tracking implementation, building on existing libraries.**

## Tool Usage Patterns

- Use `devenv shell` to enter the development environment.
- Use `python3 -m pytest` for running tests. When fixing unit tests, always rerun just the single test case instead of the whole test suite. Example command: `python3 -m pytest tests/test_find_non_dated_opens.py tests/test_find_non_dated_opens.py::test_find_non_dated_opens`
- Use `black` and `isort` for code formatting.
- **New CLI commands will be added for the capital gains tracking tool.**

## Library Documentation

Basic documentation for key libraries used in the project can be found in the `memory-bank/libraries` directory.
