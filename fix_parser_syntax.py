import re

file_path = "src/hledger_parser.py"

with open(file_path, "r") as f:
    content = f.read()

# Use regex to find the class definition line and add the comma if missing
corrected_content = re.sub(
    r"class HledgerParsers\(ParserContext (whitespace=None)\):",
    r"class HledgerParsers(ParserContext, \1):",
    content
)

with open(file_path, "w") as f:
    f.write(corrected_content)

print(f"Checked and fixed syntax in {file_path}")
