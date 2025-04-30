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

import unittest
from src.classes import AccountName, Commodity

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

class TestCommodity(unittest.TestCase):
    def test_is_cash_method(self):
        usd = Commodity(name="USD")
        pln = Commodity(name="PLN")
        aapl = Commodity(name="AAPL")

        self.assertTrue(usd.isCash())
        self.assertTrue(pln.isCash())
        self.assertFalse(aapl.isCash())

    def test_is_stock_method(self):
        aapl = Commodity(name="AAPL")
        goog = Commodity(name="GOOG")
        brka = Commodity(name="BRK.A") # Stock with a period - my simple regex won't catch this yet
        btc = Commodity(name="BTC")
        usd = Commodity(name="USD")
        option = Commodity(name="TSLA260116C200")

        self.assertTrue(aapl.isStock())
        self.assertTrue(goog.isStock())
        self.assertTrue(brka.isStock())
        self.assertFalse(btc.isStock())
        self.assertFalse(usd.isStock())
        self.assertFalse(option.isStock())

    def test_is_crypto_method(self):
        btc = Commodity(name="BTC")
        eth = Commodity(name="ETH")
        aapl = Commodity(name="AAPL")
        usd = Commodity(name="USD")

        self.assertTrue(btc.isCrypto())
        self.assertTrue(eth.isCrypto())
        self.assertFalse(aapl.isCrypto())
        self.assertFalse(usd.isCrypto())

    def test_is_option_method(self):
        option1 = Commodity(name="TSLA260116C200")
        option2 = Commodity(name="AAPL230721P150")
        aapl = Commodity(name="AAPL")
        btc = Commodity(name="BTC")

        self.assertTrue(option1.isOption())
        self.assertTrue(option2.isOption())
        self.assertFalse(aapl.isOption())
        self.assertFalse(btc.isOption())


if __name__ == '__main__':
    unittest.main()
