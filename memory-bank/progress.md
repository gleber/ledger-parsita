# Progress

This document tracks the progress, completed features, and remaining tasks for ledger-parsita.

## What Works

- Initial memory bank files have been created and updated to reflect the new project goal.
- Hledger journal parser is implemented using `parsita` with good test coverage.
- Data classes for representing parsed journal entries are defined.
- Filtering logic for account, date, description, amount, and tags is implemented and tested.

## What's Left to Build

- **Implement the capital gains tracking tool, including:**
    - Data structures for asset lots.
    - Logic for identifying closed positions and applying FIFO.
    - Capital gains/loss calculation.
    - Generation of new journal entries for gains/losses.
    - Safe in-place journal file update mechanism.
- Add comprehensive unit tests for the capital gains tracking tool.
- Integrate the capital gains tracking tool into the CLI.
- Ensure comprehensive test coverage for all filtering scenarios and edge cases.
- Implement additional filter types if needed (future).
- Develop other reporting features (future).

## Current Status

- The project's main goal has shifted to implementing the capital gains tracking tool.
- Initial planning for the capital gains tracking tool is underway, reflected in the updated memory bank files.

## Known Issues

- None identified at this time.

## Evolution of Project Decisions

- The decision to use `devenv.nix` for environment management has been made.
- The decision to use `parsita` for parsing has been made.
- **The main project focus is now on implementing the capital gains tracking tool using dated subaccounts and FIFO logic.**
