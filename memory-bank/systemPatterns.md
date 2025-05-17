# System Patterns

This document describes the system architecture and key design patterns used in ledger-parsita.

## Architecture

- The system follows a modular design, with separate modules for parsing and filtering.
- Capital gains tracking is integrated directly into the balance sheet building process. This is the implemented architecture.
- Input hledger journal files are processed chronologically.
- The balance sheet builder reads the entire journal to establish the history of asset acquisitions and dispositions, calculating gains/losses incrementally.

## Key Technical Decisions

- Using Python for development due to its suitability for text processing and data manipulation.
- Using the `parsita` library for parsing the hledger journal format.
- Using the `returns` library for error handling, particularly the `Result` pattern (`Success`, `Failure`).
- Implemented a robust FIFO logic by iterating through transactions to find sales and matching them against lots stored in the `BalanceSheet`. This logic is now integrated into the Balance Sheet Builder.
- Designing a mechanism for safely updating the hledger journal file in place (future step).
- Implemented an in-memory caching mechanism for source position lookups to improve parsing performance.
- Each test file must contain at most 500 lines of code; if a file is longer, it should be split into multiple files.

## Design Patterns

- Parser Pattern: A dedicated component (`src/hledger_parser.py`) for parsing the hledger journal format into `Journal` objects.
- Balance Sheet Builder Pattern: The `BalanceSheet` class in `src/balance.py` (with static methods `from_journal` and `from_transactions`, and instance method `apply_transaction`) processes a `Journal` chronologically.
    - The `Posting` class now has a `get_effect()` method returning a `TransactionPositionEffect` enum (e.g., `OPEN_LONG`, `CLOSE_LONG`, `OPEN_SHORT`, `CLOSE_SHORT`) to classify postings.
    - The `Lot` dataclass now includes an `is_short: bool` field.
    - `Lot.try_create_from_posting` (static method) now uses `posting.get_effect()` to identify and create `Lot` objects for both long acquisitions and opening short positions (where `is_short=True`, quantity is negative, and `cost_basis_per_unit` stores the proceeds received).
    - The `BalanceSheet.apply_transaction` method orchestrates processing:
        - It determines the `TransactionPositionEffect` of each posting.
        - For postings that are effectively closing a short position (an `OPEN_LONG` effect on an account with existing short lots), it calls `_process_short_closure_capital_gains`.
        - For `CLOSE_LONG` effects, it calls `_process_long_sale_capital_gains` (renamed from `_process_asset_sale_capital_gains`).
        - For genuine `OPEN_LONG` or `OPEN_SHORT` effects that are not closing existing positions, and for cash movements, it calls `_apply_direct_posting_effects`.
    - `_apply_direct_posting_effects`:
        - Updates own balances.
        - Creates `Lot` objects for new long or short positions via `Lot.try_create_from_posting`.
    - `_process_long_sale_capital_gains` (formerly `_process_asset_sale_capital_gains`):
        - Consolidates proceeds using `BalanceSheet._get_consolidated_proceeds`.
        - Performs FIFO matching against long lots using `BalanceSheet._perform_fifo_matching_and_gains_for_long_closure` (renamed from `_perform_fifo_matching_and_gains`).
    - New `_process_short_closure_capital_gains`:
        - Consolidates cost to cover using the new static helper `BalanceSheet._get_consolidated_cost_to_cover`.
        - Performs FIFO matching against short lots using the new static helper `BalanceSheet._perform_fifo_matching_and_gains_for_short_closure`.
    - Overall responsibilities include:
        - Calculating running balances for all accounts.
        - Identifying asset lots (`Lot` objects), including their `is_short` status, cost basis (for longs) or initial proceeds (for shorts), and adding them to `AssetBalance.lots`.
        - Incrementally calculating capital gains/losses upon encountering closing postings (sales for longs, buy-to-covers for shorts).
            - Performing FIFO matching against available lots (delegated to specific helpers for long/short).
        - Calculating cost basis, proceeds, and gain/loss for matched portions.
        - Updating the `remaining_quantity` of matched `Lot` objects.
        - Applying the calculated gain/loss by creating synthetic postings to the appropriate income/expense accounts, which in turn updates their balances.
        - Storing detailed gain/loss results (`CapitalGainResult` objects) in the `capital_gains_realized` list within the `BalanceSheet`.
        - Conditions that previously issued warnings (e.g., insufficient lots, mismatched commodities) now raise `ValueError` exceptions, making them fatal. The "no proceeds" condition is now handled via the `Result` pattern from `_get_consolidated_proceeds`.
- Filter Pattern: A mechanism for applying various criteria to filter transactions and postings. This includes:
    - Defining filter conditions (`BaseFilter` and its subclasses like `AccountFilter`, `DateFilter`, `DescriptionFilter`, `AmountFilter`, `TagFilter`, `BeforeDateFilter`, `AfterDateFilter`, `PeriodFilter`), the `Filters` class, and the `FilterListParamType` in `src/filtering.py`.
    - Using the `FilterListParamType` in `src/main.py` to parse filter strings from the command line into a `Filters` object.
    - Parsing filter queries using `FilterQueryParsers` in `src/filtering.py`, which now supports `before:`, `after:`, and `period:` filters with `YYYY-MM-DD`, `YYYY-MM`, and `YYYY` date formats.
    - Passing the parsed `Filters` object directly to `Journal.parse_from_file` in `src/classes.py`.
    - Using the `Filters.apply_to_entries()` method to filter journal entries.
- Journal Updater Pattern: A component responsible for modifying the journal file in place (future implementation, potentially using stored `CapitalGainResult` data).
- Caching Pattern: Utilized (`src/classes.py:SourceCacheManager`) for optimizing source position lookups during parsing.
- Result Pattern: Used with `returns.result.Result` (`Success`, `Failure`) for functions that can fail in predictable ways, such as `BalanceSheet._get_consolidated_proceeds`. This enhances error handling by making failure cases explicit and type-safe.
- Maybe Pattern: Used with `returns.maybe.Maybe` (`Some`, `Nothing`) for functions that can return an optional value (e.g., `Lot.try_create_from_posting`, `Account.get_account`, `BalanceSheet.get_account`). This makes handling of potentially absent values more explicit.
- Transaction Validation Pattern: The `Transaction` class in `src/classes.py` now includes methods (`validate_internal_consistency`, `is_balanced`) for checking its own integrity and balance based on its postings.
    - The `balance` method (which now calls the standalone `_transaction_balance` function from `src/transaction_balance.py`), if successful in resolving elided amounts, results in a transaction copy where a comment "; auto-balanced" is added to the postings whose amounts were calculated. This comment is appended to any existing comment on the posting.
    - This uses the `Result` pattern and custom error types (`TransactionIntegrityError`, `TransactionBalanceError` and their subtypes) for clear error reporting.

## Component Relationships

- The Parser reads the journal file(s) and produces a `Journal` object containing `Transaction` and other entries. Each `Transaction` object can now self-validate its internal consistency and whether its postings balance per commodity.
- The `Journal` object is processed by `BalanceSheet.from_journal` (which internally uses `BalanceSheet.from_transactions` that iteratively calls `BalanceSheet.apply_transaction`).
- The `BalanceSheet.apply_transaction` method:
    - Uses `posting.get_effect()` to determine the nature of the posting.
    - If an `OPEN_LONG` effect occurs on an account with existing short lots, it's treated as a `CLOSE_SHORT` and routes to `_process_short_closure_capital_gains`.
    - Otherwise, for `CLOSE_LONG`, it calls `_process_long_sale_capital_gains`.
    - For genuine `OPEN_LONG` or `OPEN_SHORT` (not closing existing positions), it calls `_apply_direct_posting_effects` which uses `Lot.try_create_from_posting` to create the new lot.
    - `_process_long_sale_capital_gains` uses `_get_consolidated_proceeds` and `_perform_fifo_matching_and_gains_for_long_closure`.
    - `_process_short_closure_capital_gains` uses `_get_consolidated_cost_to_cover` and `_perform_fifo_matching_and_gains_for_short_closure`.
- The final `BalanceSheet` produced contains all account balances and a list of detailed `CapitalGainResult` objects for both long and short position closures.
- The CLI (`src/main.py`):
    - Uses a custom `click.ParamType` to parse filter strings.
    - Calls `Journal.parse_from_file` to get a `Journal` object (or a `Failure`).
    - Handles `Result` objects using an early return pattern (`is_successful`).
    - For `balance` and `gains` commands, calls `BalanceSheet.from_journal` and catches potential `ValueErrors` from capital gains calculations (including those propagated from `Failure` cases in `_get_consolidated_proceeds`).
    - The `balance` command displays account balances.
    - The `gains` command displays capital gains results.
- The Caching mechanism is used internally by the Parser and related data classes (`PositionAware`).
- The Journal Updater (future) might use stored `CapitalGainResult` data from the `BalanceSheet` to modify the journal file.
- Balance Printing Methods:
    - The `Account` class (in `src/balance.py`) now contains `format_hierarchical` (recursive) and `format_flat_lines` methods for formatting its own data. These methods suppress the printing of zero-balance commodity lines and account names if the account (and its children, in hierarchical view) have no non-zero balances to display for the current mode. It also has `get_all_subaccounts` for recursively collecting all its descendants.
    - The `BalanceSheet` class (in `src/balance.py`) methods `format_account_hierarchy` and `format_account_flat` delegate to the `Account` methods to generate the full report, supporting tree/flat views and own/total/both balance display options.

## Critical Implementation Paths

- Accurate and efficient parsing of all valid hledger syntax.
- Correct implementation of the integrated FIFO logic within the Balance Sheet Builder (`src/balance.py`), ensuring:
    - Accurate matching of sales transactions against tracked lots.
    - Correct updating of remaining lot quantities.
    - Accurate calculation of proceeds, cost basis, and gain/loss for each matched portion.
    - Correct application of calculated gains/losses to the running balances of income/expense accounts.
    - Correct storage of detailed `CapitalGainResult` objects within the `BalanceSheet`.
    - Robust error handling for problematic capital gains scenarios (now using `ValueError` for most fatal issues and `Result` pattern for `_get_consolidated_proceeds`).
- Safe and reliable in-place modification of the journal file (future).
- Designing a flexible and performant filtering engine.
- Ensuring the caching mechanism provides significant performance improvements for large journals.
