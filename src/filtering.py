# This file will contain the filtering logic for transactions.

from typing import List, Optional, Union

from parsita import *
from src.classes import JournalEntry, Transaction, Posting, Amount, AccountName
from datetime import date, datetime
from decimal import Decimal
import re
from dataclasses import dataclass


# Define filter condition classes
@dataclass
class AccountFilter:
    pattern: str


@dataclass
class DateFilter:
    start_date: Optional[date]
    end_date: Optional[date]


@dataclass
class DescriptionFilter:
    text: str


@dataclass
class AmountFilter:
    operator: str
    value: Decimal


@dataclass
class TagFilter:
    name: str
    value: Optional[str]


# Define filter functions for different criteria
def filter_by_account(transaction: Transaction, condition: AccountFilter) -> bool:
    """Checks if any posting in the transaction has an account matching the pattern."""
    for posting in transaction.postings:
        if re.search(condition.pattern, str(posting.account), re.IGNORECASE):
            return True
    return False


def filter_by_date(transaction: Transaction, condition: DateFilter) -> bool:
    """Checks if the transaction date falls within the specified date filter."""
    if condition.start_date and condition.end_date:
        return condition.start_date <= transaction.date <= condition.end_date
    elif condition.start_date:
        return condition.start_date <= transaction.date
    elif condition.end_date:
        return transaction.date <= condition.end_date
    else:
        return False  # Should not happen with proper parsing


def filter_by_description(
    transaction: Transaction, condition: DescriptionFilter
) -> bool:
    """Checks if the transaction payee contains the specified text (case-insensitive)."""
    if isinstance(transaction.payee, str):
        return condition.text.lower() in transaction.payee.lower()
    elif isinstance(transaction.payee, AccountName):
        return condition.text.lower() in str(transaction.payee).lower()
    return False


def filter_by_amount(transaction: Transaction, condition: AmountFilter) -> bool:
    """Checks if any posting amount in the transaction matches the amount filter."""
    for posting in transaction.postings:
        if posting.amount:
            amount_value = posting.amount.quantity
            if condition.operator == ">" and amount_value > condition.value:
                return True
            elif condition.operator == "<" and amount_value < condition.value:
                return True
            elif condition.operator == ">=" and amount_value >= condition.value:
                return True
            elif condition.operator == "<=" and amount_value <= condition.value:
                return True
            elif condition.operator == "==" and amount_value == condition.value:
                return True
            elif condition.operator == "!=" and amount_value != condition.value:
                return True
    return False


def filter_by_tag(transaction: Transaction, condition: TagFilter) -> bool:
    """Checks if any posting in the transaction has a tag matching the tag filter."""
    for posting in transaction.postings:
        for tag in posting.tags:
            if tag.name == condition.name:
                if condition.value is None or tag.value == condition.value:
                    return True
    return False


class FilterQueryParsers(ParserContext, whitespace="\s*"):
    # Basic parsers
    colon = ":"
    dot_dot = ".."
    number = reg(r"-?\d+(\.\d+)?") > (lambda x: Decimal(x))
    date_str = reg(r"\d{4}-\d{2}-\d{2}")

    # Filter value parsers
    account_part = reg(r"[A-Za-z_]+")
    account = repsep(account_part, lit(":"), min=1)
    date_range = (opt(date_str) << dot_dot & opt(date_str)) > (
        lambda parts: (parts[0], parts[1])
    )
    single_date = date_str > (lambda d: (d, d))
    date_value = date_range | single_date
    description_text = reg(r"[^\s]+")
    amount_operator = reg(r"[<>!=]+")
    amount_value_part = amount_operator & number
    tag_name = reg(r"[^\s:]+")
    tag_value = colon & reg(r"[^\s:]+")
    tag_value_part = tag_name & opt(tag_value)

    # Filter parsers
    account_filter = lit("account") >> colon >> account > (
        lambda parts: AccountFilter(pattern=parts[0])
    )
    date_filter = lit("date") >> colon >> date_value > (
        lambda parts: DateFilter(
            start_date=(
                datetime.strptime(parts[1][0], "%Y-%m-%d").date()
                if parts[1][0]
                else None
            ),
            end_date=(
                datetime.strptime(parts[1][1], "%Y-%m-%d").date()
                if parts[1][1]
                else None
            ),
        )
    )
    description_filter = lit("desc") >> colon >> description_text > (
        lambda parts: DescriptionFilter(text=parts[1])
    )
    amount_filter = lit("amount") >> colon >> amount_value_part > (
        lambda parts: AmountFilter(operator=parts[1][0], value=parts[1][1])
    )
    tag_filter = lit("tag") >> colon >> tag_value_part > (
        lambda parts: TagFilter(
            name=parts[1][0], value=parts[1][1][1] if parts[1][1] else None
        )
    )

    # Combined filter parser
    filter_condition = (
        account_filter | date_filter | description_filter | amount_filter | tag_filter
    )

    # Main query parser (list of filter conditions separated by spaces)
    query_parser = rep(filter_condition, min=1)

def parse_query(query: str):
    return FilterQueryParsers.query_parser.parse(query)

def filter_entries(entries: List[JournalEntry], query: str) -> List[JournalEntry]:
    """Filters a list of transactions based on a query string."""
    filtered_transactions = []
    try:
        # Parse the query string
        parsed_conditions = parse_query(query).unwrap()

        # Apply filters with AND logic
        for entry in entries:
            if entry.transaction:
                transaction = entry.transaction
                for condition in parsed_conditions:
                    if isinstance(condition, AccountFilter):
                        if not filter_by_account(transaction, condition):
                            break
                    elif isinstance(condition, DateFilter):
                        if not filter_by_date(transaction, condition):
                            break
                    elif isinstance(condition, DescriptionFilter):
                        if not filter_by_description(transaction, condition):
                            break
                    elif isinstance(condition, AmountFilter):
                        if not filter_by_amount(transaction, condition):
                            break
                    elif isinstance(condition, TagFilter):
                        if not filter_by_tag(transaction, condition):
                            break
                    # Add more filter types here as needed

            filtered_transactions.append(transaction)

    except ParseError as e:
        print(f"Error parsing filter query: {e}")
        # Depending on desired behavior, could return empty list or raise error
        return []

    return filtered_transactions
