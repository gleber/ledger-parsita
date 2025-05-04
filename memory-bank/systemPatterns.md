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
- **Implementing a robust FIFO logic for matching asset acquisitions and dispositions.**
- **Designing a mechanism for safely updating the hledger journal file in place.**
- **Implemented an in-memory caching mechanism for source position lookups to improve parsing performance.**

## Design Patterns

- **Parser Pattern:** A dedicated component for parsing the hledger journal format.
- **Filter Pattern:** A mechanism for applying various criteria to filter transactions and postings (may be used to identify relevant investment transactions).
- **Capital Gains Tracker Pattern:** A new component responsible for identifying closed positions, applying FIFO, calculating gains/losses, and generating new journal entries.
- **Journal Updater Pattern:** A component for modifying the journal file in place.
- **Caching Pattern:** Utilized for optimizing source position lookups during parsing.

## Component Relationships

- The parser component feeds parsed data to the capital gains tracker.
- The capital gains tracker may utilize the filtering component.
- The capital gains tracker generates new journal entries.
- The journal updater modifies the original journal file based on the generated entries.
- The caching mechanism is used by the parsing component.

## Critical Implementation Paths

- Accurate and efficient parsing of all valid hledger syntax.
- **Correct implementation of FIFO logic considering dated subaccounts.**
- **Safe and reliable in-place modification of the journal file.**
- Designing a flexible and performant filtering engine (for potential use in identifying investment transactions).
- **Ensuring the caching mechanism provides significant performance improvements for large journals.**
