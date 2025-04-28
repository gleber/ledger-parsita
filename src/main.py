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
from src.classes import Posting, Transaction
from returns.result import Result, Success, Failure # Add import at the beginning


# Define the main click group
@click.group()
def cli():
    """A command-line tool for parsing hledger journal files."""
    pass

def parse_filter_strip(parse_result: Result[Journal, Union[ParseError, str]], flat: bool, strip: bool, query: Optional[str]) -> Result[Journal, Union[ParseError, str, ValueError]]:
    # Handle the initial parsing result
    if isinstance(parse_result, Failure):
        return parse_result # Propagate the parsing failure

    parsed_data: Journal = parse_result.unwrap() # Unwrap the Success result

    click.echo(f"Successfully parsed hledger journal: {parsed_data.source_location.filename}", err=True)

    filtered_entries = []

    # Apply filtering if a query is provided
    if query:
        filter_result = filter_entries(parsed_data.entries, query)
        if isinstance(filter_result, Failure):
            return Failure(ValueError(f"Error filtering entries: {filter_result.failure()}")) # Wrap filtering error in ValueError
        filtered_entries = filter_result.unwrap()
    else:
        filtered_entries = parsed_data.entries

    filtered_journal = replace(parsed_data, entries=filtered_entries)

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
    parse_result = parse_hledger_journal(str(filename.absolute()))
    process_result = parse_filter_strip(parse_result, flat, strip, query)

    if isinstance(process_result, Success):
        # Use pprint.pformat for better control if needed, or just pprint
        pprint.pprint(process_result.unwrap(), indent=2)  # Add indentation for readability
        exit(0)
    else:
        print(f"Error: {process_result.failure()}")
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
    process_result = parse_filter_strip(parse_result, flat, strip, query)

    if isinstance(process_result, Success):
        print(process_result.unwrap().to_journal_string())
        exit(0)
    else:
        print(f"Error: {process_result.failure()}")
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
    parse_result: Result[Journal, Union[ParseError, str]] = parse_hledger_journal(str(filename.absolute()))

    if isinstance(parse_result, Failure):
        # Print the error message from the Failure and exit with a non-zero status code
        print(f"Error parsing journal file: {parse_result.failure()}")
        exit(1)

    # If parsing was successful, unwrap the result and proceed
    parsed_data: Journal = parse_result.unwrap()
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
