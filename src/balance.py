from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List

from src.classes import AccountName, Amount, Commodity, Posting, Transaction

@dataclass
class Lot:
    """Represents a specific acquisition lot of an asset."""
    acquisition_date: str  # Using string for now, could be date object later
    quantity: Amount
    cost_basis_per_unit: Amount # Cost per unit in the transaction currency
    original_posting: Posting # Reference to the posting that created this lot

# Type aliases for clarity
Balance = Dict[Commodity, Amount]
BalanceSheet = Dict[AccountName, Balance]
AssetLots = Dict[AccountName, List[Lot]]

def calculate_balances_and_lots(transactions: List[Transaction]) -> tuple[BalanceSheet, AssetLots]:
    """
    Calculates the balance of each account and tracks asset lots.

    Args:
        transactions: A list of Transaction objects.

    Returns:
        A tuple containing the BalanceSheet and AssetLots.
    """
    balance_sheet: BalanceSheet = {}
    asset_lots: AssetLots = {}

    for transaction in transactions:
        for posting in transaction.postings:
            account_name = posting.account
            amount = posting.amount

            # Update BalanceSheet
            if account_name not in balance_sheet:
                balance_sheet[account_name] = {}

            if amount is not None: # Check for None
                if amount.commodity not in balance_sheet[account_name]:
                    balance_sheet[account_name][amount.commodity] = Amount(Decimal(0), amount.commodity)

                balance_sheet[account_name][amount.commodity] += amount

        # After processing all postings in a transaction, check for asset acquisitions and track lots
        acquisition_posting = transaction.get_asset_acquisition_posting()
        if acquisition_posting:
            cost_basis_posting = transaction.get_cost_basis_posting(acquisition_posting)
            if cost_basis_posting:
                cost_basis_per_unit = transaction.calculate_cost_basis_per_unit(acquisition_posting, cost_basis_posting)
                if cost_basis_per_unit and acquisition_posting.amount is not None: # Add None check
                    lot = Lot(
                        acquisition_date=str(transaction.date), # Use transaction date as acquisition date
                        quantity=acquisition_posting.amount, # Use quantity from the acquisition posting
                        cost_basis_per_unit=cost_basis_per_unit,
                        original_posting=acquisition_posting
                    )

                    account_name = acquisition_posting.account # Get account name from acquisition posting
                    if account_name not in asset_lots:
                        asset_lots[account_name] = []
                    asset_lots[account_name].append(lot)


    return balance_sheet, asset_lots
