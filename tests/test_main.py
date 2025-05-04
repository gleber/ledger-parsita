import re
import subprocess
from pathlib import Path
import pytest

TEST_INCLUDES_DIR = Path("tests/includes")

def test_cli_flat_option():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    # Use subprocess to run the main.py script with the --flat option
    result = subprocess.run(
        ["python", "-m", "src.main", "pprint", "--flat", str(main_journal_path)],
        capture_output=True,
        text=True,
        check=True,  # Raise an exception if the command fails
    )
    output = result.stdout

    # Basic check: ensure the output contains expected elements from flattened journal
    assert "Payee Main 1" in output
    assert "Payee A" in output
    assert "Payee Main 2" in output
    assert "Payee C" in output
    assert "Payee B" in output
    # Ensure include directives are NOT in the flattened output
    assert "include journal_a.journal" not in output
    assert "include journal_b.journal" not in output
    assert "include journal_c.journal" not in output

def test_cli_strip_option():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    # Use subprocess to run the main.py script with the --strip option
    result = subprocess.run(
        ["python", "-m", "src.main", "pprint", "--strip", str(main_journal_path)],
        capture_output=True,
        text=True,
        check=True,  # Raise an exception if the command fails
    )
    output = result.stdout

    location_pattern = re.compile(r"SourceLocation")
    assert location_pattern.search(output) is None, "Location information found in stripped output"

def test_cli_print_command():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    expected_output = f"""; {main_journal_path.absolute()}:0:67
2023-01-15 Payee Main 1
  Assets:Cash  10.00 $
  Income:Job  -10.00 $

; {main_journal_path.absolute()}:69:27
include journal_a.journal

; {main_journal_path.absolute()}:98:73
2023-01-20 Payee Main 2
  Assets:Bank  5.00 $
  Expenses:Utilities  -5.00 $

; {main_journal_path.absolute()}:173:27
include journal_b.journal"""
    result = subprocess.run(
        ["python", "-m", "src.main", "print", str(main_journal_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    output = (
        result.stdout.strip()
    )  # Strip leading/trailing whitespace for comparison

    assert output == expected_output.strip()

def test_cli_balance_command_taxes_journal():
    """Tests that the balance CLI command succeeds for examples/taxes/all.journal."""
    taxes_journal_path = Path("examples/taxes/all.journal")

    result = subprocess.run(
        ["python", "-m", "src.main", "balance", str(taxes_journal_path)],
        capture_output=True,
        text=True,
        check=False,  # Do not raise an exception for non-zero exit codes
    )

    # Assert that the command exited successfully (return code 0)
    assert result.returncode == 0

def test_cli_print_command_flat():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    expected_output = """2023-01-15 Payee Main 1
  Assets:Cash  10.00 $
  Income:Job  -10.00 $

; begin include journal_a.journal

2023-01-01 Payee A
  Assets:Cash  1.00 $
  Expenses:Food  -1.00 $

; end include journal_a.journal

2023-01-20 Payee Main 2
  Assets:Bank  5.00 $
  Expenses:Utilities  -5.00 $

; begin include journal_b.journal

; begin include journal_c.journal

2023-03-01 Payee C
  Assets:Cash  3.00 $
  Income:Salary  -3.00 $

; end include journal_c.journal

2023-02-01 Payee B
  Assets:Cash  2.00 $
  Expenses:Rent  -2.00 $

; end include journal_b.journal"""
    result = subprocess.run(
        [
            "python",
            "-m",
            "src.main",
            "print",
            "--flat",
            "--strip",
            str(main_journal_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.strip()

    assert output == expected_output.strip()

def test_cli_print_command_strip():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    expected_output = """2023-01-15 Payee Main 1
  Assets:Cash  10.00 $
  Income:Job  -10.00 $

include journal_a.journal

2023-01-20 Payee Main 2
  Assets:Bank  5.00 $
  Expenses:Utilities  -5.00 $

include journal_b.journal"""
    result = subprocess.run(
        ["python", "-m", "src.main", "print", "--strip", str(main_journal_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.strip()

    assert output == expected_output.strip()

def test_cli_find_positions_command():
    positions_journal_path = TEST_INCLUDES_DIR / "journal_positions.journal"
    expected_output_lines = [
        # "Successfully parsed ..." is on stderr, not on stdout
        "",
        "Opening Transactions:",
        "- 2023-01-01 Opening Transaction 1 (Line 0)",
        "- 2023-01-15 Opening Transaction 2 (Line 132)",
        "",
        "Closing Transactions:",
        "- 2023-02-01 Closing Transaction 1 (Partial) (Line 264)",
        "- 2023-03-15 Closing Transaction 2 (Full) (Line 521)",
    ]
    expected_output = "\n".join(expected_output_lines)

    result = subprocess.run(
        ["python", "-m", "src.main", "find-positions", str(positions_journal_path)],
        capture_output=True,
        text=True,
        check=True,  # Raise an exception if the command fails
    )
    output = result.stdout

    # Split output and expected output into lines for more robust comparison
    output_lines = output.splitlines()
    expected_output_lines_stripped = [
        line.strip() for line in expected_output_lines
    ]
    output_lines_stripped = [line.strip() for line in output_lines]

    # Compare line by line, ignoring potential differences in whitespace at the end of lines
    assert len(output_lines_stripped) == len(expected_output_lines_stripped)
    assert output_lines_stripped == expected_output_lines_stripped

def test_cli_balance_command():
    balance_journal_path = TEST_INCLUDES_DIR / "test_balance.journal"
    expected_output = """Current Balances:
assets:bank
  -1850 USD
assets:broker:AAPL:20230120
  5 AAPL
assets:broker:GOOG:20230125
  10 GOOG
assets:cash
  1080 USD
equity:opening-balances
  -1000 USD
expenses:food
  20 USD
expenses:travel
  50 EUR
income:salary
  -500 USD
liabilities:credit-card
  -50 EUR"""

    result = subprocess.run(
        ["python", "-m", "src.main", "balance", str(balance_journal_path)],
        capture_output=True,
        text=True,
        check=True,  # Raise an exception if the command fails
    )
    output = result.stdout.strip()

    assert output == expected_output.strip()
