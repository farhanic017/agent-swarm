import asyncio


class TimeoutManager:
    def __init__(self, default_timeout: int = 60):
        self.default_timeout = default_timeout

    async def run_with_timeout(self, coro, timeout: int = None):
        timeout = timeout or self.default_timeout
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Agent execution timed out after {timeout}s")
