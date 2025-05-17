# Product Context

This document describes the product context for ledger-parsita.

## Problem Solved

ledger-parsita now aims to provide a dedicated tool for tracking capital gains from closed investment positions (both long and short) recorded in hledger journal files. This automates the process of calculating gains/losses based on dated subaccounts (for long positions) or initial sale proceeds (for short positions) and FIFO logic, storing the results.

## How it Should Work

The tool will:
- Read and parse an hledger journal file.
- As part of building the balance sheet:
    - Identify transactions representing the opening and closing of investment positions (long and short).
    - For long positions, use dated subaccounts (e.g., `assets:broker:tastytrade:MSTR:20240414`) to determine the acquisition date and cost basis of the acquired lots.
    - For short positions (identified by a `type:short` tag on the opening sale), record the proceeds received as the basis for the short lot.
    - Apply First-In, First-Out (FIFO) logic to match closing transactions (sales for long positions, buy-to-cover for short positions) with their corresponding opening lots.
    - Calculate the capital gain or loss for each closed portion of a position and store these results.
      - For long positions: Gain/Loss = Proceeds from sale - Cost Basis.
      - For short positions: Gain/Loss = Initial Proceeds from short sale - Cost to Cover.
- (Future) Generate new transactions to record the calculated capital gains/losses.
- (Future) Update the original hledger journal file in place with these new transactions.

## User Experience Goals

- Provide an easy-to-use command-line interface (CLI) with commands like `balance` (for account balances) and `gains` (for capital gains reporting).
- Clearly report the calculated capital gains/losses to the user via the `gains` command.
- (Future) Ensure the in-place update of the journal file is safe and preserves data integrity.
- Allow users to specify which accounts and commodities to track for capital gains.
- Provide options for handling different scenarios (e.g., wash sales - future consideration).
- Maintain fast and efficient processing, even for large journal files with many transactions.
