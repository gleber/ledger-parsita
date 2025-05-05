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
- **Balance Sheet Builder Pattern:** The `BalanceSheet` class in `src/balance.py` (specifically its `apply_transaction` instance method and `from_transactions` static method) processes a `Journal` chronologically. The `apply_transaction` method, now refactored for clarity using helper methods (`_apply_direct_posting_effects`, `_process_asset_sale_capital_gains`, `_apply_gain_loss_to_income_accounts`), is responsible for:
    - Calculating running balances for all accounts by updating `Account.own_balances` and `Account.total_balances`.
    - Identifying asset lots (`Lot` objects) with their cost basis upon acquisition and adding them to `AssetBalance.lots`.
    - **Incrementally calculating capital gains/losses upon encountering closing postings (sales):**
        - Performing FIFO matching against available lots tracked within the account structure.
        - Calculating cost basis, proceeds, and gain/loss for matched portions.
        - Updating the `remaining_quantity` of matched `Lot` objects.
        - **Applying the calculated gain/loss by creating synthetic postings to the appropriate income/expense accounts, which in turn updates their balances.**
        - **Storing detailed gain/loss results (`CapitalGainResult` objects) in the `capital_gains_realized` list within the `BalanceSheet`.**
- **Filter Pattern:** A mechanism for applying various criteria to filter transactions and postings. This includes:
    - Defining filter conditions (`BaseFilter` and its subclasses like `AccountFilter`, `DateFilter`, `DescriptionFilter`, `AmountFilter`, `TagFilter`, `BeforeDateFilter`, `AfterDateFilter`, `PeriodFilter`), the `Filters` class, and the `FilterListParamType` in `src/filtering.py`.
    - Using the `FilterListParamType` in `src/main.py` to parse filter strings from the command line into a `Filters` object.
    - Parsing filter queries using `FilterQueryParsers` in `src/filtering.py`, which now supports `before:`, `after:`, and `period:` filters with `YYYY-MM-DD`, `YYYY-MM`, and `YYYY` date formats.
    - Passing the parsed `Filters` object directly to `Journal.parse_from_file` in `src/classes.py`.
    - Using the `Filters.apply_to_entries()` method to filter journal entries.
- **Journal Updater Pattern:** A component responsible for modifying the journal file in place (future implementation, potentially using stored `CapitalGainResult` data).
- **Caching Pattern:** Utilized (`src/classes.py:SourceCacheManager`) for optimizing source position lookups during parsing.

## Component Relationships

- The **Parser** reads the journal file(s) and produces a `Journal` object containing `Transaction` and other entries.
- The `Journal` object's transactions are processed by `BalanceSheet.from_transactions`, which iteratively calls `BalanceSheet.apply_transaction`.
- The `BalanceSheet.apply_transaction` method (and its helpers):
    - Identifies opening postings to create and track `Lot` objects.
    - Upon encountering closing postings, performs FIFO matching, calculates gains/losses, updates lot quantities, and creates synthetic postings to update income/expense account balances. It also stores detailed `CapitalGainResult` objects.
- The final `BalanceSheet` produced contains all account balances (reflecting all transactions, including synthetic ones for capital gains/losses) **and a list of detailed `CapitalGainResult` objects.**
- The **CLI** now uses a custom `click.ParamType` to parse filter strings and passes the resulting `List[BaseFilter]` to `Journal.parse_from_file`.
- The **Caching** mechanism is used internally by the **Parser** and related data classes (`PositionAware`).
- The **Journal Updater** (future) might use stored `CapitalGainResult` data from the `BalanceSheet` to modify the journal file.
- **Balance Printing Methods:**
    - The `Account` class (in `src/balance.py`) now contains `format_hierarchical` (recursive) and `format_flat_lines` methods for formatting its own data. These methods suppress the printing of zero-balance commodity lines and account names if the account (and its children, in hierarchical view) have no non-zero balances to display for the current mode. It also has `get_all_subaccounts` for recursively collecting all its descendants.
    - The `BalanceSheet` class (in `src/balance.py`) methods `format_account_hierarchy` and `format_account_flat` delegate to the `Account` methods to generate the full report, supporting tree/flat views and own/total/both balance display options.

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
