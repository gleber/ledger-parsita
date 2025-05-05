from dataclasses import replace
from datetime import date
from collections import defaultdict
from typing import Optional, Union, List
import click
import pprint
from pathlib import Path
from src.classes import Journal, JournalEntry # Updated import
import re
from parsita import ParseError
from src.classes import Posting, Transaction, sl
from src.filtering import BaseFilter, parse_query
from returns.result import Result, Success, Failure
from src.capital_gains import find_open_transactions, find_close_transactions
from src.balance import BalanceSheet # Updated import
from returns.pipeline import (flow)
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
    "-q", "--query", type=FILTER_LIST, default=None, help="Filter transactions using a query string."
)
def print_cmd(filename: Path, flat: bool, strip: bool, query: Optional[Filters]):
    """Parses the journal file and prints the result using to_journal_string."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=flat, strip=strip, query=query
    )

    match result:
        case Success(processed_journal):
            print(processed_journal.to_journal_string())
            exit(0)
        case Failure(error):
            print(f"Error processing journal: {error}")
            exit(1)


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

    match result:
        case Failure(error):
            print(f"Error parsing journal file: {error}")
            exit(1)
        case Success(journal):
            parsed_data: Journal = journal
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
def balance_cmd(filename: Path, query: Optional[Filters]):
    """Calculates and prints the current balance of all accounts."""
    result: Result[Journal, Union[ParseError, str, ValueError]] = Journal.parse_from_file(
        str(filename.absolute()), flat=True, strip=False, query=query
    )

    match result:
        case Failure(error):
            print(f"Error parsing journal file: {error}")
            exit(1)
        case Success(journal):
            # Extract only Transaction objects from the flattened entries (already flattened by parse_from_file)
            transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
            balance_sheet = BalanceSheet.from_transactions(transactions_only) # Updated function call

            # Format and print the balance sheet
            click.echo("Current Balances:")
            # Sort accounts alphabetically
            for account_name in sorted(balance_sheet.accounts.keys(), key=lambda x: str(x)):
                account = balance_sheet.get_account(account_name)
                if not account.name.isAsset():
                    continue
                click.echo(f"{account.name}")
                # Sort commodities alphabetically within each account
                for commodity, balance in sorted(account.balances.items(), key=lambda x: str(x[0])):
                    click.echo(f"  {balance.total_amount}")

            # Print Capital Gains Results from the BalanceSheet object
            click.echo("\nCapital Gains Results:")
            if balance_sheet.capital_gains_realized:
                for gain_result in balance_sheet.capital_gains_realized: # Rename loop variable to avoid shadowing
                    # Use the date fields directly from CapitalGainResult
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


if __name__ == "__main__":
    cli()
