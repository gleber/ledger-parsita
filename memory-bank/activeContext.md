# Active Context

This document outlines the current focus and active considerations for ledger-parsita development.

## Current Work Focus

- Refactoring the balance sheet building process (`src/balance.py`) to integrate incremental capital gains calculation.

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
- **Implemented a caching mechanism for `set_filename` and `_calculate_line_column` using a `SourceCacheManager` in `src/classes.py` to improve parsing performance for large journals with includes.**
- **Modified `PositionAware.set_filename` to use the `SourceCacheManager` for efficient line/column calculation.**
- **Resolved an `ImportError` in `tests/test_filtering.py` and an `AttributeError` in `SourceCacheManager` during testing.**
- **Changed `SourceCacheManager` to use `__init__` instead of `__new__` while keeping the global instance, as requested.**
- Added `isCrypto()` method to `Commodity` class in `src/classes.py` and added tests for it in `tests/test_classes.py`.
- Fixed `AttributeError: 'Account' object has no attribute 'isAsset'` in `src/main.py` by accessing `account.name.isAsset()`.
- Added a rule that each test file must contain at most 500 lines of code.

## Next Steps

**Phase 1: Integrate Capital Gains Calculation into Balance Sheet Builder**
1.  **Move Logic:** Transfer the core FIFO matching and gain/loss calculation logic from `src/capital_gains.py::calculate_capital_gains` into `src/balance.py`, likely as a helper function called by `calculate_balances_and_lots`.
2.  **Modify `calculate_balances_and_lots` (`src/balance.py`):**
    *   Integrate the call to the moved FIFO logic when a closing posting is encountered.
    *   Ensure the logic correctly updates the `remaining_quantity` of lots tracked within the `BalanceSheet` state.
    *   **Implement the application of calculated gains/losses to the running balances of appropriate income/expense accounts (e.g., `income:capital_gains`, `expenses:capital_losses`) within the `BalanceSheet` object being built.**
    *   Optionally, add logic to store `CapitalGainResult` objects in the `BalanceSheet`.
3.  **Refactor/Remove `src/capital_gains.py`:** Remove the now redundant `calculate_capital_gains` function. Decide whether to keep/move `CapitalGainResult`.
4.  **Update `BalanceSheet` Class (Optional):** Consider adding `capital_gains_realized: List[CapitalGainResult]` field in `src/classes.py`.
5.  **Update Tests:**
    *   Adapt/move tests from `tests/test_capital_gains_fifo.py` to `tests/test_balance.py`.
    *   Add new tests in `tests/test_balance.py` to verify the integrated calculation and its impact on income/expense balances and lot quantities.

**Phase 2: Future Steps**
- Design and implement the mechanism for generating new journal entries for capital gains transactions (potentially using stored `CapitalGainResult` data).
- Design and implement the safe in-place journal file update mechanism.
- Check existing test files to ensure they adhere to the new 500-line limit and split them if necessary.

## Active Decisions and Considerations

- **Integrating capital gains calculation directly into the balance sheet building process.**
- How to efficiently track lots and apply gains/losses to running balances within `calculate_balances_and_lots`.
- Determining the appropriate income/expense accounts for posting gains/losses (e.g., `income:capital_gains`, `expenses:capital_losses`).
- Structure and storage of `CapitalGainResult` objects if needed for future journal updates.
- Design of the filtering API.
- Implementation details of the in-memory caching for source position lookups.

## Important Patterns and Preferences

- Adhere to Python best practices and maintainable code.
- Prioritize accurate parsing and robust error handling.
- Utilize the implemented caching mechanism for efficient source position lookups.

## Learnings and Project Insights

- The project involves parsing a domain-specific language (hledger journal format).
- The parsing process will require careful handling of various transaction and posting types.
- Successfully refactored existing `unittest` tests to `pytest` style, improving test readability and maintainability.
- Gained experience in implementing and integrating in-memory caching for performance optimization.
- Encountered and resolved issues related to file path handling and import mechanisms during development.
