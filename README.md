# Ledger Parsita

This project provides a Python library for parsing [hledger](https://hledger.org/) journal files. It uses the `parsita` library to define the grammar and parse the journal entries.

## Features

*   Parses hledger journal files, including:
    *   Transactions with status, code, payee, postings, and comments.
    *   Postings with account names, amounts (with or without currency), costs, and balance assertions.
    *   `include` directives for handling multiple files.
    *   `commodity` directives.
    *   `account` directives.
    *   `alias` directives.
    *   `P` (price) directives.
    *   Top-level comments.
*   Provides Python classes to represent the parsed journal structure (Transactions, Postings, Amounts, etc.).
*   Includes source location information (filename, offset, length) for parsed elements.
*   Handles recursive includes.

## Setup

This project uses `uv` for environment and package management.

1.  **Install `uv`:**
    If you don't have `uv` installed, follow the instructions on the [official `uv` installation guide](https://github.com/astral-sh/uv#installation).

2.  **Create and activate the virtual environment:**
    ```bash
    # Create the virtual environment (usually named .venv)
    uv venv

    # Activate the virtual environment
    # On Linux/macOS:
    source .venv/bin/activate
    # On Windows (Command Prompt):
    # .venv\Scripts\activate.bat
    # On Windows (PowerShell):
    # .venv\Scripts\Activate.ps1
    ```

3.  **Install dependencies:**
    Once the virtual environment is activated, install the required packages using `uv`:
    ```bash
    uv pip install -r requirements.txt
    ```

## Usage

You can use the `parse_hledger_journal` function from `src.hledger_parser` to parse a journal file:

```python
from src.hledger_parser import parse_hledger_journal
from pathlib import Path

# Example usage:
journal_file = Path("examples/taxes/all.journal")
try:
    parsed_journal = parse_hledger_journal(str(journal_file))
    print(f"Successfully parsed {journal_file}")
    print(f"Parsed {len(parsed_journal)} top-level entries.")

    # Access parsed data (e.g., transactions, postings)
    for entry in parsed_journal.entries:
        if entry.transaction:
            print(f"Transaction on {entry.transaction.date}: {entry.transaction.payee}")
            for posting in entry.transaction.postings:
                print(f"  Posting: {posting.account.full_name()} {posting.amount}")

except FileNotFoundError:
    print(f"Error: File not found at {journal_file}")
except Exception as e: # Catch potential parsing errors from parsita
    print(f"An error occurred during parsing: {e}")

```

## Running Tests

The project includes unit tests using Python's built-in `unittest` module. To run the tests:

1.  Make sure you have activated the virtual environment and installed dependencies.
2.  Run the tests from the project's root directory:

    ```bash
    python -m unittest discover -s tests
    ```

This command will automatically discover and run all tests within the `tests` directory.
