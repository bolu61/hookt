from hookt import hook, TriggerGroup
from anyio import sleep

import pytest


@pytest.mark.anyio
async def test_function():

    class Sample:
        g = TriggerGroup()

        @g.trigger("ident")
        async def identity(self, arg):
            await sleep(0)
            return arg

    sample = Sample()

    @sample.g.hook("ident")
    async def capture(captured_output):
        nonlocal result
        result = captured_output

    result = None

    assert await sample.identity(Ellipsis) == result
