# Progress

This document tracks the progress, completed features, and remaining tasks for ledger-parsita.

## What Works

- Initial memory bank files have been created and updated to reflect the new project goal.
- Hledger journal parser is implemented using `parsita` with good test coverage.
- Data classes for representing parsed journal entries are defined.
- Filtering logic for account, date, description, amount, and tags is implemented and tested.
- Added `isAsset()` method to `AccountName` and used it in `capital_gains.py`.
- Added tests for `AccountName.isAsset()` in `tests/test_classes.py`.
- Added tests for capital gains functions using `isAsset()` in `tests/test_capital_gains.py`.
- Added `getKey()` method to `Transaction` and used it in capital gains functions for tracking seen transactions.
- Refactored capital gains finding functions using a higher-order function to deduplicate logic.
- Added `isCash()` method to `Commodity` class and used it in `capital_gains.py` to exclude cash-only transactions.
- Added tests to `tests/test_capital_gains.py` to ensure cash transactions are excluded.
- The `isDatedSubaccount` method was found to be already implemented and tested in `src/classes.py`.
- Added CLI command `find-positions` to find open and close transactions.
- **Tests in `tests/test_classes.py`, `tests/test_journal_flattening.py`, and `tests/test_main.py` have been refactored to pytest style and are passing.**
- **Implemented a caching mechanism for `set_filename` and `_calculate_line_column` to improve parsing performance.**
- **Resolved import and attribute errors encountered during the implementation and testing of the caching mechanism.**
- Added `isCrypto()` method to `Commodity` class in `src/classes.py` and added tests for it in `tests/test_classes.py`.
- Fixed `AttributeError: 'Account' object has no attribute 'isAsset'` in `src/main.py`.
- **Completed Phase 1: Integrated Capital Gains Calculation into Balance Sheet Builder:**
    - Integrated FIFO matching and gain/loss calculation logic into `src/balance.py::calculate_balances_and_lots`.
    - `calculate_balances_and_lots` now incrementally applies gains/losses to income/expense account balances.
    - `CapitalGainResult` dataclass moved to `src/classes.py` and updated to include date fields.
    - `calculate_balances_and_lots` now stores detailed `CapitalGainResult` objects in the `BalanceSheet.capital_gains_realized` list.
    - CLI command `balance` in `src/main.py` updated to display capital gains from the `BalanceSheet`.
    - Tests moved and adapted to `tests/test_balance.py` to verify integrated logic.
    - All tests pass after fixing issues related to the integration (`AttributeError`, `AssertionError`, `IndentationError`, Mypy errors).
- **Refactored Balance Calculation:**
    - Split `calculate_balances_and_lots` into `BalanceSheet.apply_transaction` (incremental) and `build_balance_sheet_from_transactions` (using `reduce`).
    - Updated all relevant tests and `src/main.py` to use the new function.
    - All tests pass after refactoring.
- Refactored `build_balance_sheet_from_transactions` into the static method `BalanceSheet.from_transactions`.
- Refactored `parse_hledger_journal` and `parse_hledger_journal_content` into static methods `Journal.parse_from_file` and `Journal.parse_from_content` within `src/classes.py`, resolving circular import issues.

## What's Left to Build

- Check existing test files for adherence to the 500-line limit and split if necessary.
- Implement generation of capital gains journal entries.
- Implement safe in-place journal file update mechanism.
- Ensure comprehensive test coverage for all filtering scenarios and edge cases.
- Implement additional filter types if needed (future).
- Develop other reporting features (future).

## Current Status

- **Phase 1 (Integration of Capital Gains Calculation into Balance Sheet Builder) is complete.**
- **Refactoring of balance calculation logic is complete.**
- The performance optimization for source position lookups during parsing has been completed and verified by passing tests.
- Ready to begin Phase 2 (Generating journal entries, updating files).

## Known Issues

- None.

## Evolution of Project Decisions

- The decision to use `devenv.nix` for environment management has been made.
- The decision to use `parsita` for parsing has been made.
- **The main project focus is now on implementing the capital gains tracking tool using dated subaccounts and FIFO logic.**
- **Adopted pytest as the testing framework and refactored existing tests.**
- **Implemented an in-memory caching mechanism for source position lookups to improve parsing performance.**
- **Decided to remove the non-functional `closing_postings` mechanism.**
- **Planned the reimplementation strategy for FIFO matching based on iterating transactions and using `BalanceSheet` lots.** (Implemented in Phase 1)
- **Decided that each test file must contain at most 500 lines of code to improve maintainability.**
- **Decided to store detailed `CapitalGainResult` objects within the `BalanceSheet` for potential future use (e.g., journal updates).**
