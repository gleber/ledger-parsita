import click
import pprint
from pathlib import Path
from src.hledger_parser import parse_hledger_journal
from src.classes import Journal
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
def pprint_cmd(filename: Path, flat: bool, strip: bool):
    """Parses the journal file and pretty-prints the result."""
    try:
        # Pass the absolute path string to the parser function
        parsed_data = parse_hledger_journal(str(filename.absolute()))
        print(f"Successfully parsed hledger journal: {filename}")
        if flat:
            parsed_data = parsed_data.flatten()
        if strip:
            parsed_data = parsed_data.strip_loc()
        # Use pprint.pformat for better control if needed, or just pprint
        pprint.pprint(parsed_data, indent=2)  # Add indentation for readability
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
def print_cmd(filename: Path, flat: bool, strip: bool):
    """Parses the journal file and prints the result using to_journal_string."""
    try:
        # Pass the absolute path string to the parser function
        parsed_data = parse_hledger_journal(str(filename.absolute()))
        click.echo(f"Successfully parsed hledger journal: {filename}", err=True)
        if flat:
            parsed_data = parsed_data.flatten()
        if strip:
            parsed_data = parsed_data.strip_loc()
        # Use to_journal_string to print the data
        print(parsed_data.to_journal_string())
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
