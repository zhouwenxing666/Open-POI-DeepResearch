import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional

from pydantic import Field

from app.agent.validator_base import BaseAgent
from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Memory


class ReActAgent(BaseAgent, ABC):
    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0

    @abstractmethod
    async def think(self) -> bool:
        """Process current state and decide next action"""

    @abstractmethod
    async def act(self) -> AsyncGenerator[str, None]:
        """Execute decided actions and stream results"""

    async def step(self) -> str:
        # This method is less relevant for our new streaming logic but kept for compatibility.
        should_act = await self.think()
        if not should_act:
            last_msg = self.memory.messages[-1] if self.memory.messages else None
            return last_msg.content if last_msg and last_msg.content else "Thinking complete - no action needed"
        # Since act is now a generator, we'd need to consume it to get a string.
        # This highlights why run_stream needs its own logic.
        return "Action step initiated."

    async def run_stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        Run the agent's thinking and acting loop, yielding structured, formatted results.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        self.state = AgentState.RUNNING
        self.current_step = 0
        self.memory.clear()
        if prompt:
            self.update_memory("user", prompt)

        logger.info(f"ð Starting agent '{self.name}' with prompt: {prompt}")

        while self.state == AgentState.RUNNING and self.current_step < self.max_steps:
            self.current_step += 1
            logger.info(f"--- Step {self.current_step} ---")

            # Yield a container for the whole step
            yield f'<div class="step-container"><div class="step-header">Step {self.current_step}</div>'

            try:
                can_continue = await self.think()
                last_message = self.memory.messages[-1] if self.memory.messages else None

                # 1. Yield the thinking part
                if last_message and last_message.content:
                    thought_content = f"""<div class="step-part">
<h4>ð¤ 思考 (Thinking)</h4>
<p>{last_message.content}</p>
</div>"""
                    yield thought_content

                if not can_continue or self.state == AgentState.FINISHED:
                    yield '</div>' # Close the step container
                    break

                # 2. Iterate through the action generator and yield its chunks
                if hasattr(self, 'tool_calls') and self.tool_calls:
                    async for chunk in self.act():
                        yield chunk

                yield '</div>' # Close the step container

            except Exception as e:
                logger.error(f"Error during agent execution at step {self.current_step}: {e}")
                error_message = f"An error occurred: {str(e)}"
                yield f'<div class="step-part"><p style="color:red;">{error_message}</p></div></div>'
                self.state = AgentState.ERROR
                break

        # Finalization step
        if self.state == AgentState.RUNNING: self.state = AgentState.FINISHED
        final_message = self.memory.messages[-1] if self.memory.messages else None

        final_response_text = ""
        if self.state == AgentState.FINISHED:
            final_response = "任务完成。"
            if final_message and final_message.content and not (hasattr(final_message, 'tool_calls') and final_message.tool_calls):
                 final_response = final_message.content
            logger.info(f"✅ Agent '{self.name}' finished successfully.")
            final_response_text = f"ð {final_response}"
        elif self.state == AgentState.ERROR:
            logger.error(f"❌ Agent '{self.name}' stopped due to an error.")
            final_response_text = "❌ 任务因错误中止。"
        elif self.current_step >= self.max_steps:
            logger.warning(f"⚠️ Agent '{self.name}' reached max steps limit.")
            final_response_text = "⚠️ 已达到最大执行步数，任务中止。"

        if final_response_text:
            yield f'<div class="step-container"><div class="step-header">{final_response_text}</div></div>'
