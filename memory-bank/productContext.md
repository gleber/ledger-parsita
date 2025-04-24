# Product Context

This document describes the product context for ledger-parsita.

## Problem Solved

ledger-parsita now aims to provide a dedicated tool for tracking capital gains from closed investment positions recorded in hledger journal files. This automates the process of calculating gains/losses based on dated subaccounts and FIFO logic, and records the results directly in the journal.

## How it Should Work

The tool will:
- Read and parse an hledger journal file.
- Identify transactions representing the closing of investment positions.
- Use dated subaccounts (e.g., `assets:broker:tastytrade:MSTR:20240414`) to determine the acquisition date and cost basis of the sold lots.
- Apply First-In, First-Out (FIFO) logic to match sold lots with acquired lots.
- Calculate the capital gain or loss for each closed position.
- Generate new transactions to record the calculated capital gains/losses.
- Update the original hledger journal file in place with these new transactions.

## User Experience Goals

- Provide an easy-to-use command-line interface for triggering the capital gains calculation and journal update.
- Clearly report the calculated capital gains/losses to the user.
- Ensure the in-place update of the journal file is safe and preserves data integrity.
- Allow users to specify which accounts and commodities to track for capital gains.
- Provide options for handling different scenarios (e.g., wash sales - future consideration).
- Maintain fast and efficient processing, even for large journal files with many transactions.
