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
- Attempted to fix failing capital gains tests, but the cause of the failures is unclear and may be related to test data or environment issues.
- Added `isCash()` method to `Commodity` class and used it in `capital_gains.py` to exclude cash-only transactions.
- Added tests to `tests/test_capital_gains.py` to ensure cash transactions are excluded.
- **All currently implemented tests are passing (including fixes for journal flattening and journal string conversion).**

## What's Left to Build

- **Implement the capital gains tracking tool, including:**
    - Logic to find open positions which match closed positions using FIFO ordering.
    - Safe in-place journal file update mechanism so that dated lot of open and closed positions are the same.
- Add comprehensive unit tests for the capital gains tracking tool.
- Ensure comprehensive test coverage for all filtering scenarios and edge cases.
- Implement additional filter types if needed (future).
- Develop other reporting features (future).
- Added CLI command `find-positions` to find open and close transactions.

## Current Status

- The project's main goal has shifted to implementing the capital gains tracking tool.
- Initial planning for the capital gains tracking tool is underway, reflected in the updated memory bank files.
- Added tests for `AccountName.isAsset()` and related capital gains functions, but some tests are currently failing. The cause is unclear and requires further investigation, potentially related to test data or environment configuration.
- **All currently implemented tests are passing.**

## Known Issues

- None.

## Evolution of Project Decisions

- The decision to use `devenv.nix` for environment management has been made.
- The decision to use `parsita` for parsing has been made.
- **The main project focus is now on implementing the capital gains tracking tool using dated subaccounts and FIFO logic.**
