# Returns Library

The `returns` library in Python provides a set of monadic types for handling errors and side effects in a functional way.

## Key Concepts

- **Result:** A type that represents either a successful value (`Success`) or a failure (`Failure`).
- **Maybe:** A type that represents either a value (`Some`) or the absence of a value (`Nothing`).
- **IO:** A type that represents a computation that may have side effects.

## Usage in ledger-parsita

The `returns` library is used for robust error handling, allowing functions to return `Result` types to explicitly indicate success or failure without raising exceptions.

## Guidelines for using Result

When working with the `Result` class (`Success` and `Failure`), follow these guidelines:

- Except for the unit tests:
  - Prefer using the `.map()` method for transforming the value inside a `Success` instead of using `.unwrap()` or checking the type with `isinstance()`. This promotes a more functional and less      
    error-prone approach.
  - Use structural pattern matching (`match` statement) to determine if a `Result` is a `Success` or `Failure` and to extract the contained value or error.
- In unit tests prefer use of `.unwrap()` and other fail-fast techniques.

## Context7 MCP Documentation Snippets

Here are some relevant documentation snippets for Returns retrieved from the Context7 MCP:

### API Request with Result Container

```python
import requests
from returns.result import Result, safe
from returns.pipeline import flow
from returns.pointfree import bind

def fetch_user_profile(user_id: int) -> Result['UserProfile', Exception]:
    """Fetches `UserProfile` TypedDict from foreign API."""
    return flow(
        user_id,
        _make_request,
        bind(_parse_json),
    )

@safe
def _make_request(user_id: int) -> requests.Response:
    # TODO: we are not yet done with this example, read more about `IO`:
    response = requests.get('/api/users/{0}'.format(user_id))
    response.raise_for_status()
    return response

@safe
def _parse_json(response: requests.Response) -> 'UserProfile':
    return response.json()
```
SOURCE: https://github.com/dry-python/returns/blob/master/README.md#2025-04-21_snippet_7

### API Request with IOResult Container

```python
import requests
from returns.io import IOResult, impure_safe
from returns.result import safe
from returns.pipeline import flow
from returns.pointfree import bind_result

def fetch_user_profile(user_id: int) -> IOResult['UserProfile', Exception]:
    """Fetches `UserProfile` TypedDict from foreign API."""
    return flow(
        user_id,
        _make_request,
        # before: def (Response) -> UserProfile
        # after safe: def (Response) -> ResultE[UserProfile]
        # after bind_result: def (IOResultE[Response]) -> IOResultE[UserProfile]
        bind_result(_parse_json),
    )

@impure_safe
def _make_request(user_id: int) -> requests.Response:
    response = requests.get('/api/users/{0}'.format(user_id))
    response.raise_for_status()
    return response

@safe
def _parse_json(response: requests.Response) -> 'UserProfile':
    return response.json()
```
SOURCE: https://github.com/dry-python/returns/blob/master/README.md#2025-04-21_snippet_9

### Refactoring Code with Maybe Container

```python
user: Optional[User]

# Type hint here is optional, it only helps the reader here:
discount_program: Maybe['DiscountProgram'] = Maybe.from_optional(
    user,
).bind_optional(  # This won't be called if `user is None`
    lambda real_user: real_user.get_balance(),
).bind_optional(  # This won't be called if `real_user.get_balance()` is None
    lambda balance: balance.credit_amount(),
).bind_optional(  # And so on!
    lambda credit: choose_discount(credit) if credit > 0 else None,
)
```
SOURCE: https://github.com/dry-python/returns/blob/master/README.md#2025-04-21_snippet_3

### Basic Usage of Result for Error Handling

```python
from returns.result import Result, Success, Failure

def find_user(user_id: int) -> Result['User', str]:
    user = User.objects.filter(id=user_id)
    if user.exists():
        return Success(user[0])
    return Failure('User was not found')

user_search_result = find_user(1)
# => Success(User{id: 1, ...})

user_search_result = find_user(0)  # id 0 does not exist!
# => Failure('User was not found')
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/result.rst#2025-04-21_snippet_0

### Handling Async Exceptions with FutureResult

```python
import anyio
from returns.future import future_safe
from returns.io import IOFailure

@future_safe
async def raising():
    raise ValueError('Not so fast!')

ioresult = anyio.run(raising.awaitable)  # all `Future`s return IO containers
assert ioresult == IOFailure(ValueError('Not so fast!'))  # True
```
SOURCE: https://github.com/dry-python/returns/blob/master/README.md#2025-04-21_snippet_13

### Resource Management with managed

```python
from typing import TextIO
from returns.pipeline import managed, is_successful
from returns.result import ResultE
from returns.io import IOResultE, impure_safe

def read_file(file_obj: TextIO) -> IOResultE[str]:
    return impure_safe(file_obj.read)()  # this will be the final result

def close_file(
    file_obj: TextIO,
    file_contents: ResultE[str],
) -> IOResultE[None]:  # sometimes might require to use `untap`
    return impure_safe(file_obj.close)()  # this value will be dropped

managed_read = managed(read_file, close_file)

read_result = managed_read(
    impure_safe(lambda filename: open(filename, 'r'))('pyproject.toml'),
)
assert is_successful(read_result)  # file content is inside `IOSuccess`
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/pipeline.rst#2025-04-21_snippet_5

### Unwrapping Container Values with unwrap

```python
from returns.result import Failure, Success
from returns.maybe import Some, Nothing

assert Success(1).value_or(None) == 1
assert Some(0).unwrap() == 0
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/railway.rst#2025-04-21_snippet_3

### Using @safe Decorator to Handle Exceptions with Result

```python
from returns.result import Success, safe

@safe  # Will convert type to: Callable[[int], Result[float, Exception]]
def divide(number: int) -> float:
    return number / number

assert divide(1) == Success(1.0)
str(divide(0))
'<Failure: division by zero>'
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/result.rst#2025-04-21_snippet_1

### Differentiating Map vs Bind Methods with Result

```python
import json
from typing import Dict

from returns.result import Failure, Result, Success, safe

# `cast_to_bool` doesn't produce any side-effect
def cast_to_bool(arg: int) -> bool:
    return bool(arg)

# `parse_json` can produce Exceptions, so we use the `safe` decorator
# to prevent any kind of exceptions
@safe
def parse_json(arg: str) -> Dict[str, str]:
    return json.loads(arg)

assert Success(1).map(cast_to_bool) == Success(True)
assert Success('{"example": "example"}').bind(parse_json) == Success({"example": "example"})
assert Success('').bind(parse_json).alt(str) == Failure('Expecting value: line 1 column 1 (char 0)')
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/result.rst#2025-04-21_snippet_6

### Composing Containers with pipe

```python
from returns.pipeline import pipe
from returns.result import Result, Success, Failure
from returns.pointfree import bind

def regular_function(arg: int) -> float:
    return float(arg)

def returns_container(arg: float) -> Result[str, ValueError]:
    if arg != 0:
        return Success(str(arg))
    return Failure(ValueError('Wrong arg'))

def also_returns_container(arg: str) -> Result[str, ValueError]:
    return Success(arg + '!')

transaction = pipe(
    regular_function,  # composes easily
    returns_container,  # also composes easily, but returns a container
    # So we need to `bind` the next function to allow it to consume
    # the container from the previous step.
    bind(also_returns_container),
)
result = transaction(1)  # running the pipeline
assert result == Success('1.0!')
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/pipeline.rst#2025-04-21_snippet_4

### Handling Specific Exceptions with @safe Decorator

```python
@safe(exceptions=(ZeroDivisionError,))  # Other exceptions will be raised
def divide(number: int) -> float:
    if number > 10:
        raise ValueError('Too big')
    return number / number

assert divide(5) == Success(1.0)
assert divide(0).failure()
divide(15)
Traceback (most recent call last):
  ...
ValueError: Too big
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/result.rst#2025-04-21_snippet_2

### Using flow to Compose Multiple Functions

```python
from returns.pipeline import flow
assert flow(
    [1, 2, 3],
    lambda collection: max(collection),
    lambda max_number: -max_number,
) == -3
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/pipeline.rst#2025-04-21_snippet_0

### Using maybe Decorator for Optional Return Values

```python
from typing import Optional
from returns.maybe import Maybe, Some, maybe

@maybe
def number(num: int) -> Optional[int]:
    if num > 0:
        return num
    return None

result: Maybe[int] = number(1)
assert result == Some(1)
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/maybe.rst#2025-04-21_snippet_4

### Functional Style Async Composition with FutureResult

```python
import anyio
from returns.future import FutureResultE, future_safe
from returns.io import IOSuccess, IOFailure

@future_safe
async def fetch_user(user_id: int) -> 'User':
    ...

@future_safe
async def get_user_permissions(user: 'User') -> 'Permissions':
    ...

@future_safe
async def ensure_allowed(permissions: 'Permissions') -> bool:
    ...

def main(user_id: int) -> FutureResultE[bool]:
    # We can now turn `main` into a sync function, it does not `await` at all.
    # We also don't care about exceptions anymore, they are already handled.
    return fetch_user(user_id).bind(get_user_permissions).bind(ensure_allowed)

correct_user_id: int  # has required permissions
banned_user_id: int  # does not have required permissions
wrong_user_id: int  # does not exist

# We can have correct business results:
assert anyio.run(main(correct_user_id).awaitable) == IOSuccess(True)
assert anyio.run(main(banned_user_id).awaitable) == IOSuccess(False)

# Or we can have errors along the way:
assert anyio.run(main(wrong_user_id).awaitable) == IOFailure(
    UserDoesNotExistError(...),
)
```
SOURCE: https://github.com/dry-python/returns/blob/master/README.md#2025-04-21_snippet_15

### Using Future Container for Async Composition

```python
from returns.future import Future

def second() -> Future[int]:
    return Future(first()).map(lambda num: num + 1)
```
SOURCE: https://github.com/dry-python/returns/blob/master/README.md#2025-04-21_snippet_11

### Using map Method with Result Container

```python
from typing import Any
from returns.result import Success, Result

def double(state: int) -> int:
    return state * 2

result: Result[int, Any] = Success(1).map(double)
assert str(result) == '<Success: 2>'

result: Result[int, Any] = result.map(lambda state: state + 1)
assert str(result) == '<Success: 3>'
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/container.rst#2025-04-21_snippet_0

### Using @future Decorator for Async Functions

```python
import anyio
from returns.future import future, Future
from returns.io import IO

@future
async def test(arg: int) -> float:
    return arg / 2

future_instance = test(1)
assert isinstance(future_instance, Future)
assert anyio.run(future_instance.awaitable) == IO(0.5)
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/future.rst#2025-04-21_snippet_2

### Working with Multiple Containers Using curry and apply

```python
from returns.curry import curry
from returns.io import IO

@curry
def sum_two_numbers(first: int, second: int) -> int:
    return first + second

one = IO(1)
two = IO(2)
assert two.apply(one.apply(IO(sum_two_numbers))) == IO(3)
```
SOURCE: https://github.com/dry-python/returns/blob/master/docs/pages/container.rst#2025-04-21_snippet_6
