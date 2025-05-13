from dataclasses import replace
from datetime import date
from collections import defaultdict
from typing import Optional, Union, List
import click
import pprint
from pathlib import Path
from src.classes import Journal, JournalEntry, VerificationError # Updated import
import re
from parsita import ParseError
from src.classes import Posting, Transaction, sl, AccountName # Import AccountName
from src.filtering import BaseFilter, parse_query
from returns.result import Result, Success, Failure
from src.capital_gains import find_open_transactions, find_close_transactions
from src.balance import BalanceSheet, Account # Import BalanceSheet and Account
from returns.pipeline import flow, is_successful # Import is_successful
from returns.pointfree import (bind)
from src.filtering import Filters, FILTER_LIST # Import Filters and FILTER_LIST

# Define the main click group
@click.group()
def cli():
    """A command-line tool for parsing hledger journal files."""
    pass

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
    "-q", "--query", type=FILTER_LIST, default=None, help="Filter transactions using a query string."
)
def pprint_cmd(filename: Path, flat: bool, strip: bool, query: Optional[Filters]):
    """Parses the journal file and pretty-prints the result."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=flat, strip=strip, query=query
    )

    if not is_successful(result):
        error_content = result.failure()
        click.echo(f"Error: {error_content}", err=True)
        exit(1)
    
    journal: Journal = result.unwrap()
    pprint.pprint(journal, indent=2)
    exit(0)


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
    "-q", "--query", type=FILTER_LIST, default=None, help="Filter transactions using a query string."
)
def print_cmd(filename: Path, flat: bool, strip: bool, query: Optional[Filters]):
    """Parses the journal file and prints the result using to_journal_string."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=flat, strip=strip, query=query
    )

    if not is_successful(result):
        error_content = result.failure()
        click.echo(f"Error processing journal: {error_content}", err=True)
        exit(1)

    processed_journal: Journal = result.unwrap()
    click.echo(processed_journal.to_journal_string())
    exit(0)


def is_opening_position(posting: Posting) -> bool:
    """Checks if a posting represents an opening position (assets account with positive quantity), excluding assets:cash."""
    return (
        posting.account.name.startswith("assets:")
        and posting.account.name != "assets:cash" # Exclude assets:cash
        and posting.amount is not None
        and posting.amount.quantity > 0
    )

def find_non_dated_stock_txs(journal: Journal) -> list[Transaction]:
    """Finds transactions with non-dated opening positions."""
    non_dated_opens: list[Transaction] = []
    unique_commodity = {}
    for entry in journal.entries:
        if entry.transaction: # Check if the entry is a transaction
            for posting in entry.transaction.postings:
                if posting.amount and posting.amount.commodity:
                    unique_commodity[posting.amount.commodity.name] = posting.amount.commodity
                if posting.isClosing() and not posting.account.isDatedSubaccount() and posting.account.isAsset() and posting.amount and posting.amount.commodity and (posting.amount.commodity.isStock()): # or posting.amount.commodity.isOption()):
                    non_dated_opens.append(entry.transaction)
                    break
    # kinds = defaultdict(list)
    # for v in unique_commodity.values():
    #     kinds[v.kind].append(v.name)
    # pprint.pprint(dict(kinds))
    return non_dated_opens

def find_capgain_non_crypto_txs(journal: Journal) -> list[Transaction]:
    """Finds transactions which produce cap gains for non-crypto."""
    restxs: list[Transaction] = []
    for entry in journal.entries:
        if entry.transaction: # Check if the entry is a transaction
            if not (date(2024, 1, 1) <= entry.transaction.date < date(2025,1,1)):
                continue
            unique_commodity = {}
            for posting in entry.transaction.postings:
                if posting.amount and posting.amount.commodity:
                    unique_commodity[posting.amount.commodity.name] = posting.amount.commodity
            if len(unique_commodity) < 2:
                continue
            if not [ u for u in unique_commodity.values() if (u.isStock() or u.isOption()) ]:
                continue

            restxs.append(entry.transaction)
            continue
            for posting in entry.transaction.postings:
                if posting.isClosing() and not posting.account.isDatedSubaccount() and posting.account.isAsset() and posting.amount and posting.amount.commodity and (posting.amount.commodity.isStock()): # or posting.amount.commodity.isOption()):
                    restxs.append(entry.transaction)
                    break
    # kinds = defaultdict(list)
    # for v in unique_commodity.values():
    #     kinds[v.kind].append(v.name)
    # pprint.pprint(dict(kinds))
    return restxs


# Define the find-positions command
@cli.command("find-positions")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def find_positions_cmd(filename: Path):
    """Finds transactions that open or close positions."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=True, strip=False, query=None
    )

    if not is_successful(result):
        error_content = result.failure()
        click.echo(f"Error parsing journal file: {error_content}", err=True)
        exit(1)
    
    parsed_data: Journal = result.unwrap()
    click.echo(f"Successfully parsed hledger journal: {filename}", err=True)

    open_txns = find_open_transactions(parsed_data)
    close_txns = find_close_transactions(parsed_data)

    if open_txns:
        click.echo("\nOpening Transactions:")
        for transaction in open_txns:
            source_loc = transaction.source_location
            line_info = f"(Line {source_loc.offset})" if source_loc else "(Line N/A)"
            click.echo(f"- {transaction.date} {transaction.payee} {line_info}")
    else:
        click.echo("\nNo opening transactions found.")

    if close_txns:
        click.echo("\nClosing Transactions:")
        for transaction in close_txns:
            source_loc = transaction.source_location
            line_info = f"(Line {source_loc.offset})" if source_loc else "(Line N/A)"
            click.echo(f"- {transaction.date} {transaction.payee} {line_info}")
    else:
        click.echo("\nNo closing transactions found.")

    exit(0)


# Define the balance command
@cli.command("balance")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "-q", "--query", type=FILTER_LIST, default=None, help="Filter transactions using a query string."
)
@click.option(
    "-F", "--flat", is_flag=True, help="Print accounts as a flat list instead of a tree."
)
@click.option(
    "-D", "--display", type=click.Choice(['own', 'total', 'both'], case_sensitive=False),
    default='total', help="Specify which balances to display: 'own', 'total', or 'both'."
)
def balance_cmd(filename: Path, query: Optional[Filters], flat: bool, display: str):
    """Calculates and prints the current balance of all accounts."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=True, strip=False, query=query
    )

    if not is_successful(result):
        error_content = result.failure()
        click.echo(f"Error parsing journal file: {error_content}", err=True)
        exit(1)

    journal: Journal = result.unwrap()
    
    balance_sheet_result = BalanceSheet.from_journal(journal) # Use new method
    if not is_successful(balance_sheet_result):
        errors = balance_sheet_result.failure()
        click.echo("Error calculating balance sheet:", err=True)
        for error in errors: # errors is List[BalanceSheetCalculationError]
            click.echo(f"  - {error}", err=True) # BalanceSheetCalculationError has __str__
        exit(1)
    
    balance_sheet: BalanceSheet = balance_sheet_result.unwrap()

    click.echo("Current Balances:")
    if flat:
        for line in balance_sheet.format_account_flat(display=display): # Use BalanceSheet method
            click.echo(line)
    else:
        # The BalanceSheet.format_account_hierarchy method now handles iterating through its root accounts.
        for line in balance_sheet.format_account_hierarchy(display=display): 
            click.echo(line)

    exit(0)

# Define the gains command
@cli.command("gains")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "-q", "--query", type=FILTER_LIST, default=None, help="Filter transactions using a query string."
)
def gains_cmd(filename: Path, query: Optional[Filters]):
    """Calculates and prints only the capital gains results."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=True, strip=False, query=query
    )

    if not is_successful(result):
        error_content = result.failure()
        click.echo(f"Error parsing journal file: {error_content}", err=True)
        exit(1)

    journal: Journal = result.unwrap()
    
    balance_sheet_result = BalanceSheet.from_journal(journal) # Use new method
    if not is_successful(balance_sheet_result):
        errors = balance_sheet_result.failure()
        click.echo("Error calculating capital gains:", err=True)
        for error in errors: # errors is List[BalanceSheetCalculationError]
            click.echo(f"  - {error}", err=True)
        exit(1)
        
    balance_sheet: BalanceSheet = balance_sheet_result.unwrap()

    click.echo("Capital Gains Results:")
    if balance_sheet.capital_gains_realized: # Accessing attribute on unwrapped BalanceSheet
        for gain_result in balance_sheet.capital_gains_realized: # Accessing attribute on unwrapped BalanceSheet
            closing_date_str = gain_result.closing_date.strftime('%Y-%m-%d') if gain_result.closing_date else 'N/A'
            acquisition_date_str = gain_result.acquisition_date.strftime('%Y-%m-%d') if gain_result.acquisition_date else 'N/A'

            closing_account = gain_result.closing_posting.account.name if gain_result.closing_posting.account else 'N/A'
            closing_commodity = gain_result.matched_quantity.commodity.name if gain_result.matched_quantity.commodity else 'N/A'
            matched_quantity = gain_result.matched_quantity.quantity
            cost_basis = gain_result.cost_basis.quantity
            proceeds = gain_result.proceeds.quantity
            gain_loss = gain_result.gain_loss.quantity
            gain_loss_commodity = gain_result.gain_loss.commodity.name if gain_result.gain_loss.commodity else 'N/A'

            click.echo(f"  Sale Date: {closing_date_str}, Account: {closing_account}, Commodity: {closing_commodity}, Quantity: {matched_quantity}")
            click.echo(f"    Acquisition Date: {acquisition_date_str}, Cost Basis: {cost_basis}, Proceeds: {proceeds}, Gain/Loss: {gain_loss} {gain_loss_commodity}")
    else:
        click.echo("  No capital gains or losses calculated.")

    exit(0)


# Define the verify command
@cli.command("verify")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def verify_cmd(filename: Path):
    """Verifies the integrity and consistency of the journal file."""
    parse_result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=True, strip=False, query=None # flat=True to resolve includes for full verification
    )

    if not is_successful(parse_result):
        error_content = parse_result.failure()
        click.echo(f"Error parsing journal file: {error_content}", err=True)
        exit(1)

    journal: Journal = parse_result.unwrap()
    
    verification_result = journal.verify() # This returns Result[None, List[VerificationError]]

    if is_successful(verification_result):
        click.echo(f"Journal '{filename}' verified successfully.")
        exit(0)
    else:
        errors: List[VerificationError] = verification_result.failure()
        click.echo(f"Journal verification failed with {len(errors)} error(s):", err=True)
        for i, error in enumerate(errors):
            # VerificationError has a custom __str__ that includes source location
            click.echo(f"  {i+1}. {error}", err=True) 
        exit(1)

if __name__ == "__main__":
    cli()
