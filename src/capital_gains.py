from typing import List, Callable, Dict
from dataclasses import dataclass, field
from decimal import Decimal
import re
import datetime

from src.classes import Journal, Transaction, Posting, AccountName, Amount, Commodity, SourceLocation

dated_account_regex = re.compile(r"^assets:.*:.*:\d{8}$")


@dataclass
class OpenLot:
    """Represents an open position lot."""
    posting: Posting
    remaining_quantity: Decimal
    transaction_date: datetime.date


@dataclass
class MatchResult:
    """Represents a match between a closing posting and an opening lot."""
    closing_posting: Posting
    opening_lot: OpenLot
    matched_quantity: Decimal


def find_transactions_by_posting_criteria(
    journal: Journal, posting_filter: Callable[[Posting], bool]
) -> List[Transaction]:
    """
    Finds transactions containing at least one posting that matches the given criteria.
    Returns a list of unique Transaction objects.
    """
    matching_txns = []
    seen_txns = set()
    for entry in journal.entries:
        if entry.transaction:
            tx = entry.transaction
            tx_key = tx.getKey()
            if tx_key in seen_txns:
                continue  # Skip if transaction has already been processed

            found_matching_posting = False
            for posting in tx.postings:
                if posting_filter(posting):
                    found_matching_posting = True
                    break

            if found_matching_posting:
                matching_txns.append(tx)
                seen_txns.add(tx_key)
    return matching_txns


# Posting filter functions
def is_open_position_posting(posting: Posting) -> bool:
    """Checks if a posting indicates opening a position in an asset account and is not cash."""
    return bool(
        posting.account
        and posting.account.isAsset()
        and posting.amount
        and posting.amount.quantity > 0
        and not posting.amount.commodity.isCash()
    )


def is_close_position_posting(posting: Posting) -> bool:
    """Checks if a posting indicates closing a position in an asset account and is not cash."""
    return bool(
        posting.account
        and posting.account.isAsset()
        and posting.amount
        and posting.amount.quantity < 0
        and not posting.amount.commodity.isCash()
    )


def is_open_position_with_dated_subaccount_posting(posting: Posting) -> bool:
    """Checks if a posting indicates opening a position in a dated asset account and is not cash."""
    return bool(
        posting.account
        and posting.account.isAsset()
        and posting.account.isDatedSubaccount()
        and posting.amount
        and posting.amount.quantity > 0
        and not posting.amount.commodity.isCash()
    )


def is_close_position_without_dated_subaccount_posting(posting: Posting) -> bool:
    """Checks if a posting indicates closing a position in a non-dated asset account and is not cash."""
    return bool(
        posting.account
        and posting.account.isAsset()
        and not posting.account.isDatedSubaccount()
        and posting.amount
        and posting.amount.quantity < 0
        and not posting.amount.commodity.isCash()
    )


# Refactored functions using the higher-order function
def find_open_transactions(journal: Journal) -> List[Transaction]:
    """
    Finds transactions containing postings that increase the quantity
    in an asset account (indicating an opening position), regardless of dated subaccount.
    Returns a list of unique Transaction objects.
    """
    return find_transactions_by_posting_criteria(journal, is_open_position_posting)


def find_close_transactions(journal: Journal) -> List[Transaction]:
    """
    Finds transactions containing postings that decrease the quantity
    in an asset account (indicating a closing position), regardless of dated subaccount.
    Returns a list of unique Transaction objects.
    """
    return find_transactions_by_posting_criteria(journal, is_close_position_posting)


def find_open_transactions_with_dated_subaccounts(
    journal: Journal,
) -> List[Transaction]:
    """
    Finds transactions containing postings that increase the quantity
    in an asset account that uses a dated subaccount.
    Returns a list of unique Transaction objects.
    """
    return find_transactions_by_posting_criteria(
        journal, is_open_position_with_dated_subaccount_posting
    )


def find_close_transactions_without_dated_subaccounts(
    journal: Journal,
) -> List[Transaction]:
    """
    Finds transactions containing postings that decrease the quantity
    in an asset account that does NOT use a dated subaccount.
    Returns a list of unique Transaction objects.
    """
    return find_transactions_by_posting_criteria(
        journal, is_close_position_without_dated_subaccount_posting
    )


def get_base_account_name(account_name: AccountName) -> str:
    """Extracts the base account name from a potentially dated subaccount."""
    if account_name.isDatedSubaccount():
        return ":".join(account_name.parts[:-1])
    return account_name.name


def match_fifo(journal: Journal) -> List[MatchResult]:
    """
    Matches closing postings without dated subaccounts to opening postings with dated subaccounts
    using FIFO logic.
    """
    open_lots: Dict[tuple[str, str], List[OpenLot]] = {}
    match_results: List[MatchResult] = []

    # Sort entries by date to ensure FIFO
    sorted_entries = sorted(journal.entries, key=lambda entry: entry.transaction.date if entry.transaction else datetime.date.min)

    for entry in sorted_entries:
        if entry.transaction:
            tx = entry.transaction
            for posting in tx.postings:
                if is_open_position_with_dated_subaccount_posting(posting) and posting.amount is not None:
                    # Add to open lots
                    base_account = get_base_account_name(posting.account)
                    if posting.amount is not None: # Redundant check for Mypy
                        commodity_name = posting.amount.commodity.name
                        key = (commodity_name, base_account)
                        if key not in open_lots:
                            open_lots[key] = []
                        if posting.amount is not None: # Redundant check for Mypy
                            open_lots[key].append(OpenLot(posting=posting, remaining_quantity=posting.amount.quantity, transaction_date=tx.date))
                            # Ensure lots are sorted by date (should be due to sorted entries, but good practice)
                            open_lots[key].sort(key=lambda lot: lot.transaction_date)

                elif is_close_position_without_dated_subaccount_posting(posting) and posting.amount is not None:
                    # Match with open lots
                    base_account = get_base_account_name(posting.account)
                    if posting.amount is not None: # Redundant check for Mypy
                        commodity_name = posting.amount.commodity.name
                        key = (commodity_name, base_account)
                        closing_quantity = abs(posting.amount.quantity)

                        if key in open_lots:
                            lots_for_commodity = open_lots[key]
                            while closing_quantity > 0 and lots_for_commodity:
                                current_lot = lots_for_commodity[0]
                                match_quantity = min(closing_quantity, current_lot.remaining_quantity)

                                match_results.append(MatchResult(
                                    closing_posting=posting,
                                    opening_lot=current_lot,
                                    matched_quantity=match_quantity
                                ))

                                current_lot.remaining_quantity -= match_quantity
                                closing_quantity -= match_quantity

                                if current_lot.remaining_quantity == 0:
                                    lots_for_commodity.pop(0) # Remove fully consumed lot

                            if closing_quantity > 0 and posting.amount is not None:
                                # Handle case where there are not enough open lots
                                print(f"Warning: Not enough open lots for {commodity_name} in {base_account} to match closing quantity of {abs(posting.amount.quantity)} in transaction {tx.date} {tx.payee}")
                                # Depending on requirements, we might raise an error here instead

    return match_results
