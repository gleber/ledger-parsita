from typing import List, Callable, Dict
from decimal import Decimal
import re
import datetime

from src.classes import Transaction, Posting, AccountName, Amount, Commodity, SourceLocation, PositionEffect # Added TransactionPositionEffect
from src.journal import Journal
from src.balance import BalanceSheet, AssetBalance, CashBalance, Lot # Import BalanceSheet, Balance types, and Lot

def find_open_transactions(journal: Journal) -> List[Transaction]:
    """Finds transactions that open positions."""
    open_txns: List[Transaction] = []
    for entry in journal.entries:
        if entry.transaction:
            for posting in entry.transaction.postings:
                if posting.get_effect() == PositionEffect.OPEN_LONG: # Changed to use get_effect
                    open_txns.append(entry.transaction)
                    break # Move to the next transaction once an opening posting is found
    return open_txns

def find_close_transactions(journal: Journal) -> List[Transaction]:
    """Finds transactions that close positions."""
    close_txns: List[Transaction] = []
    for entry in journal.entries:
        if entry.transaction:
            for posting in entry.transaction.postings:
                # For now, find_close_transactions will find sales of long positions.
                # Closing short positions (buy-to-cover) would be TransactionPositionEffect.CLOSE_SHORT
                # or an OPEN_LONG that is identified as closing a short in BalanceSheet.
                if posting.get_effect() == PositionEffect.CLOSE_LONG: # Changed to use get_effect
                    close_txns.append(entry.transaction)
                    break # Move to the next transaction once a closing posting is found
    return close_txns
