from typing import List, Callable, Dict
from dataclasses import dataclass, field
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

@dataclass
class CapitalGainResult:
    """Represents the result of a capital gain/loss calculation for a matched sale portion."""
    closing_posting: Posting
    opening_lot_original_posting: Posting # Reference to the original posting of the matched lot
    matched_quantity: Amount
    cost_basis: Amount # Total cost basis for the matched quantity
    proceeds: Amount # Total proceeds for the matched quantity
    gain_loss: Amount # Calculated gain or loss

def calculate_capital_gains(transactions: List[Transaction], balance_sheet: BalanceSheet) -> List[CapitalGainResult]:
    """
    Calculates capital gains and losses by matching closing postings to opening lots using FIFO logic.
    """
    capital_gain_results: List[CapitalGainResult] = []

    # Iterate through transactions to find closing postings (sales)
    for transaction in transactions:
        for posting in transaction.postings:
            if posting.isClosing():
                closing_account = posting.account
                closing_commodity = posting.amount.commodity if posting.amount else None
                closing_quantity = abs(posting.amount.quantity) if posting.amount else Decimal(0)

                if closing_commodity and closing_quantity > 0:
                    # Find proceeds for this closing posting within the same transaction
                    total_proceeds = Amount(Decimal(0), Commodity("")) # Initialize with zero amount and empty commodity
                    proceeds_found = False
                    for other_posting in transaction.postings:
                        if other_posting != posting and other_posting.amount and other_posting.amount.quantity > 0 and other_posting.amount.commodity.isCash():
                             if total_proceeds.commodity.name == "": # Set commodity on first cash posting
                                total_proceeds = Amount(total_proceeds.quantity + other_posting.amount.quantity, other_posting.amount.commodity)
                             elif total_proceeds.commodity == other_posting.amount.commodity:
                                total_proceeds.quantity += other_posting.amount.quantity
                             else:
                                 # Handle multiple cash commodities in one transaction if necessary, or raise error
                                 print(f"Warning: Multiple cash commodities in transaction {transaction.date} - {transaction.payee}. Only summing {total_proceeds.commodity.name}.")
                                 total_proceeds.quantity += other_posting.amount.quantity # Still sum, but warn
                             proceeds_found = True

                    if not proceeds_found:
                         print(f"Warning: No cash proceeds found for closing posting in transaction {transaction.date} - {transaction.payee} for {closing_quantity} {closing_commodity.name} from {closing_account.name}.")
                         # Depending on requirements, might skip this posting or handle differently

                    quantity_to_match = closing_quantity

                    # Collect all relevant AssetBalance objects for the closing commodity under the closing account and its children
                    relevant_asset_balances: List[AssetBalance] = []
                    for account_name, account_data in balance_sheet.accounts.items():
                        if account_name.name.startswith(closing_account.name):
                            for commodity_name, balance in account_data.balances.items():
                                if isinstance(balance, AssetBalance) and balance.commodity == closing_commodity:
                                     relevant_asset_balances.append(balance)

                    if relevant_asset_balances:
                        # Combine lots from all relevant balances and sort by acquisition date
                        all_relevant_lots: List[Lot] = []
                        for balance in relevant_asset_balances:
                            all_relevant_lots.extend(balance.lots)

                        sorted_lots = sorted(all_relevant_lots, key=lambda lot: datetime.datetime.strptime(lot.acquisition_date, '%Y-%m-%d').date())

                        # Perform FIFO matching
                        for current_lot in sorted_lots:
                            if quantity_to_match <= 0:
                                break # Stop if the closing quantity is fully matched

                            if current_lot.remaining_quantity > 0:
                                match_quantity_decimal = min(quantity_to_match, current_lot.remaining_quantity)
                                match_quantity_amount = Amount(match_quantity_decimal, closing_commodity)

                                # Calculate cost basis for the matched quantity
                                cost_basis_decimal = match_quantity_decimal * current_lot.cost_basis_per_unit.quantity
                                cost_basis_amount = Amount(cost_basis_decimal, current_lot.cost_basis_per_unit.commodity)

                                # Calculate proceeds for the matched quantity (pro-rata)
                                proceeds_decimal = (match_quantity_decimal / closing_quantity) * total_proceeds.quantity if closing_quantity != 0 else Decimal(0)
                                proceeds_amount = Amount(proceeds_decimal, total_proceeds.commodity)

                                # Calculate gain/loss
                                # Ensure both amounts are in the same currency for calculation
                                if cost_basis_amount.commodity != proceeds_amount.commodity:
                                     print(f"Warning: Cost basis commodity ({cost_basis_amount.commodity.name}) and proceeds commodity ({proceeds_amount.commodity.name}) differ for match in transaction {transaction.date} - {transaction.payee}. Cannot calculate gain/loss directly.")
                                     gain_loss_amount = Amount(Decimal(0), Commodity("")) # Cannot calculate if currencies differ
                                else:
                                    gain_loss_decimal = proceeds_decimal - cost_basis_decimal
                                    gain_loss_amount = Amount(gain_loss_decimal, proceeds_amount.commodity)


                                # Create and append CapitalGainResult
                                capital_gain_results.append(CapitalGainResult(
                                    closing_posting=posting,
                                    opening_lot_original_posting=current_lot.original_posting,
                                    matched_quantity=match_quantity_amount,
                                    cost_basis=cost_basis_amount,
                                    proceeds=proceeds_amount,
                                    gain_loss=gain_loss_amount
                                ))

                                # Update remaining quantity in the lot
                                current_lot.remaining_quantity -= match_quantity_decimal
                                quantity_to_match -= match_quantity_decimal

                        if quantity_to_match > 0:
                            print(f"Warning: Not enough open lots found for {closing_quantity} {closing_commodity.name} in {closing_account.name} to match closing posting in transaction {transaction.date} - {transaction.payee}. Remaining quantity to match: {quantity_to_match}")

                    else:
                        print(f"Warning: Could not find any relevant AssetBalance for {closing_account.name}:{closing_commodity.name} to perform FIFO matching.")


    return capital_gain_results
