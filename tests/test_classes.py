import unittest
from src.classes import AccountName

class TestAccountName(unittest.TestCase):
    def test_account_name_creation(self):
        account = AccountName(parts=["assets", "stocks", "AAPL"])
        self.assertEqual(str(account), "assets:stocks:AAPL")
        self.assertEqual(account.name, "assets:stocks:AAPL")

    def test_account_name_parent(self):
        account = AccountName(parts=["assets", "stocks", "AAPL"])
        parent = account.parent
        self.assertIsNotNone(parent)
        self.assertEqual(str(parent), "assets:stocks")

        grandparent = parent.parent if parent else None
        self.assertIsNotNone(grandparent)
        self.assertEqual(str(grandparent), "assets")

        great_grandparent = grandparent.parent if grandparent else None
        self.assertIsNone(great_grandparent)

    def test_is_asset_method(self):
        asset_account = AccountName(parts=["assets", "stocks", "AAPL"])
        expense_account = AccountName(parts=["expenses", "food"])
        income_account = AccountName(parts=["income", "salary"])
        liability_account = AccountName(parts=["liabilities", "credit card"])
        equity_account = AccountName(parts=["equity", "opening balances"])

        self.assertTrue(asset_account.isAsset())
        self.assertFalse(expense_account.isAsset())
        self.assertFalse(income_account.isAsset())
        self.assertFalse(liability_account.isAsset())
        self.assertFalse(equity_account.isAsset())

    def test_is_dated_subaccount_method(self):
        dated_account = AccountName(parts=["assets", "stocks", "AAPL", "20230101"])
        non_dated_asset_account = AccountName(parts=["assets", "stocks", "MSFT"])
        expense_account = AccountName(parts=["expenses", "food"])

        self.assertTrue(dated_account.isDatedSubaccount())
        self.assertFalse(non_dated_asset_account.isDatedSubaccount())
        self.assertFalse(expense_account.isDatedSubaccount())

if __name__ == '__main__':
    unittest.main()
