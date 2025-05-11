# Tech Context

This document details the technologies, development setup, and dependencies for ledger-parsita.

## Technologies Used

- Python: The primary programming language.
- Pytest: Used for writing and running tests.
- Click: Used for building the command-line interface, including custom parameter types (`click.ParamType`).
- Custom Filtering Classes: Implemented `BaseFilter`, `Filters`, and `FilterListParamType` classes in `src/filtering.py` for defining and applying transaction filters and integrating with Click.

## Development Setup

- The project uses `devenv.nix` for managing the development environment and dependencies.
- VS Code is the recommended editor, with relevant Python extensions.

## Dependencies

- Dependencies are managed via `devenv.nix`.
- `parsita` is used for parsing.
- `returns` is used for error handling.
- `pytest` is used for testing.
- No new major dependencies are anticipated for the initial capital gains tracking implementation, building on existing libraries.

## Tool Usage Patterns

- Use `devenv shell` to enter the development environment.
- Use `python3 -m pytest` for running tests.
- When debugging and fixing tests, when a failure is observed ALWAYS test just a single test with command like `python3 -m pytest tests/test_hledger_parser.py::test_journal_and_entities_have_source_location`. Always fix tests one by one. Each fix should be small.
- Always re-run a single test AFTER EVERY SINGLE CODE MODIFICATION! If not sure which test to run, run all of them.
- Use `black` and `isort` for code formatting.
- The `gains` CLI command has been added for capital gains reporting. Other CLI commands related to capital gains (e.g., for journal updates) may be added in the future.

## Library Documentation

Basic documentation for key libraries used in the project can be found in the `memory-bank/libraries` directory.
