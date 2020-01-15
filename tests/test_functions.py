from hookt import hook, trigger

import pytest

@trigger
async def identity(arg):
    return arg


class listener:

    def __init__(self, f):
        self.result = None

        @hook(f)
        async def capture(res):
            self.result = res


@pytest.mark.anyio
async def test_function():
    l = listener(identity)
    result = await identity(Ellipsis)
    assert result == l.result
