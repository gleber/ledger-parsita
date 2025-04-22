from dataclasses import replace
from typing import Optional
import click
import pprint
from pathlib import Path
from src.filtering import filter_entries
from src.hledger_parser import parse_hledger_journal
from src.classes import Journal, JournalEntry
from parsita import ParseError



# Define the main click group
@click.group()
def cli():
    """A command-line tool for parsing hledger journal files."""
    pass


# Define the pprint command
@cli.command("pprint")  # Explicitly name the command
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)  # Use Path object
@click.option(
    "-f", "--flat", is_flag=True, help="Flatten the output of the parsed journal."
)
@click.option(
    "-s", "--strip", is_flag=True, help="Strip location information from the output."
)
@click.option(
    "-q", "--query", type=str, default=None, help="Filter transactions using a query string."
)
def pprint_cmd(filename: Path, flat: bool, strip: bool, query: Optional[str]):
    """Parses the journal file and pretty-prints the result."""
    try:
        # Pass the absolute path string to the parser function
        parsed_data = parse_hledger_journal(str(filename.absolute()))
        click.echo(f"Successfully parsed hledger journal: {filename}", err=True)

        # Apply filtering if a query is provided
        if query:
            filtered_transactions = filter_entries(parsed_data.entries, query)
        else:
            filtered_transactions = parsed_data.entries

        filtered_journal = replace(parsed_data, entries=filtered_transactions)

        if flat:
            filtered_journal = filtered_journal.flatten()
        if strip:
            filtered_journal = filtered_journal.strip_loc()
        # Use pprint.pformat for better control if needed, or just pprint
        pprint.pprint(filtered_journal, indent=2)  # Add indentation for readability
    except ParseError as e:
        # Improve error reporting
        print(f"Parsing failed in '{filename}': {e}")
        # Consider showing the problematic line/context if possible from Parsita error
    except Exception as e:
        print(f"An unexpected error occurred while processing '{filename}': {e}")
        # Consider adding traceback for debugging unexpected errors
        # import traceback
        # traceback.print_exc()


# Define the print command
@cli.command("print")  # Explicitly name the command
@click.argument(
    "filename", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)  # Use Path object
@click.option(
    "-f", "--flat", is_flag=True, help="Flatten the output of the parsed journal."
)
@click.option(
    "-s", "--strip", is_flag=True, help="Strip location information from the output."
)
@click.option(
    "-q", "--query", type=str, default=None, help="Filter transactions using a query string."
)
def print_cmd(filename: Path, flat: bool, strip: bool, query: Optional[str]):
    """Parses the journal file and prints the result using to_journal_string."""
    try:
        # Pass the absolute path string to the parser function
        parsed_data = parse_hledger_journal(str(filename.absolute()))
        click.echo(f"Successfully parsed hledger journal: {filename}", err=True)
        if flat:
            parsed_data = parsed_data.flatten()

        # Apply filtering if a query is provided
        if query:
            filtered_transactions = filter_entries(parsed_data.entries, query)
        else:
            filtered_transactions = parsed_data.entries

        # Create a new Journal object with only the filtered transactions for printing
        filtered_journal = replace(parsed_data, entries=filtered_transactions)

        if strip:
            filtered_journal = filtered_journal.strip_loc()
        # Use to_journal_string to print the data
        print(filtered_journal.to_journal_string())
    except ParseError as e:
        # Improve error reporting
        print(f"Parsing failed in '{filename}': {e}")
        # Consider showing the problematic line/context if possible from Parsita error
    except Exception as e:
        print(f"An unexpected error occurred while processing '{filename}': {e}")
        # Consider adding traceback for debugging unexpected errors
        # import traceback
        # traceback.print_exc()


if __name__ == "__main__":
    cli()
