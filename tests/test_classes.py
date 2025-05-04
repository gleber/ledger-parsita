import unittest
from decimal import Decimal
from datetime import date
from src.classes import AccountName, Commodity, Amount, Cost, CostKind, Posting, Transaction

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

class TestTransaction(unittest.TestCase):
    def test_get_posting_cost_explicit_unit_cost(self):
        # Transaction with explicit unit cost
        transaction = Transaction(
            date=date(2022, 1, 1),
            payee="Buy EUR",
            postings=[
                Posting(account=AccountName(parts=["assets", "dollars"]), amount=Amount(Decimal("-135"), Commodity(name="USD"))),
                Posting(account=AccountName(parts=["assets", "euros"]), amount=Amount(Decimal("100"), Commodity(name="EUR")), cost=Cost(kind=CostKind.UnitCost, amount=Amount(Decimal("1.35"), Commodity(name="USD")))),
            ],
        )
        target_posting = transaction.postings[1] # The EUR posting
        cost = transaction.get_posting_cost(target_posting)
        self.assertIsNotNone(cost)
        self.assertEqual(cost.kind, CostKind.UnitCost)
        self.assertEqual(cost.amount, Amount(Decimal("1.35"), Commodity(name="USD")))

    def test_get_posting_cost_explicit_total_cost(self):
        # Transaction with explicit total cost
        transaction = Transaction(
            date=date(2022, 1, 1),
            payee="Buy EUR",
            postings=[
                Posting(account=AccountName(parts=["assets", "dollars"]), amount=Amount(Decimal("-135"), Commodity(name="USD"))),
                Posting(account=AccountName(parts=["assets", "euros"]), amount=Amount(Decimal("100"), Commodity(name="EUR")), cost=Cost(kind=CostKind.TotalCost, amount=Amount(Decimal("135"), Commodity(name="USD")))),
            ],
        )
        target_posting = transaction.postings[1] # The EUR posting
        cost = transaction.get_posting_cost(target_posting)
        self.assertIsNotNone(cost)
        self.assertEqual(cost.kind, CostKind.TotalCost)
        self.assertEqual(cost.amount, Amount(Decimal("135"), Commodity(name="USD")))

    def test_get_posting_cost_inferred_total_cost(self):
        # Transaction with implicit cost (Variant 3)
        transaction = Transaction(
            date=date(2022, 1, 1),
            payee="Buy EUR",
            postings=[
                Posting(account=AccountName(parts=["assets", "dollars"]), amount=Amount(Decimal("-135"), Commodity(name="USD"))),
                Posting(account=AccountName(parts=["assets", "euros"]), amount=Amount(Decimal("100"), Commodity(name="EUR"))),
            ],
        )
        target_posting = transaction.postings[1] # The EUR posting
        cost = transaction.get_posting_cost(target_posting)
        self.assertIsNotNone(cost)
        self.assertEqual(cost.kind, CostKind.TotalCost)
        self.assertEqual(cost.amount, Amount(Decimal("135"), Commodity(name="USD")))

        target_posting_other = transaction.postings[0] # The USD posting
        cost_other = transaction.get_posting_cost(target_posting_other)
        self.assertIsNotNone(cost_other)
        self.assertEqual(cost_other.kind, CostKind.TotalCost)
        self.assertEqual(cost_other.amount, Amount(Decimal("100"), Commodity(name="EUR")))


    def test_get_posting_cost_no_cost(self):
        # Transaction with no cost and not eligible for inference
        transaction = Transaction(
            date=date(2022, 1, 1),
            payee="Salary",
            postings=[
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("1000"), Commodity(name="USD"))),
                Posting(account=AccountName(parts=["income", "salary"]), amount=Amount(Decimal("-1000"), Commodity(name="USD"))),
                Posting(account=AccountName(parts=["expenses", "tax"]), amount=Amount(Decimal("200"), Commodity(name="USD"))), # More than two postings
            ],
        )
        target_posting = transaction.postings[0] # The bank posting
        cost = transaction.get_posting_cost(target_posting)
        self.assertIsNone(cost)

        # Transaction with two postings but same commodity
        transaction_same_commodity = Transaction(
            date=date(2022, 1, 1),
            payee="Transfer",
            postings=[
                Posting(account=AccountName(parts=["assets", "bank"]), amount=Amount(Decimal("-100"), Commodity(name="USD"))),
                Posting(account=AccountName(parts=["assets", "cash"]), amount=Amount(Decimal("100"), Commodity(name="USD"))),
            ],
        )
        target_posting_same_commodity = transaction_same_commodity.postings[0]
        cost_same_commodity = transaction_same_commodity.get_posting_cost(target_posting_same_commodity)
        self.assertIsNone(cost_same_commodity)


if __name__ == '__main__':
    unittest.main()
