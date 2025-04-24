# Parsita Library

Parsita is a parsing library for Python. It allows defining grammars and parsing text based on those grammars.

## Key Concepts

- **Parsers:** Objects that attempt to match a pattern in the input text.
- **Grammars:** Collections of parsers that define the structure of the language being parsed.
- **Parsing:** The process of applying a grammar to input text to produce a structured representation.

## Usage in ledger-parsita

Parsita is used to parse the hledger journal file format, converting the text-based journal entries into structured Python objects.

## Important Considerations

- Avoid using `from parsita import *` because it imports a `Result` class that conflicts with the `Result` class from the `returns` library, which is also used in this project. Explicitly import necessary components from `parsita` instead.

## Context7 MCP Documentation Snippets

Here are some relevant documentation snippets for Parsita retrieved from the Context7 MCP:

### Hello World Parser Implementation

```python
from parsita import *

class HelloWorldParsers(ParserContext, whitespace=r'[ ]*'):
    hello_world = lit('Hello') >> ',' >> reg(r'[A-Z][a-z]*') << '!'

# A successful parse produces the parsed value
name = HelloWorldParsers.hello_world.parse('Hello, David!').unwrap()
assert name == 'David'

# A parsing failure produces a useful error message
name = HelloWorldParsers.hello_world.parse('Hello David!').unwrap()
# parsita.state.ParseError: Expected ',' but found 'David'
# Line 1, character 7
#
# Hello David!
#       ^
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/index.md#2025-04-21_snippet_1

### Defining Basic Numeric List Parser

```python
from parsita import *

class NumericListParsers(ParserContext, whitespace=r'[ ]*'):
    integer_list = '[' >> repsep(reg('[+-]?[0-9]+') > int, ',') << ']'
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/getting_started.md#2025-04-21_snippet_0

### Using Basic Sequential Parser (&) for URL Parsing

```python
from parsita import *

class UrlParsers(ParserContext):
    url = lit('http', 'ftp') & '://' & reg(r'[^/]+') & reg(r'.*')

assert UrlParsers.url.parse('http://drhagen.com/blog/sane-equality/') == \
    Success(['http', '://', 'drhagen.com', '/blog/sane-equality/'])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/sequential_parsers.md#2025-04-21_snippet_0

### Implementing Alternative Number Parsers (|)

```python
from parsita import *

class NumberParsers(ParserContext):
    integer = reg(r'[-+]?[0-9]+') > int
    real = reg(r'[+-]?\d+\.\d+(e[+-]?\d+)?') | 'nan' | 'inf' > float
    number = real | integer

assert NumberParsers.number.parse('4.0000') == Success(4.0)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/alternative_parsers.md#2025-04-21_snippet_1

### Using Discard Operators (>> and <<) for Point Coordinate Parsing

```python
from parsita import *

class PointParsers(ParserContext, whitespace=r'[ ]*'):
    integer = reg(r'[-+]?[0-9]+') > int
    point = '(' >> integer << ',' & integer << ')'

assert PointParsers.point.parse('(4, 3)') == Success([4, 3])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/sequential_parsers.md#2025-04-21_snippet_1

### Implementing Summation Parser with Repeated Elements

```python
from parsita import *

class SummationParsers(ParserContext, whitespace=r'[ ]*'):
    integer = reg(r'[-+]?[0-9]+') > int
    summation = integer & rep('+' >> integer) > (lambda x: sum([x[0]] + x[1]))

assert SummationParsers.summation.parse('1 + 1 + 2 + 3 + 5') == Success(12)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/repeated_parsers.md#2025-04-21_snippet_0

### Implementing Validation Logic with Transformation Parser (>=)

```python
from dataclasses import dataclass

from parsita import *

@dataclass
class Percent:
    number: int

def to_percent(number: int) -> Parser[str, Percent]:
    if not 0 <= number <= 100:
        return failure("a number between 0 and 100")
    else:
        return success(Percent(number))

class PercentParsers(ParserContext):
    percent = (reg(r"[0-9]+") > int) >= to_percent

assert PercentParsers.percent.parse('50') == Success(Percent(50))
assert isinstance(PercentParsers.percent.parse('150'), Failure)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/conversion_parsers.md#2025-04-21_snippet_1

### Converting Text to Integers with Conversion Parser (>)

```python
from parsita import *

class IntegerParsers(ParserContext):
    integer = reg(r'[-+]?[0-9]+') > int

assert IntegerParsers.integer.parse('-128') == Success(-128)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/conversion_parsers.md#2025-04-21_snippet_0

### Using literal parsers (lit)

```python
from parsita import *

class HelloParsers(ParserContext):
    hello = lit('Hello World!')

assert HelloParsers.hello.parse('Hello World!') == Success('Hello World!')
assert isinstance(HelloParsers.hello.parse('Goodbye'), Failure)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/terminal_parsers.md#2025-04-21_snippet_0

### Using regular expression parsers (reg)

```python
from parsita import *

class IntegerParsers(ParserContext):
    integer = reg(r'[-+]?[0-9]+')

assert IntegerParsers.integer.parse('-128') == Success('-128')
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/terminal_parsers.md#2025-04-21_snippet_1

### Creating List Parser with Separated Repeated Elements (repsep)

```python
from parsita import *

class ListParsers(ParserContext, whitespace=r'[ ]*'):
    integer = reg(r'[-+]?[0-9]+') > int
    my_list = '[' >> repsep(integer, ',') << ']'

assert ListParsers.my_list.parse('[1,2,3]') == Success([1, 2, 3])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/repeated_parsers.md#2025-04-21_snippet_1

### Creating Context-Dependent Parsers with Transformation Parser (>=)

```python
from parsita import *

def select_parser(type: str):
    if type == 'int':
        return reg(r"[0-9]+") > int
    elif type == 'decimal':
        return reg(r"[0-9]+\.[0-9]+") > float

class NumberParsers(ParserContext, whitespace=r'[ ]*'):
    type = lit('int', 'decimal')
    number = type >= select_parser

assert NumberParsers.number.parse('int 5') == Success(5)
assert isinstance(NumberParsers.number.parse('int 2.0'), Failure)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/conversion_parsers.md#2025-04-21_snippet_2

### Using Predicate Parser (pred) to Validate Parsed Values

```python
from parsita import *

class IntervalParsers(ParserContext, whitespace=r'[ ]*'):
    number = reg('\d+') > int
    pair = '[' >> number << ',' & number << ']'
    interval = pred(pair, lambda x: x[0] <= x[1], 'ordered pair')

assert IntervalParsers.interval.parse('[1, 2]') == Success([1, 2])
assert IntervalParsers.interval.parse('[2, 1]') != Success([2, 1])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/miscellaneous_parsers.md#2025-04-21_snippet_0

### Using Longest Alternative Parser (longest)

```python
from parsita import *

class ExpressionParsers(ParserContext):
    name = reg(r'[a-zA-Z_]+')
    function = name & '(' >> expression << ')'
    expression = longest(name, function)

assert ExpressionParsers.expression.parse('f(x)') == Success(['f', 'x'])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/alternative_parsers.md#2025-04-21_snippet_1

### First Alternative Parser Implementation (first)

```python
from parsita import *

class ExpressionParsers(ParserContext):
    keyword = lit('pi', 'nan', 'inf')
    name = reg(r'[a-zA-Z_]+')
    function = name & '(' >> expression << ')'
    expression = first(keyword, function, name)

assert ExpressionParsers.expression.parse('f(x)') == Success(['f', 'x'])
assert str(ExpressionParsers.expression.parse('pi(x)').failure()) == (
    "Expected end of source but found '('\
"
    "Line 1, character 3\n\n"
    "pi(x)\n"
    "  ^  "
)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/alternative_parsers.md#2025-04-21_snippet_2

### Optional Parser Implementation (opt)

```python
from parsita import *

class DeclarationParsers(ParserContext, whitespace=r'[ ]*'):
    id = reg(r'[A-Za-z_][A-Za-z0-9_]*')
    declaration = id & opt(':' >> id)

assert DeclarationParsers.declaration.parse('x: int') == Success(['x', ['int']])
assert DeclarationParsers.declaration.parse('x') == Success(['x', []])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/alternative_parsers.md#2025-04-21_snippet_3

### Creating Forward Declarations with fwd() Parser

```python
from parsita import *

class AddingParsers(ParserContext):
    number = reg(r'[+-]?\d+') > int
    expr = fwd()
    base = '(' >> expr << ')' | number
    expr.define(rep1sep(base, '+') > sum)

assert AddingParsers.expr.parse('2+(1+2)+3') == Success(8)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/miscellaneous_parsers.md#2025-04-21_snippet_4

### Implementing Heredoc Parsing with until() Parser

```python
from parsita import *

class TestParser(ParserContext, whitespace=r'\s*'):
    heredoc = reg("[A-Za-z]+") >= (lambda token: until(token) << token)

content = "EOF\nAnything at all\nEOF"
assert TestParser.heredoc.parse(content) == Success("Anything at all\n")
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/miscellaneous_parsers.md#2025-04-21_snippet_1

### Using any1 Parser for Single Element Matching

```python
from parsita import *

class DigitParsers(ParserContext):
    digit = pred(any1, lambda x: x['type'] == 'digit', 'a digit') > \
        (lambda x: x['payload'])

assert DigitParsers.digit.parse([{'type': 'digit', 'payload': 3}]) == \
    Success(3)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/miscellaneous_parsers.md#2025-04-21_snippet_2

### Using constant() to create a function that always returns the same value

```python
from parsita import *
from parsita.util import constant

class BooleanParsers(ParserContext):
    true = lit('true') > constant(True)
    false = lit('false') > constant(False)
    boolean = true | false

assert BooleanParsers.boolean.parse('false') == Success(False)
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/utility_functions.md#2025-04-21_snippet_0

### Using splat() to convert a multi-argument function for use with sequential parsers

```python
from collections import namedtuple
from parsita import *
from parsita.util import splat

Url = namedtuple('Url', ['host', 'port', 'path'])

class UrlParsers(ParserContext):
    host = reg(r'[A-Za-z0-9.]+')
    port = reg(r'[0-9]+') > int
    path = reg(r'[-._~A-Za-z0-9/]*')
    url = 'https://' >> host << ':' & port & path > splat(Url)
assert UrlParsers.url.parse('https://drhagen.com:443/blog/') == \
    Success(Url('drhagen.com', 443, '/blog/'))
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/utility_functions.md#2025-04-21_snippet_1

### Pattern Matching Parser Results with Python 3.10+

```python
from parsita import *

class NumericListParsers(ParserContext, whitespace=r'[ ]*'):
    integer_list = '[' >> repsep(reg('[+-]?[0-9]+') > int, ',') << ']'

result = NumericListParsers.integer_list.parse('[1, 1, 2, 3, 5]')

match result:
    case Success(value):
        python_list = value
    case Failure(error):
        raise error
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/getting_started.md#2025-04-21_snippet_1

### Pre-Python 3.10 Parser Result Handling

```python
from parsita import *

class NumericListParsers(ParserContext, whitespace=r'[ ]*'):
    integer_list = '[' >> repsep(reg('[+-]?[0-9]+') > int, ',') << ']'

result = NumericListParsers.integer_list.parse('[1, 1, 2, 3, 5]')

if isinstance(result, Success):
    python_list = result.unwrap()
elif isinstance(result, Failure):
    raise result.failure()
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/getting_started.md#2025-04-21_snippet_2

### Handling End of File with eof Parser

```python
from parsita import *

class OptionsParsers(ParserContext):
    option = reg(r'[A-Za-z]+') << '=' & reg(r'[A-Za-z]+') << (';' | eof)
    options = rep(option)

assert OptionsParsers.options.parse('log=warn;detail=minimal;') == \
    Success([['log', 'warn'], ['detail', 'minimal']])
assert OptionsParsers.options.parse('log=warn;detail=minimal') == \
    Success([['log', 'warn'], ['detail', 'minimal']])
```
SOURCE: https://github.com/drhagen/parsita/blob/master/docs/miscellaneous_parsers.md#2025-04-21_snippet_3
