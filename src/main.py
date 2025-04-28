from dataclasses import replace
from typing import Optional, Union
import click
import pprint
from pathlib import Path
from src.filtering import filter_entries
from src.hledger_parser import parse_hledger_journal
from src.classes import Journal, JournalEntry
import re
from parsita import ParseError
from src.classes import Posting, Transaction, sl
from returns.result import Result, Success, Failure # Add import at the beginning
from returns.pipeline import (flow)
from returns.pointfree import (bind)


# Define the main click group
@click.group()
def cli():
    """A command-line tool for parsing hledger journal files."""
    pass

def parse_filter_strip(journal: Journal, flat: bool, strip: bool, query: Optional[str]) -> Result[Journal, Union[ParseError, str, ValueError]]:
    click.echo(f"Successfully parsed hledger journal: {sl(journal.source_location).filename}", err=True)

    filtered_entries = []

    # Apply filtering if a query is provided
    if query:
        filter_result = filter_entries(journal.entries, query)
        match filter_result:
            case Failure(error):
                return Failure(ValueError(f"Error filtering entries: {error}")) # Wrap filtering error in ValueError
            case Success(entries):
                filtered_entries = entries
    else:
        filtered_entries = journal.entries

    filtered_journal = replace(journal, entries=filtered_entries)

    if flat:
        filtered_journal = filtered_journal.flatten()
    if strip:
        filtered_journal = filtered_journal.strip_loc()
    return Success(filtered_journal) # Return Success with the processed journal

# Define the pprint command
@cli.command("pprint")  # Explicitly name the command
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)  # Use Path object
@click.option(
    "-f", "--flat", is_flag=True, help="Flatten the output of the parsed journal."
)
@click.option(
    "-s", "--strip", is_flag=True, help="Strip location information from the output."
)
@click.option(
    "-q", "--query", type=str, default=None, help="Filter transactions using a query string."
)
def pprint_cmd(filename: Path, flat: bool, strip: bool, query: Optional[str]):
    """Parses the journal file and pretty-prints the result."""
    result: Result[Journal, ValueError] = flow(
        str(filename.absolute()),
        parse_hledger_journal,
        bind(lambda journal: parse_filter_strip(journal, flat, strip, query))
    )

    match result:
        case Success(journal):
            pprint.pprint(journal, indent=2)
            exit(0)
        case Failure(error):
            print(f"Error: {error}")
            exit(1)


# Define the print command
@cli.command("print")  # Explicitly name the command
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)  # Use Path object
@click.option(
    "-f", "--flat", is_flag=True, help="Flatten the output of the parsed journal."
)
@click.option(
    "-s", "--strip", is_flag=True, help="Strip location information from the output."
)
@click.option(
    "-q", "--query", type=str, default=None, help="Filter transactions using a query string."
)
def print_cmd(filename: Path, flat: bool, strip: bool, query: Optional[str]):
    """Parses the journal file and prints the result using to_journal_string."""
    parse_result = parse_hledger_journal(str(filename.absolute()))

    match parse_result:
        case Success(journal):
            process_result = parse_filter_strip(journal, flat, strip, query)
            match process_result:
                case Success(processed_journal):
                    print(processed_journal.to_journal_string())
                    exit(0)
                case Failure(error):
                    print(f"Error processing journal: {error}")
                    exit(1)
        case Failure(error):
            print(f"Error parsing journal file: {error}")
            exit(1)


def is_opening_position(posting: Posting) -> bool:
    """Checks if a posting represents an opening position (assets account with positive quantity), excluding assets:cash."""
    return (
        posting.account.name.startswith("assets:")
        and posting.account.name != "assets:cash" # Exclude assets:cash
        and posting.amount is not None
        and posting.amount.quantity > 0
    )

def is_non_dated_account(account_name: str) -> bool:
    """Checks if an account name is non-dated based on the :YYYYMMDD pattern."""
    return not re.search(r":\d{8}$", account_name)

def find_non_dated_opening_transactions(journal: Journal) -> list[Transaction]:
    """Finds transactions with non-dated opening positions."""
    non_dated_opens: list[Transaction] = []
    for entry in journal.entries:
        if entry.transaction: # Check if the entry is a transaction
            for posting in entry.transaction.postings:
                if is_opening_position(posting) and is_non_dated_account(posting.account.name):
                    non_dated_opens.append(entry.transaction)
                    break # Only add the transaction once per entry
    return non_dated_opens

# Define the find-non-dated-opens command
@cli.command("find-non-dated-opens")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def find_non_dated_opens_cmd(filename: Path):
    """Finds transactions opening positions using non-dated subaccounts."""
    parse_result: Result[Journal, Union[ParseError, str, Exception]] = parse_hledger_journal(str(filename.absolute()))

    match parse_result:
        case Failure(error):
            # Print the error message from the Failure and exit with a non-zero status code
            print(f"Error parsing journal file: {error}")
            exit(1)
        case Success(journal):
            # If parsing was successful, unwrap the result and proceed
            parsed_data: Journal = journal
            click.echo(f"Successfully parsed hledger journal: {filename}", err=True)

    non_dated_opens = find_non_dated_opening_transactions(parsed_data)

    if non_dated_opens:
        click.echo("\nTransactions opening positions with non-dated subaccounts:")
        for transaction in non_dated_opens:
            # Access attributes directly from the Transaction object
            source_loc = transaction.source_location
            line_info = f"(Line {source_loc.offset})" if source_loc else "(Line N/A)"
            click.echo(f"- {transaction.date} {transaction.payee} {line_info}")
    else:
        click.echo("\nNo transactions found opening positions with non-dated subaccounts.")

    # Exit with a zero status code on success
    exit(0)


if __name__ == "__main__":
    cli()
