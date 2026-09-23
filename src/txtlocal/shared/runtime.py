import asyncio
from collections.abc import Coroutine
from typing import Any

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return _loop.run_until_complete(coro)
