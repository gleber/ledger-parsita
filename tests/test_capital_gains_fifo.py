import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from src.classes import (
    Journal,
    Transaction,
    Posting,
    AccountName,
    Amount,
    Commodity,
    SourceLocation,
    JournalEntry,
    CostKind,
    Cost
)
from src.capital_gains import (
    find_open_transactions,
    find_close_transactions,
    calculate_capital_gains,
    CapitalGainResult
)
from src.balance import calculate_balances_and_lots, BalanceSheet
from tests.test_capital_gains import create_test_journal
from src.hledger_parser import parse_hledger_journal_content


def test_calculate_capital_gains_simple():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-15 * Sell AAPL
    assets:stocks:AAPL          -5 AAPL
    assets:cash                 1000 USD
    income:capital-gains        -100 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()

    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("5")
    assert result.cost_basis.quantity == Decimal("750") # 5/10 * 1500
    assert result.proceeds.quantity == Decimal("1000")
    assert result.gain_loss.quantity == Decimal("250") # 1000 - 750
    assert result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_multiple_opens_single_close():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-05 * Open AAPL Lot 2
    assets:stocks:AAPL:20230105  15 AAPL @@ 2500 USD
    equity:opening-balances     -15 AAPL
    assets:cash                -2500 USD

2023-01-20 * Sell AAPL
    assets:stocks:AAPL          -12 AAPL
    assets:cash                 2000 USD
    income:capital-gains        -200 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 2

    # Match 1 (from Lot 1)
    result1 = capital_gain_results[0]
    assert result1.matched_quantity.quantity == Decimal("10")
    assert result1.cost_basis.quantity == pytest.approx(Decimal("1500")) # 10/10 * 1500
    assert result1.proceeds.quantity == pytest.approx(Decimal("1666.666666666666666666666667")) # 10/12 * 2000
    assert result1.gain_loss.quantity == pytest.approx(Decimal("166.666666666666666666666667")) # 1666.66... - 1500
    assert result1.gain_loss.commodity.name == "USD"

    # Match 2 (from Lot 2)
    result2 = capital_gain_results[1]
    assert result2.matched_quantity.quantity == Decimal("2")
    assert result2.cost_basis.quantity == pytest.approx(Decimal("333.3333333333333333333333333")) # 2/15 * 2500
    assert result2.proceeds.quantity == pytest.approx(Decimal("333.3333333333333333333333333")) # 2/12 * 2000
    assert result2.gain_loss.quantity == pytest.approx(Decimal("0")) # 333.33... - 333.33...
    assert result2.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_single_open_multiple_closes():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  20 AAPL @@ 3000 USD
    equity:opening-balances     -20 AAPL
    assets:cash                -3000 USD

2023-01-15 * Sell AAPL Part 1
    assets:stocks:AAPL          -5 AAPL
    assets:cash                 1000 USD
    income:capital-gains        -100 USD

2023-01-20 * Sell AAPL Part 2
    assets:stocks:AAPL          -8 AAPL
    assets:cash                 1500 USD
    income:capital-gains        -150 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 2

    # Match 1 (from first sale)
    result1 = capital_gain_results[0]
    assert result1.matched_quantity.quantity == Decimal("5")
    assert result1.cost_basis.quantity == Decimal("750") # 5/20 * 3000
    assert result1.proceeds.quantity == Decimal("1000")
    assert result1.gain_loss.quantity == Decimal("250") # 1000 - 750
    assert result1.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_multiple_assets():
    journal_string = """
2023-01-01 * Open AAPL
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-02 * Open MSFT
    assets:stocks:MSFT:20230102  15 MSFT @@ 2500 USD
    equity:opening-balances     -15 MSFT
    assets:cash                -2500 USD

2023-01-15 * Sell AAPL
    assets:stocks:AAPL          -5 AAPL
    assets:cash                 1000 USD
    income:capital-gains        -100 USD

2023-01-20 * Sell MSFT
    assets:stocks:MSFT          -8 MSFT
    assets:cash                 1500 USD
    income:capital-gains        -150 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 2

    # Verify results for AAPL
    aapl_result = next(
        (
            r
            for r in capital_gain_results
            if r.matched_quantity.commodity.name == "AAPL"
        ),
        None,
    )
    assert aapl_result is not None
    assert aapl_result.matched_quantity.quantity == Decimal("5")
    assert aapl_result.cost_basis.quantity == Decimal("750") # 5/10 * 1500
    assert aapl_result.proceeds.quantity == Decimal("1000")
    assert aapl_result.gain_loss.quantity == Decimal("250")
    assert aapl_result.gain_loss.commodity.name == "USD"

    # Verify results for MSFT
    msft_result = next(
        (
            r
            for r in capital_gain_results
            if r.matched_quantity.commodity.name == "MSFT"
        ),
        None,
    )
    assert msft_result is not None
    assert msft_result.matched_quantity.quantity == Decimal("8")
    assert msft_result.cost_basis.quantity == pytest.approx(Decimal("1333.333333333333333333333333")) # 8/15 * 2500
    assert msft_result.proceeds.quantity == pytest.approx(Decimal("1500"))
    assert msft_result.gain_loss.quantity == pytest.approx(Decimal("166.666666666666666666666667")) # 1500 - 1333.33...
    assert msft_result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_excludes_non_asset_closing_postings():
    journal_string = """
2023-01-01 * Open AAPL Lot 1
    assets:stocks:AAPL:20230101  10 AAPL @@ 1500 USD
    equity:opening-balances     -10 AAPL
    assets:cash                -1500 USD

2023-01-15 * Withdraw USD
    assets:cash:USD          -100 USD
    expenses:withdrawal       100 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    # Only asset closing postings should be considered for matching
    assert len(capital_gain_results) == 0


def test_calculate_capital_gains_handles_undated_open_accounts():
    journal_string = """
2023-01-01 * Open BTC Lot 1
    assets:crypto:BTC:20230101  1 BTC @@ 30000 USD
    equity:opening-balances     -1 BTC
    assets:cash                -30000 USD

2023-01-15 * Sell BTC
    assets:crypto:BTC          -0.5 BTC
    assets:cash                 20000 USD
    income:capital-gains        -5000 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("0.5")
    assert result.cost_basis.quantity == Decimal("15000") # 0.5/1 * 30000
    assert result.proceeds.quantity == Decimal("20000") # Assuming full proceeds go to this match for simplicity in this test
    assert result.gain_loss.quantity == Decimal("5000") # 20000 - 15000
    assert result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_partial_match_gain():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  10 XYZ @@ 1000 USD
    equity:opening-balances     -10 XYZ
    assets:cash                -1000 USD

2023-01-15 * Sell XYZ Partial
    assets:stocks:XYZ          -4 XYZ
    assets:cash                 600 USD
    income:capital-gains        -200 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("4")
    assert result.cost_basis.quantity == Decimal("400") # 4/10 * 1000
    assert result.proceeds.quantity == Decimal("600") # 4/4 * 600 (all proceeds for this sale)
    assert result.gain_loss.quantity == Decimal("200") # 600 - 400
    assert result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_partial_match_loss():
    journal_string = """
2023-01-01 * Open ABC Lot 1
    assets:stocks:ABC:20230101  10 ABC @@ 1000 USD
    equity:opening-balances     -10 ABC
    assets:cash                -1000 USD

2023-01-15 * Sell ABC Partial
    assets:stocks:ABC          -4 ABC
    assets:cash                 300 USD
    expenses:capital-loss      -100 USD
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("4")
    assert result.cost_basis.quantity == Decimal("400") # 4/10 * 1000
    assert result.proceeds.quantity == Decimal("300") # 4/4 * 300 (all proceeds for this sale)
    assert result.gain_loss.quantity == Decimal("-100") # 300 - 400
    assert result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_multiple_postings_same_commodity():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  10 XYZ @@ 1000 USD
    equity:opening-balances     -10 XYZ
    assets:cash                -1000 USD

2023-01-15 * Sell XYZ and Receive Funds
    assets:stocks:XYZ          -5 XYZ
    assets:cash                 800 USD
    income:dividends:XYZ        50 USD
    income:capital-gains       -350 USD ; Example balancing posting
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("5")
    assert result.cost_basis.quantity == Decimal("500") # 5/10 * 1000
    assert result.proceeds.quantity == Decimal("850") # Proceeds from sale (800) + Dividend (50) - the code should sum all positive cash postings
    assert result.gain_loss.quantity == Decimal("350") # 850 - 500
    assert result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_multiple_cash_postings():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  10 XYZ @@ 1000 USD
    equity:opening-balances     -10 XYZ
    assets:cash                -1000 USD

2023-01-15 * Sell XYZ and Receive Funds in Two Accounts
    assets:stocks:XYZ          -5 XYZ
    assets:cash:broker1         400 USD
    assets:cash:broker2         450 USD
    income:capital-gains       -350 USD ; Example balancing posting
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("5")
    assert result.cost_basis.quantity == Decimal("500") # 5/10 * 1000
    assert result.proceeds.quantity == Decimal("850") # Proceeds in broker1 (400) + Proceeds in broker2 (450)
    assert result.gain_loss.quantity == Decimal("350") # 850 - 500
    assert result.gain_loss.commodity.name == "USD"


def test_calculate_capital_gains_insufficient_lots():
    journal_string = """
2023-01-01 * Open XYZ Lot 1
    assets:stocks:XYZ:20230101  5 XYZ @@ 500 USD
    equity:opening-balances     -5 XYZ
    assets:cash                -500 USD

2023-01-15 * Sell XYZ More Than Owned
    assets:stocks:XYZ          -10 XYZ
    assets:cash                 1500 USD
    income:capital-gains       -1000 USD ; Example balancing
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)

    # Expect a warning to be printed and results for the matched quantity
    # The function should still process the available lots
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 1 # Should match the available 5 shares
    result = capital_gain_results[0]
    assert result.matched_quantity.quantity == Decimal("5")
    assert result.cost_basis.quantity == Decimal("500") # 5/5 * 500
    # Proceeds should be proportional to the matched quantity
    assert result.proceeds.quantity == Decimal("750") # 5/10 * 1500
    assert result.gain_loss.quantity == Decimal("250") # 750 - 500
    assert result.gain_loss.commodity.name == "USD"

def test_calculate_capital_gains_complex_fifo():
    journal_string = """
2023-01-01 * Buy ABC Lot 1
    assets:stocks:ABC:20230101  10 ABC @@ 1000 USD
    equity:opening-balances     -10 ABC
    assets:cash                -1000 USD

2023-01-05 * Buy ABC Lot 2
    assets:stocks:ABC:20230105  15 ABC @@ 2250 USD
    equity:opening-balances     -15 ABC
    assets:cash                -2250 USD

2023-01-10 * Buy ABC Lot 3
    assets:stocks:ABC:20230110  5 ABC @@ 1000 USD
    equity:opening-balances     -5 ABC
    assets:cash                -1000 USD

2023-01-15 * Sell ABC Part 1 (from Lot 1)
    assets:stocks:ABC          -8 ABC
    assets:cash                 1200 USD
    income:capital-gains        -400 USD ; Example balancing

2023-01-20 * Sell ABC Part 2 (from Lot 1 and Lot 2)
    assets:stocks:ABC          -10 ABC
    assets:cash                 1800 USD
    income:capital-gains        -300 USD ; Example balancing

2023-01-25 * Sell ABC Part 3 (from Lot 2 and Lot 3)
    assets:stocks:ABC          -7 ABC
    assets:cash                 1500 USD
    income:capital-gains        -200 USD ; Example balancing
"""
    journal = parse_hledger_journal_content(journal_string, Path("a.journal")).unwrap()
    transactions_only = [entry.transaction for entry in journal.entries if entry.transaction is not None]
    balance_sheet = calculate_balances_and_lots(transactions_only)
    capital_gain_results = calculate_capital_gains(transactions_only, balance_sheet)

    assert len(capital_gain_results) == 4 # 3 sales, matching against 1, 2, and 1 lots respectively

    # Sale 1 (8 ABC from Lot 1)
    result1 = capital_gain_results[0]
    assert result1.matched_quantity.quantity == Decimal("8")
    assert result1.cost_basis.quantity == Decimal("800") # 8/10 * 1000
    assert result1.proceeds.quantity == Decimal("1200") # 8/8 * 1200
    assert result1.gain_loss.quantity == Decimal("400") # 1200 - 800
    assert result1.gain_loss.commodity.name == "USD"

    # Sale 2 (2 ABC from Lot 1, 8 ABC from Lot 2)
    result2 = capital_gain_results[1]
    assert result2.matched_quantity.quantity == Decimal("2")
    assert result2.cost_basis.quantity == Decimal("200") # 2/10 * 1000
    assert result2.proceeds.quantity == pytest.approx(Decimal("360")) # 2/10 * 1800
    assert result2.gain_loss.quantity == pytest.approx(Decimal("160")) # 360 - 200
    assert result2.gain_loss.commodity.name == "USD"

    result3 = capital_gain_results[2]
    assert result3.matched_quantity.quantity == Decimal("8")
    assert result3.cost_basis.quantity == pytest.approx(Decimal("1200")) # 8/15 * 2250
    assert result3.proceeds.quantity == pytest.approx(Decimal("1440")) # 8/10 * 1800
    assert result3.gain_loss.quantity == pytest.approx(Decimal("240")) # 1440 - 1200
    assert result3.gain_loss.commodity.name == "USD"

    # Sale 3 (7 ABC from Lot 2)
    result4 = capital_gain_results[3]
    assert result4.matched_quantity.quantity == Decimal("7")
    assert result4.cost_basis.quantity == pytest.approx(Decimal("1050")) # 7/15 * 2250
    assert result4.proceeds.quantity == pytest.approx(Decimal("1500")) # 7/7 * 1500
    assert result4.gain_loss.quantity == pytest.approx(Decimal("450")) # 1500 - 1050
    assert result4.gain_loss.commodity.name == "USD"
