from hookt import hook, trigger
from anyio import sleep

import pytest


@pytest.mark.anyio
async def test_function():

    @trigger
    async def identity(arg):
        await sleep(0)
        return arg

    @hook(identity)
    async def capture(captured_output):
        nonlocal result
        result = captured_output

    result = None

    assert await identity(Ellipsis) == result
