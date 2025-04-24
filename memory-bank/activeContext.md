# Active Context

This document outlines the current focus and active considerations for ledger-parsita development.

## Current Work Focus

- Planning and implementing the capital gains tracking tool.

## Recent Changes

- Initialized and updated memory bank core files based on initial code review.
- Updated `.clinerules` with instruction for Context7 library IDs and created `memory-bank/context7_library_ids.md`.
- Reviewed `README.md`, `src/`, and `tests/` directories.
- Refined `TagFilter` implementation and tests.
- Updated memory bank files (`projectbrief.md`, `productContext.md`, `systemPatterns.md`, `techContext.md`) to reflect the new main goal of capital gains tracking.

## Next Steps

- Define the data structures needed for tracking asset lots and capital gains calculations.
- Implement the logic for identifying closed positions based on journal entries and dated subaccounts.
- Implement the FIFO logic for matching acquisitions and dispositions.
- Implement the calculation of capital gains/losses.
- Design and implement the mechanism for generating new journal entries for capital gains transactions.
- Design and implement the safe in-place journal file update mechanism.
- Add comprehensive unit tests for all components of the capital gains tracking tool.
- Integrate the new tool into the CLI.

## Active Decisions and Considerations

- How to best represent the parsed hledger data structure in Python.
- Design of the filtering API.

## Important Patterns and Preferences

- Adhere to Python best practices and maintainable code.
- Prioritize accurate parsing and robust error handling.

## Learnings and Project Insights

- The project involves parsing a domain-specific language (hledger journal format).
- The parsing process will require careful handling of various transaction and posting types.
