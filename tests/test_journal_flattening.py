from pathlib import Path
from src.classes import Journal, JournalEntry, Transaction, Include, AccountName, Amount, Commodity, SourceLocation # Updated import
from datetime import date
from decimal import Decimal
import pytest


TEST_INCLUDES_DIR = Path("tests/includes")

def test_simple_flattening():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    parsed_journal = Journal.parse_from_file(str(main_journal_path)).unwrap() # Updated call
    flattened_journal = parsed_journal.flatten()

    # Expected number of entries after flattening: 2 from main + 1 from journal_a + 2 from journal_b (1 from b + 1 from c)
    # plus 3 include comments
    # Total: 2 + 1 + 2 +3 = 5
    # assert len(flattened_journal.entries) == 8

    # Verify the content of the flattened entries (basic check)
    assert flattened_journal.entries[0].source_location is not None
    assert flattened_journal.entries[0].source_location.filename == main_journal_path.absolute()
    assert flattened_journal.entries[0].transaction is not None
    assert flattened_journal.entries[0].transaction.payee == "Payee Main 1"

    assert flattened_journal.entries[1].source_location is not None
    assert flattened_journal.entries[1].source_location.filename == main_journal_path.absolute()
    assert flattened_journal.entries[1].comment is not None
    assert flattened_journal.entries[1].comment.comment == "begin include journal_a.journal"

    assert flattened_journal.entries[2].source_location is not None
    assert flattened_journal.entries[2].source_location.filename == (TEST_INCLUDES_DIR / "journal_a.journal").absolute()
    assert flattened_journal.entries[2].transaction is not None
    assert flattened_journal.entries[2].transaction.payee == "Payee A"

    assert flattened_journal.entries[3].source_location is not None
    assert flattened_journal.entries[3].source_location.filename == main_journal_path.absolute()
    assert flattened_journal.entries[3].comment is not None
    assert flattened_journal.entries[3].comment.comment == "end include journal_a.journal"

    assert flattened_journal.entries[4].source_location is not None
    assert flattened_journal.entries[4].source_location.filename == main_journal_path.absolute()
    assert flattened_journal.entries[4].transaction is not None
    assert flattened_journal.entries[4].transaction.payee == "Payee Main 2"

    assert flattened_journal.entries[5].source_location is not None
    assert flattened_journal.entries[5].source_location.filename == main_journal_path.absolute()
    assert flattened_journal.entries[5].comment is not None
    assert flattened_journal.entries[5].comment.comment == "begin include journal_b.journal"

    assert flattened_journal.entries[6].source_location is not None
    assert flattened_journal.entries[6].source_location.filename == (TEST_INCLUDES_DIR / "journal_b.journal").absolute()
    assert flattened_journal.entries[6].comment is not None
    assert flattened_journal.entries[6].comment.comment == "begin include journal_c.journal"

    assert flattened_journal.entries[7].source_location is not None
    assert flattened_journal.entries[7].source_location.filename == (TEST_INCLUDES_DIR / "journal_c.journal").absolute()
    assert flattened_journal.entries[7].transaction is not None
    assert flattened_journal.entries[7].transaction.payee == "Payee C" # From nested include

    assert flattened_journal.entries[8].source_location is not None
    assert flattened_journal.entries[8].source_location.filename == (TEST_INCLUDES_DIR / "journal_b.journal").absolute()
    assert flattened_journal.entries[8].comment is not None
    assert flattened_journal.entries[8].comment.comment == "end include journal_c.journal"

    assert flattened_journal.entries[9].source_location is not None
    assert flattened_journal.entries[9].source_location.filename == (TEST_INCLUDES_DIR / "journal_b.journal").absolute()
    assert flattened_journal.entries[9].transaction is not None
    assert flattened_journal.entries[9].transaction.payee == "Payee B" # From nested include

    assert flattened_journal.entries[10].source_location is not None
    assert flattened_journal.entries[10].source_location.filename == main_journal_path.absolute()
    assert flattened_journal.entries[10].comment is not None
    assert flattened_journal.entries[10].comment.comment == "end include journal_b.journal"

def test_nested_flattening():
    journal_b_path = TEST_INCLUDES_DIR / "journal_b.journal"
    parsed_journal_b = Journal.parse_from_file(str(journal_b_path)).unwrap() # Updated call
    flattened_journal_b = parsed_journal_b.flatten()

    # Expected number of entries after flattening: 1 from journal_b + 1 from journal_c
    assert len(flattened_journal_b.entries) == 4

    # Verify the content of the flattened entries
    assert flattened_journal_b.entries[0].comment is not None
    assert flattened_journal_b.entries[0].comment.comment == "begin include journal_c.journal"
    assert flattened_journal_b.entries[1].transaction is not None
    assert flattened_journal_b.entries[1].transaction.payee == "Payee C"
    assert flattened_journal_b.entries[2].comment is not None
    assert flattened_journal_b.entries[2].comment.comment == "end include journal_c.journal"
    assert flattened_journal_b.entries[3].transaction is not None
    assert flattened_journal_b.entries[3].transaction.payee == "Payee B"

def test_original_journal_unchanged():
    main_journal_path = TEST_INCLUDES_DIR / "main.journal"
    parsed_journal = Journal.parse_from_file(str(main_journal_path)).unwrap() # Updated call
    original_entries_count = len(parsed_journal.entries)

    flattened_journal = parsed_journal.flatten()

    # Verify the original journal's entries list is unchanged
    assert len(parsed_journal.entries) == original_entries_count
    # Verify the original journal still contains Include entries
    assert any(entry.include is not None for entry in parsed_journal.entries)
