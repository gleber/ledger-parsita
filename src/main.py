from dataclasses import replace
from datetime import date
from collections import defaultdict
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
from returns.result import Result, Success, Failure
from src.capital_gains import find_open_transactions, find_close_transactions, calculate_capital_gains # Import calculate_capital_gains
from src.balance import calculate_balances_and_lots # Import calculate_balances_and_lots
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



# Define the capgains command
@cli.command("capgains")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def capgains_cmd(filename: Path):
    """Finds transactions opening positions using non-dated subaccounts."""
    result: Result[Journal, ValueError] = flow(
        str(filename.absolute()),
        parse_hledger_journal,
        bind(lambda journal: parse_filter_strip(journal, True, False, None))
    )
    journal = result.unwrap()
    capgains_tx = find_capgain_non_crypto_txs(journal)

    click.echo("\nTransactions with capgains:", err=True)
    for transaction in capgains_tx:
        # Access attributes directly from the Transaction object
        sl = transaction.source_location
        #line_info = f"(at {sl.filename}:{sl.line}:{sl.column})" if sl else "(Line N/A)"
        line_info = f"{sl.filename}:{sl.line}:{sl.column}" if sl else "(Line N/A)"
        side = transaction.side()
        # click.echo(f"- {transaction.date} {side} {transaction.payee} {line_info}")
        click.echo(f"; {line_info}")
        click.echo(transaction.to_journal_string())
        click.echo(f"")

    # Exit with a zero status code on success
    exit(0)


# Define the find-non-dated-opens command
@cli.command("find-non-dated-opens")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def find_non_dated_opens_cmd(filename: Path):
    """Finds transactions opening positions using non-dated subaccounts."""
    result: Result[Journal, ValueError] = flow(
        str(filename.absolute()),
        parse_hledger_journal,
        bind(lambda journal: parse_filter_strip(journal, True, False, None))
    )
    match result:
        case Failure(error):
            # Print the error message from the Failure and exit with a non-zero status code
            print(f"Error parsing journal file: {error}")
            exit(1)
        case Success(journal):
            # If parsing was successful, unwrap the result and proceed
            parsed_data: Journal = journal
            click.echo(f"Successfully parsed hledger journal: {filename}", err=True)

    non_dated_opens = find_non_dated_stock_txs(parsed_data)

    if non_dated_opens:
        click.echo("\nTransactions positions with non-dated subaccounts:", err=True)
        for transaction in non_dated_opens:
            # Access attributes directly from the Transaction object
            sl = transaction.source_location
            #line_info = f"(at {sl.filename}:{sl.line}:{sl.column})" if sl else "(Line N/A)"
            line_info = f"{sl.filename}:{sl.line}:{sl.column}" if sl else "(Line N/A)"
            side = transaction.side()
            # click.echo(f"- {transaction.date} {side} {transaction.payee} {line_info}")
            click.echo(f"; {line_info}")
            click.echo(transaction.to_journal_string())
            click.echo(f"")
    else:
        click.echo("\nNo transactions found positions with non-dated subaccounts.")

    # Exit with a zero status code on success
    exit(0)


# Define the find-positions command
@cli.command("find-positions")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def find_positions_cmd(filename: Path):
    """Finds transactions that open or close positions."""
    result: Result[Journal, ValueError] = flow(
        str(filename.absolute()),
        parse_hledger_journal,
        bind(lambda journal: parse_filter_strip(journal, True, False, None))
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
def balance_cmd(filename: Path):
    """Calculates and prints the current balance of all accounts."""
    result: Result[Journal, ValueError] = flow(
        str(filename.absolute()),
        parse_hledger_journal,
        bind(lambda journal: parse_filter_strip(journal, True, False, None))
    )

    match result:
        case Failure(error):
            print(f"Error parsing journal file: {error}")
            exit(1)
        case Success(journal):
            # Flatten the journal to ensure all transactions are processed for balance
            flattened_journal = journal.flatten()
            # Extract only Transaction objects from the flattened entries
            transactions_only = [entry.transaction for entry in flattened_journal.entries if entry.transaction is not None]
            balance_sheet = calculate_balances_and_lots(transactions_only)

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

    exit(0)


# Define the calculate-capgains command
@cli.command("calculate-capgains")
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def calculate_capgains_cmd(filename: Path):
    """Calculates and reports capital gains and losses."""
    result: Result[Journal, ValueError] = flow(
        str(filename.absolute()),
        parse_hledger_journal,
        bind(lambda journal: parse_filter_strip(journal, True, False, None)) # Flatten and process journal
    )

    match result:
        case Failure(error):
            print(f"Error parsing journal file: {error}")
            exit(1)
        case Success(journal):
            # Extract only Transaction objects from the flattened entries
            transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
            
            # Calculate balances and lots
            balance_sheet = calculate_balances_and_lots(transactions_only)

            # Calculate capital gains
            capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

            # Print the results
            click.echo("\nCapital Gains Results:")
            if capital_gain_results:
                for result in capital_gain_results:
                    closing_date = result.closing_posting.transaction.date.strftime('%Y-%m-%d') if result.closing_posting.transaction else 'N/A'
                    closing_account = result.closing_posting.account.name if result.closing_posting.account else 'N/A'
                    closing_commodity = result.matched_quantity.commodity.name if result.matched_quantity.commodity else 'N/A'
                    matched_quantity = result.matched_quantity.quantity
                    acquisition_date = result.opening_lot_original_posting.transaction.date.strftime('%Y-%m-%d') if result.opening_lot_original_posting.transaction else 'N/A'
                    cost_basis = result.cost_basis.quantity
                    proceeds = result.proceeds.quantity
                    gain_loss = result.gain_loss.quantity
                    gain_loss_commodity = result.gain_loss.commodity.name if result.gain_loss.commodity else 'N/A'


                    click.echo(f"  Sale Date: {closing_date}, Account: {closing_account}, Commodity: {closing_commodity}, Quantity: {matched_quantity}")
                    click.echo(f"    Acquisition Date: {acquisition_date}, Cost Basis: {cost_basis}, Proceeds: {proceeds}, Gain/Loss: {gain_loss} {gain_loss_commodity}")
            else:
                click.echo("  No capital gains or losses calculated.")

    exit(0)


if __name__ == "__main__":
    cli()
