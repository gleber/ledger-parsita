# Active Context

This document outlines the current focus and active considerations for ledger-parsita development.

## Current Work Focus

- Planning and implementing the capital gains tracking tool.

## Recent Changes

- Initialized and updated memory bank core files based on initial code review.
- Updated `.clinerules` with instruction for Context7 library IDs and created `memory-bank/context7_library_ids.md`.
- Reviewed `README.md`, `src/`, and `tests/` directories.
- Refined `TagFilter` implementation and tests.
- Updated memory bank files (`projectbrief.md`, `productContext.md`, `systemPatterns.md`, `techContext.md`) to reflect the new main goal of capital gains tracking.
- Added `isAsset()` method to `AccountName` class in `src/classes.py`.
- Updated `src/capital_gains.py` to use the `isAsset()` method instead of regex for identifying asset accounts.
- Added `tests/test_classes.py` with tests for `AccountName`, including the `isAsset()` method.
- Added tests to `tests/test_capital_gains.py` for the functions using `isAsset()`.
- Added tests for `AccountName.isAsset()` and related capital gains functions.
- Added `getKey()` method to `Transaction` class and used it in capital gains functions for tracking seen transactions.
- Refactored capital gains finding functions using a higher-order function to deduplicate logic.
- Attempted to fix failing capital gains tests, but the cause of the failures is unclear and may be related to test data or environment issues.
- Added `isCash()` method to `Commodity` class in `src/classes.py`.
- Updated `src/capital_gains.py` to use the `isCash()` method to exclude cash-only transactions.
- Added tests to `tests/test_capital_gains.py` to ensure cash transactions are excluded.
- The `isDatedSubaccount` method was found to be already implemented and tested in `src/classes.py`.
- Added the `find-positions` CLI command to `src/main.py` to find open and close transactions.
- Added a test case for the `find-positions` command in `tests/test_main.py`.
- Created `tests/includes/journal_positions.journal` for testing the `find-positions` command.
- Refactored tests in `tests/test_classes.py`, `tests/test_journal_flattening.py`, and `tests/test_main.py` from `unittest` to `pytest` style.

## Next Steps

- Define the data structures needed for tracking asset lots and capital gains calculations.
- Implement the logic for identifying closed positions based on journal entries and dated subaccounts.
- Implement the FIFO logic for matching acquisitions and dispositions.
- Implement the calculation of capital gains/losses.
- Design and implement the mechanism for generating new journal entries for capital gains transactions.
- Design and implement the safe in-place journal file update mechanism.
- Add comprehensive unit tests for all components of the capital gains tracking tool.
- Integrate the new tool into the CLI.

## Active Decisions and Considerations

- How to best represent the parsed hledger data structure in Python.
- Design of the filtering API.

## Important Patterns and Preferences

- Adhere to Python best practices and maintainable code.
- Prioritize accurate parsing and robust error handling.

## Learnings and Project Insights

- The project involves parsing a domain-specific language (hledger journal format).
- The parsing process will require careful handling of various transaction and posting types.
- Successfully refactored existing `unittest` tests to `pytest` style, improving test readability and maintainability.
