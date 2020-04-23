from hookt import TriggerGroup, HooksMixin
from anyio import sleep

import pytest


@pytest.mark.anyio
async def test_function():

    class Sample(HooksMixin):
        hooks = TriggerGroup()

        @hooks.trigger("ident")
        async def identity(self, arg):
            await sleep(0)
            return arg

    sample = Sample()

    @sample.on("ident")
    async def capture(captured_output):
        nonlocal result
        result = captured_output

    result = None

    assert await sample.identity(Ellipsis) == result
