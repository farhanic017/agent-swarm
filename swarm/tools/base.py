from inspect import iscoroutine
from typing import Callable, Optional


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: dict,
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters

    def to_openai_format(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> str:
        try:
            result = self.func(**kwargs)
            if iscoroutine(result):
                result = await result
            return str(result)
        except Exception as e:
            return f"Error executing {self.name}: {e}"
