# System Patterns

This document describes the system architecture and key design patterns used in ledger-parsita.

## Architecture

- The system follows a modular design, with separate modules for parsing and filtering.
- **Capital gains tracking is integrated directly into the balance sheet building process.** This is the **implemented architecture**.
- Input hledger journal files are processed chronologically.
- The balance sheet builder reads the entire journal to establish the history of asset acquisitions and dispositions, calculating gains/losses incrementally.

## Key Technical Decisions

- Using Python for development due to its suitability for text processing and data manipulation.
- Using the `parsita` library for parsing the hledger journal format.
- Using the `returns` library for error handling.
- **Implemented a robust FIFO logic by iterating through transactions to find sales and matching them against lots stored in the `BalanceSheet`. This logic is now integrated into the Balance Sheet Builder.**
- **Designing a mechanism for safely updating the hledger journal file in place (future step).**
- **Implemented an in-memory caching mechanism for source position lookups to improve parsing performance.**
- **Each test file must contain at most 500 lines of code; if a file is longer, it should be split into multiple files.**

## Design Patterns

- **Parser Pattern:** A dedicated component (`src/hledger_parser.py`) for parsing the hledger journal format into `Journal` objects.
- **Balance Sheet Builder Pattern:** A component (`src/balance.py`, specifically `calculate_balances_and_lots`) that processes a `Journal` chronologically to create a `BalanceSheet`. It is responsible for:
    - Calculating running balances for all accounts.
    - Identifying asset lots (`Lot` objects) with their cost basis upon acquisition.
    - **Incrementally calculating capital gains/losses upon encountering closing postings (sales):**
        - Performing FIFO matching against available lots tracked within the builder's state.
        - Calculating cost basis, proceeds, and gain/loss for matched portions.
        - Updating the remaining quantity of matched lots.
        - **Applying the calculated gain/loss directly to the running balances of the appropriate income/expense accounts.**
        - **Storing detailed gain/loss results (`CapitalGainResult` objects) in the `capital_gains_realized` list within the `BalanceSheet`.**
- **Filter Pattern:** A mechanism for applying various criteria to filter transactions and postings. This includes:
    - Defining filter conditions, the `Filters` class, and the `FilterListParamType` in `src/filtering.py`.
    - Using the `FilterListParamType` in `src/main.py` to parse filter strings from the command line into a `Filters` object.
    - Passing the parsed `Filters` object directly to `Journal.parse_from_file` in `src/classes.py`.
    - Using the `Filters.apply_to_entries()` method to filter journal entries.
- **Journal Updater Pattern:** A component responsible for modifying the journal file in place (future implementation, potentially using stored `CapitalGainResult` data).
- **Caching Pattern:** Utilized (`src/classes.py:SourceCacheManager`) for optimizing source position lookups during parsing.

## Component Relationships

- The **Parser** reads the journal file(s) and produces a `Journal` object containing `Transaction` and other entries.
- The `Journal` object is passed to the **Balance Sheet Builder** (`calculate_balances_and_lots`).
- The **Balance Sheet Builder** iterates through the `Journal`'s transactions:
    - It identifies opening postings to create and track `Lot` objects.
    - Upon encountering closing postings, it performs FIFO matching against tracked lots, calculates gains/losses, updates lot quantities, and **updates the running balances of income/expense accounts directly within the `BalanceSheet` being built.** It also stores detailed `CapitalGainResult` objects in the `BalanceSheet`.
- The final `BalanceSheet` produced by the builder contains all account balances (including the incrementally calculated capital gains/losses reflected in income/expense accounts) **and a list of detailed `CapitalGainResult` objects.**
- The **CLI** now uses a custom `click.ParamType` to parse filter strings and passes the resulting `List[BaseFilter]` to `Journal.parse_from_file`.
- The **Caching** mechanism is used internally by the **Parser** and related data classes (`PositionAware`).
- The **Journal Updater** (future) might use stored `CapitalGainResult` data from the `BalanceSheet` to modify the journal file.

## Critical Implementation Paths

- Accurate and efficient parsing of all valid hledger syntax.
- **Correct implementation of the integrated FIFO logic within the Balance Sheet Builder (`src/balance.py`), ensuring:**
    - Accurate matching of sales transactions against tracked lots.
    - Correct updating of remaining lot quantities.
    - Accurate calculation of proceeds, cost basis, and gain/loss for each matched portion.
    - **Correct application of calculated gains/losses to the running balances of income/expense accounts.**
    - **Correct storage of detailed `CapitalGainResult` objects within the `BalanceSheet`.**
- Safe and reliable in-place modification of the journal file (future).
- Designing a flexible and performant filtering engine.
- Ensuring the caching mechanism provides significant performance improvements for large journals.
