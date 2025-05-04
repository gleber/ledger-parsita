# Active Context

This document outlines the current focus and active considerations for ledger-parsita development.

## Current Work Focus

- Removing the non-functional `closing_postings` mechanism.
- Reimplementing the FIFO matching logic for capital gains calculation.
- Completed performance optimization for source position lookups during parsing.

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
- **Planned the removal of the non-functional `closing_postings` mechanism and the reimplementation strategy for FIFO matching.**
- Added `isCrypto()` method to `Commodity` class in `src/classes.py` and added tests for it in `tests/test_classes.py`.
- Fixed `AttributeError: 'Account' object has no attribute 'isAsset'` in `src/main.py` by accessing `account.name.isAsset()`.
- Added a rule that each test file must contain at most 500 lines of code.

## Next Steps

- **Phase 1: Removal**
    - Modify `src/balance.py`: Remove code attempting to use `account.closing_postings`.
    - Modify `src/capital_gains.py`: Remove the old `match_fifo` function.
- **Phase 2: Reimplementation**
    - Create new function `calculate_capital_gains(transactions: List[Transaction], balance_sheet: BalanceSheet)` in `src/capital_gains.py`.
    - Implement core FIFO logic within `calculate_capital_gains`:
        - Track remaining lot quantities mutably.
        - Iterate transactions to find closing postings (`posting.isClosing()`).
        - Determine proceeds from the same transaction.
        - Match closing quantity against available lots (FIFO).
        - Calculate cost basis, proceeds, and gain/loss for each match.
        - Update remaining lot quantities.
    - Define `CapitalGainResult` dataclass to structure the output.
    - Integrate the new `calculate_capital_gains` function into the CLI (`src/main.py`).
    - Add comprehensive `pytest` tests for the new logic.
- Design and implement the mechanism for generating new journal entries for capital gains transactions (future step after calculation works).
- Design and implement the safe in-place journal file update mechanism (future step).
- Check existing test files to ensure they adhere to the new 500-line limit and split them if necessary.

## Active Decisions and Considerations

- How to best represent the parsed hledger data structure in Python.
- Design of the filtering API.
- Implementation details of the in-memory caching for source position lookups.
- Specific approach for FIFO matching: Iterate transactions, use `BalanceSheet` lots, track remaining quantity mutably.

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
- Identified non-functional code (`closing_postings` mechanism) and planned its removal and replacement.
