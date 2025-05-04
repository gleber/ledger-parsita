from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List

from src.classes import AccountName, Amount, Commodity, Posting, Transaction, CostKind

@dataclass
class Lot:
    """Represents a specific acquisition lot of an asset."""
    acquisition_date: str  # Using string for now, could be date object later
    quantity: Amount
    cost_basis_per_unit: Amount # Cost per unit in the transaction currency
    original_posting: Posting # Reference to the posting that created this lot

@dataclass
class Balance:
    """Represents the balance of a single commodity within an account, including lots."""
    commodity: Commodity
    total_amount: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity(""))) # Initialize with zero amount
    lots: List[Lot] = field(default_factory=list)

    def __iadd__(self, other: Amount) -> 'Balance':
        """In-place addition for updating total_amount."""
        if self.total_amount.commodity.name == "": # Handle initial zero amount
             self.total_amount = Amount(self.total_amount.quantity + other.quantity, other.commodity)
        elif self.total_amount.commodity != other.commodity:
            raise ValueError("Cannot add amounts of different commodities")
        else:
            self.total_amount += other
        return self

@dataclass
class Account:
    """Represents an account with balances for different commodities."""
    name: AccountName
    balances: Dict[Commodity, Balance] = field(default_factory=dict)

    def get_balance(self, commodity: Commodity) -> Balance:
        """Gets or creates a Balance object for a given commodity."""
        if commodity not in self.balances:
            self.balances[commodity] = Balance(commodity=commodity)
        return self.balances[commodity]

    def add_lot(self, commodity: Commodity, lot: Lot):
        """Adds a lot to the balance of a specific commodity."""
        balance = self.get_balance(commodity)
        balance.lots.append(lot)

@dataclass
class BalanceSheet:
    """Represents the balance sheet with accounts and their balances."""
    accounts: Dict[AccountName, Account] = field(default_factory=dict)

    def get_account(self, account_name: AccountName) -> Account:
        """Gets or creates an Account object for a given account name."""
        if account_name not in self.accounts:
            self.accounts[account_name] = Account(name=account_name)
        return self.accounts[account_name]

    def update_balance(self, account_name: AccountName, amount: Amount):
        """Updates the balance of a specific commodity in an account."""
        account = self.get_account(account_name)
        balance = account.get_balance(amount.commodity)
        balance += amount

    def add_lot_to_account(self, account_name: AccountName, commodity: Commodity, lot: Lot):
        """Adds a lot to a specific commodity balance within an account."""
        account = self.get_account(account_name)
        account.add_lot(commodity, lot)


def calculate_balances_and_lots(transactions: List[Transaction]) -> BalanceSheet:
    """
    Calculates the balance of each account and tracks asset lots, returning a BalanceSheet.

    Args:
        transactions: A list of Transaction objects.

    Returns:
        A BalanceSheet containing accounts, their balances, and associated lots.
    """
    balance_sheet = BalanceSheet()

    for transaction in transactions:
        for posting in transaction.postings:
            account_name = posting.account
            amount = posting.amount

            if amount is not None:
                balance_sheet.update_balance(account_name, amount)

        # After processing all postings in a transaction, check for asset acquisitions and track lots
        acquisition_posting = transaction.get_asset_acquisition_posting()
        if acquisition_posting:
            # Get the cost for this posting (explicit or inferred)
            cost = transaction.get_posting_cost(acquisition_posting)

            if cost and acquisition_posting.amount is not None:
                cost_basis_per_unit = None
                if cost.kind == CostKind.TotalCost:
                    # Calculate per-unit cost from total cost
                    if acquisition_posting.amount.quantity != 0:
                        cost_basis_per_unit_value = abs(cost.amount.quantity / acquisition_posting.amount.quantity)
                        cost_basis_per_unit = Amount(cost_basis_per_unit_value, cost.amount.commodity)
                elif cost.kind == CostKind.UnitCost:
                    # Unit cost is provided directly
                    cost_basis_per_unit = cost.amount

                if cost_basis_per_unit:
                    lot = Lot(
                        acquisition_date=str(transaction.date), # Use transaction date as acquisition date
                        quantity=acquisition_posting.amount, # Use quantity from the acquisition posting
                        cost_basis_per_unit=cost_basis_per_unit,
                        original_posting=acquisition_posting
                    )

                    account_name = acquisition_posting.account # Get account name from acquisition posting
                    balance_sheet.add_lot_to_account(account_name, acquisition_posting.amount.commodity, lot)


    return balance_sheet
