# System Patterns

This document describes the system architecture and key design patterns used in ledger-parsita.

## Architecture

- The system follows a modular design, with separate modules for parsing, filtering, and capital gains tracking.
- Input hledger journal files are processed to identify relevant transactions for capital gains calculation.
- The tool will need to read the entire journal to establish the history of asset acquisitions and dispositions.

## Key Technical Decisions

- Using Python for development due to its suitability for text processing and data manipulation.
- Using the `parsita` library for parsing the hledger journal format.
- Using the `returns` library for error handling.
- **Removing the non-functional `closing_postings` mechanism.**
- **Implementing a robust FIFO logic by iterating through transactions to find sales and matching them against lots stored in the `BalanceSheet`.**
- **Designing a mechanism for safely updating the hledger journal file in place (future step).**
- **Implemented an in-memory caching mechanism for source position lookups to improve parsing performance.**
- **Each test file must contain at most 500 lines of code; if a file is longer, it should be split into multiple files.**

## Design Patterns

- **Parser Pattern:** A dedicated component (`src/hledger_parser.py`) for parsing the hledger journal format into `Journal` objects.
- **Balance Sheet Builder Pattern:** A component (`src/balance.py`) that processes a `Journal` to create a `BalanceSheet`, calculating balances and identifying asset lots with their cost basis.
- **Filter Pattern:** A mechanism (`src/filtering.py`) for applying various criteria to filter transactions and postings.
- **Capital Gains Calculator Pattern:** A component (`src/capital_gains.py`, specifically the planned `calculate_capital_gains` function) responsible for:
    - Taking the full list of `Transaction` objects and the `BalanceSheet` as input.
    - Iterating through transactions to identify closing postings (sales).
    - Matching sales against available lots from the `BalanceSheet` using FIFO logic.
    - Calculating gains/losses for each match.
    - Returning structured results (e.g., `CapitalGainResult` objects).
- **Journal Updater Pattern:** A component responsible for modifying the journal file in place (future implementation).
- **Caching Pattern:** Utilized (`src/classes.py:SourceCacheManager`) for optimizing source position lookups during parsing.

## Component Relationships

- The **Parser** reads the journal file(s) and produces a `Journal` object containing `Transaction` and other entries.
- The `Journal` object is passed to the **Balance Sheet Builder** (`calculate_balances_and_lots`) which produces a `BalanceSheet` containing accounts, balances, and identified asset `Lot` objects.
- Both the original `Journal` (specifically, its list of `Transaction` objects) and the generated `BalanceSheet` are passed as input to the **Capital Gains Calculator** (`calculate_capital_gains`).
- The **Capital Gains Calculator** uses the transactions to find sales and the `BalanceSheet` lots to perform FIFO matching and calculations.
- The **Filter** component might be used by the CLI or potentially by the Calculator to narrow down transactions/accounts if needed.
- The **Caching** mechanism is used internally by the **Parser** and related data classes (`PositionAware`).
- The **Journal Updater** (future) will take results from the Calculator to modify the journal file.

## Critical Implementation Paths

- Accurate and efficient parsing of all valid hledger syntax.
- **Correct implementation of the new FIFO logic within `calculate_capital_gains`, ensuring accurate matching of sales transactions against `BalanceSheet` lots.**
- **Accurate calculation of proceeds, cost basis, and gain/loss for each matched portion.**
- Safe and reliable in-place modification of the journal file (future).
- Designing a flexible and performant filtering engine.
- Ensuring the caching mechanism provides significant performance improvements for large journals.
