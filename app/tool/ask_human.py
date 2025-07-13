
import asyncio
import sys
from typing import TYPE_CHECKING

from app.tool import BaseTool

if TYPE_CHECKING:
    from app.agent.base import BaseAgent


class AskHuman(BaseTool):
    """Add a tool to ask human for help."""

    name: str = "ask_human"
    description: str = "Use this tool to ask human for help."
    parameters: str = {
        "type": "object",
        "properties": {
            "inquire": {
                "type": "string",
                "description": "The question you want to ask human.",
            }
        },
        "required": ["inquire"],
    }

    async def execute(self, inquire: str, agent: "BaseAgent", **kwargs) -> str:
        """
        Pauses execution by raising a special exception and asks the human for input.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return "Error: ask_human must be run within an asyncio event loop."

        # 状态仍然存储在 agent 上
        agent._human_input_future = loop.create_future()
        agent._human_input_request = {"question": inquire}

        print(
            f"Agent has set human input request. Raising exception to pause.",
            file=sys.stderr,
        )

        # 只抛出信号异常，不传递任何状态
        raise HumanInputRequiredError()
