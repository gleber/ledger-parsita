from typing import List, Callable, Dict
from decimal import Decimal
import re
import datetime

from src.classes import Journal, Transaction, Posting, AccountName, Amount, Commodity, SourceLocation
from src.balance import BalanceSheet, AssetBalance, CashBalance, Lot # Import BalanceSheet, Balance types, and Lot

def find_open_transactions(journal: Journal) -> List[Transaction]:
    """Finds transactions that open positions."""
    open_txns: List[Transaction] = []
    for entry in journal.entries:
        if entry.transaction:
            for posting in entry.transaction.postings:
                if posting.isOpening():
                    open_txns.append(entry.transaction)
                    break # Move to the next transaction once an opening posting is found
    return open_txns

def find_close_transactions(journal: Journal) -> List[Transaction]:
    """Finds transactions that close positions."""
    close_txns: List[Transaction] = []
    for entry in journal.entries:
        if entry.transaction:
            for posting in entry.transaction.postings:
                if posting.isClosing():
                    close_txns.append(entry.transaction)
                    break # Move to the next transaction once a closing posting is found
    return close_txns
