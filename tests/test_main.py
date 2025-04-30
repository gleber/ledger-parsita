import re
import unittest
import subprocess
from pathlib import Path

TEST_INCLUDES_DIR = Path("tests/includes")


class TestMain(unittest.TestCase):
    def test_cli_flat_option(self):
        main_journal_path = TEST_INCLUDES_DIR / "main.journal"
        # Use subprocess to run the main.py script with the --flat option
        import subprocess

        result = subprocess.run(
            ["python", "-m", "src.main", "pprint", "--flat", str(main_journal_path)],
            capture_output=True,
            text=True,
            check=True,  # Raise an exception if the command fails
        )
        output = result.stdout

        # Basic check: ensure the output contains expected elements from flattened journal
        self.assertIn("Payee Main 1", output)
        self.assertIn("Payee A", output)
        self.assertIn("Payee Main 2", output)
        self.assertIn("Payee C", output)
        self.assertIn("Payee B", output)
        # Ensure include directives are NOT in the flattened output
        self.assertNotIn("include journal_a.journal", output)
        self.assertNotIn("include journal_b.journal", output)
        self.assertNotIn("include journal_c.journal", output)

    def test_cli_strip_option(self):
        main_journal_path = TEST_INCLUDES_DIR / "main.journal"
        # Use subprocess to run the main.py script with the --strip option
        import subprocess

        result = subprocess.run(
            ["python", "-m", "src.main", "pprint", "--strip", str(main_journal_path)],
            capture_output=True,
            text=True,
            check=True,  # Raise an exception if the command fails
        )
        output = result.stdout

        location_pattern = re.compile(r"SourceLocation")
        self.assertIsNone(
            location_pattern.search(output),
            "Location information found in stripped output",
        )

    def test_cli_print_command(self):
        self.maxDiff = None
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

        self.assertEqual(output, expected_output.strip())

    def test_cli_print_command_flat(self):
        self.maxDiff = None
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

        self.assertEqual(output, expected_output.strip())

    def test_cli_print_command_strip(self):
        self.maxDiff = None
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

        self.assertEqual(output, expected_output.strip())

    def test_cli_find_positions_command(self):
        self.maxDiff = None
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
        self.assertEqual(len(output_lines_stripped), len(expected_output_lines_stripped))
        self.assertEqual(output_lines_stripped, expected_output_lines_stripped)


if __name__ == "__main__":
    unittest.main()
