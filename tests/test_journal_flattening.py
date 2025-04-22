import unittest
from pathlib import Path
from src.hledger_parser import parse_hledger_journal
from src.classes import Journal, JournalEntry, Transaction, Include, AccountName, Amount, Commodity, SourceLocation
from datetime import date
from decimal import Decimal


TEST_INCLUDES_DIR = Path("tests/includes")

class TestJournalFlattening(unittest.TestCase):

    def test_simple_flattening(self):
        main_journal_path = TEST_INCLUDES_DIR / "main.journal"
        parsed_journal = parse_hledger_journal(str(main_journal_path))
        flattened_journal = parsed_journal.flatten()

        # Expected number of entries after flattening: 2 from main + 1 from journal_a + 2 from journal_b (1 from b + 1 from c)
        # plus 3 include comments
        # Total: 2 + 1 + 2 +3 = 5
        self.assertEqual(len(flattened_journal.entries), 8)

        # Verify the content of the flattened entries (basic check)
        self.assertEqual(flattened_journal.entries[0].transaction.payee, "Payee Main 1")
        self.assertEqual(flattened_journal.entries[1].comment.comment, "include journal_a.journal")
        self.assertEqual(flattened_journal.entries[2].transaction.payee, "Payee A")
        self.assertEqual(flattened_journal.entries[3].transaction.payee, "Payee Main 2")
        self.assertEqual(flattened_journal.entries[4].comment.comment, "include journal_b.journal")
        self.assertEqual(flattened_journal.entries[5].comment.comment, "include journal_c.journal")
        self.assertEqual(flattened_journal.entries[6].transaction.payee, "Payee C") # From nested include
        self.assertEqual(flattened_journal.entries[7].transaction.payee, "Payee B") # From nested include

    def test_nested_flattening(self):
        journal_b_path = TEST_INCLUDES_DIR / "journal_b.journal"
        parsed_journal_b = parse_hledger_journal(str(journal_b_path))
        flattened_journal_b = parsed_journal_b.flatten()

        # Expected number of entries after flattening: 1 from journal_b + 1 from journal_c
        self.assertEqual(len(flattened_journal_b.entries), 3)

        # Verify the content of the flattened entries
        self.assertEqual(flattened_journal_b.entries[0].comment.comment, "include journal_c.journal")
        self.assertEqual(flattened_journal_b.entries[1].transaction.payee, "Payee C")
        self.assertEqual(flattened_journal_b.entries[2].transaction.payee, "Payee B")

    def test_source_location_preservation(self):
        main_journal_path = TEST_INCLUDES_DIR / "main.journal"
        parsed_journal = parse_hledger_journal(str(main_journal_path))
       
        flattened_journal = parsed_journal.flatten()
        self.assertEqual(len(flattened_journal.entries), 8)
        # Verify source locations for entries from different files
        self.assertIsNotNone(flattened_journal.entries[0])
        self.assertIsNotNone(flattened_journal.entries[0].source_location)
        self.assertEqual(flattened_journal.entries[0].source_location.filename, main_journal_path.absolute())
        self.assertEqual(flattened_journal.entries[1].source_location.filename, main_journal_path.absolute())
        self.assertEqual(flattened_journal.entries[2].source_location.filename, (TEST_INCLUDES_DIR / "journal_a.journal").absolute())
        self.assertEqual(flattened_journal.entries[3].source_location.filename, main_journal_path.absolute())
        self.assertEqual(flattened_journal.entries[4].source_location.filename, main_journal_path.absolute())
        self.assertEqual(flattened_journal.entries[5].source_location.filename, (TEST_INCLUDES_DIR / "journal_b.journal").absolute())
        self.assertEqual(flattened_journal.entries[6].source_location.filename, (TEST_INCLUDES_DIR / "journal_c.journal").absolute())
        self.assertEqual(flattened_journal.entries[7].source_location.filename, (TEST_INCLUDES_DIR / "journal_b.journal").absolute())

    def test_original_journal_unchanged(self):
        main_journal_path = TEST_INCLUDES_DIR / "main.journal"
        parsed_journal = parse_hledger_journal(str(main_journal_path))
        original_entries_count = len(parsed_journal.entries)
        
        flattened_journal = parsed_journal.flatten()

        # Verify the original journal's entries list is unchanged
        self.assertEqual(len(parsed_journal.entries), original_entries_count)
        # Verify the original journal still contains Include entries
        self.assertTrue(any(entry.include for entry in parsed_journal.entries))


if __name__ == '__main__':
    unittest.main()
