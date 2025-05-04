from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Union

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
    """Base class for account balances."""
    commodity: Commodity
    total_amount: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity(""))) # Initialize with zero amount

@dataclass
class CashBalance(Balance):
    """Represents the balance of a cash or cryptocurrency commodity within an account."""
    # Inherits commodity and total_amount from Balance
    pass

@dataclass
class AssetBalance(Balance):
    """Represents the balance of a stock or option commodity within an account, including lots."""
    # Inherits commodity and total_amount from Balance
    cost_basis_per_unit: Amount = field(default_factory=lambda: Amount(Decimal(0), Commodity(""))) # Initialize with zero amount
    lots: List[Lot] = field(default_factory=list)

    def add_lot(self, lot: Lot):
        """Adds a lot to this AssetBalance and incrementally recalculates total_amount and cost_basis_per_unit."""
        if lot.quantity.commodity != self.commodity:
            raise ValueError("Lot commodity must match Balance commodity")

        # Calculate the new total quantity and total cost
        current_total_quantity = self.total_amount.quantity if self.total_amount.commodity == self.commodity else Decimal(0)
        current_total_cost = current_total_quantity * self.cost_basis_per_unit.quantity if self.cost_basis_per_unit and self.cost_basis_per_unit.commodity.name != "" else Decimal(0)

        new_total_quantity = current_total_quantity + lot.quantity.quantity
        new_total_cost = current_total_cost + (lot.quantity.quantity * lot.cost_basis_per_unit.quantity if lot.cost_basis_per_unit else Decimal(0))

        # Update total_amount
        self.total_amount = Amount(new_total_quantity, self.commodity)

        # Update cost_basis_per_unit (weighted average)
        if new_total_quantity != 0:
            cost_commodity = lot.cost_basis_per_unit.commodity if lot.cost_basis_per_unit else (self.cost_basis_per_unit.commodity if self.cost_basis_per_unit.commodity.name != "" else Commodity(""))
            self.cost_basis_per_unit = Amount(new_total_cost / new_total_quantity, cost_commodity)
        else:
            self.cost_basis_per_unit = Amount(Decimal(0), self.cost_basis_per_unit.commodity if self.cost_basis_per_unit.commodity.name != "" else Commodity("")) # Handle zero quantity

        self.lots.append(lot)


@dataclass
class Account:
    """Represents an account with balances for different commodities."""
    name: AccountName
    balances: Dict[Commodity, Union[CashBalance, AssetBalance]] = field(default_factory=dict)

    def get_balance(self, commodity: Commodity) -> Union[CashBalance, AssetBalance]:
        """Gets or creates a Balance subclass object for a given commodity based on its type."""
        if commodity not in self.balances:
            # Determine the type of Balance to create based on commodity type
            if commodity.isCash() or commodity.isCrypto(): # Assuming isCrypto() method exists or similar logic
                self.balances[commodity] = CashBalance(commodity=commodity)
            elif commodity.isStock() or commodity.isOption(): # Assuming isStock() and isOption() methods exist or similar logic
                 # Initialize AssetBalance with zero total_amount and cost_basis_per_unit
                self.balances[commodity] = AssetBalance(commodity=commodity, total_amount=Amount(Decimal(0), commodity), cost_basis_per_unit=Amount(Decimal(0), Commodity("")))
            else:
                # Default to CashBalance for unknown types or raise an error
                self.balances[commodity] = CashBalance(commodity=commodity) # Or raise ValueError(f"Unsupported commodity type: {commodity.name}")

        return self.balances[commodity]

    def add_lot(self, commodity: Commodity, lot: Lot):
        """Adds a lot to the balance of a specific commodity (must be an AssetBalance)."""
        balance = self.get_balance(commodity)
        if isinstance(balance, AssetBalance):
            balance.add_lot(lot)
        else:
            raise TypeError(f"Cannot add lot to non-asset balance for commodity: {commodity.name}")


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
        """Updates the balance of a specific commodity in an account (only for CashBalance)."""
        account = self.get_account(account_name)
        balance = account.get_balance(amount.commodity)
        if isinstance(balance, CashBalance):
             # Explicitly add amount quantity to total_amount quantity for CashBalance
            if balance.total_amount.commodity.name == "": # Handle initial zero amount
                 balance.total_amount = Amount(balance.total_amount.quantity + amount.quantity, amount.commodity)
            elif balance.total_amount.commodity != amount.commodity:
                raise ValueError("Cannot add amounts of different commodities")
            else:
                balance.total_amount.quantity += amount.quantity
        # For AssetBalance, total_amount is updated when lots are added, not by postings here


    def add_lot_to_account(self, account_name: AccountName, commodity: Commodity, lot: Lot):
        """Adds a lot to a specific commodity balance within an account (must be an AssetBalance)."""
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

            # Ensure the account exists in the balance sheet
            account = balance_sheet.get_account(account_name)

            if amount is not None:
                # Ensure the balance for the commodity exists and update if it's a CashBalance
                balance = account.get_balance(amount.commodity)
                if isinstance(balance, CashBalance):
                    # Explicitly add amount to total_amount for CashBalance
                    if balance.total_amount.commodity.name == "": # Handle initial zero amount
                         balance.total_amount = Amount(balance.total_amount.quantity + amount.quantity, amount.commodity)
                    elif balance.total_amount.commodity != amount.commodity:
                        raise ValueError("Cannot add amounts of different commodities")
                    else:
                        balance.total_amount.quantity += amount.quantity
                # For AssetBalance, total_amount is updated when lots are added, not by postings here


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
