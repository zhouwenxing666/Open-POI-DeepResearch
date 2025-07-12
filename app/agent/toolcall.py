import asyncio
import json
from typing import Any, List, Optional, Union, Dict
from app.agent.validator import Validator
from pydantic import Field
import time
from app.agent.react import ReActAgent
from app.exceptions import TokenLimitExceeded
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import TOOL_CHOICE_TYPE, AgentState, Message, ToolCall, ToolChoice
from app.tool import CreateChatCompletion, Terminate, ToolCollection
from app.tool.base import ToolResult
from app.tool.mcp import ConnectionLostError, mcp_clients_instance, MCPClientTool
from app.prompt.manus import NEXT_STEP_PROMPT as MANUS_NEXT_STEP_PROMPT
from app.prompt.validator import SYSTEM_PROMPT as VALIDATOR_SYSTEM_PROMPT, NEXT_STEP_PROMPT as VALIDATOR_NEXT_STEP_PROMPT
import re
import copy
import uuid


TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion()
    )
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO  # type: ignore

    tool_calls: List[ToolCall] = Field(default_factory=list)
    _current_base64_image: Optional[str] = None

    max_steps: int = 30
    max_observe: Optional[Union[int, bool]] = None

    max_retries: int = 10

    # The _format_validator_prompt and _run_validator_if_needed methods are unchanged
    async def _format_validator_prompt(self, messages: List[Message], response_content: str) -> str:
        """
        Formats the prompt for the validator LLM call.
        """
        user_question = "No user question found."
        for msg in messages:
            if msg.role == 'user':
                user_question = msg.content
                break

        final_prompt = f"【用户的问题】:\n{user_question}\n\n"

        final_message = response_content
        if isinstance(final_message, str) and '</think>' in final_message:
            parts = final_message.split('</think>', 1)
            # reason_message = parts[0].replace('<think>', '').strip()
            final_message_content = parts[1].strip()
            # final_prompt += f"【待判别的推理】:\n{reason_message}\n\n"
            final_prompt += f"【待判别的回复】:\n{final_message_content}\n\n"
        else:
            final_prompt += f"【待判别的回复】:\n{final_message}\n\n"

        tool_outputs = []
        for item in messages:
            if item.role == 'tool':
                tool_name = item.name
                content = item.content

                if isinstance(content, str) and 'Observed output of cmd' in content:
                    content = content.split(':', 1)[-1].strip()

                try:
                    parsed_content = json.loads(content)
                    formatted_content = json.dumps(parsed_content, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    formatted_content = str(content)

                tool_output = f"""【{tool_name}】输出结果：
{formatted_content}
--------------------"""
                tool_outputs.append(tool_output)

        if tool_outputs:
            final_prompt += "【参考信息】，其中【】中为信息来源名称：\n"
            final_prompt += "\n".join(tool_outputs)

        return final_prompt

    async def _run_validator_if_needed(self, response: Any) -> Optional[dict]:
        """
        If no tool is called, run a direct LLM call to validate the plan.
        This version correctly handles the 'str' return type from self.llm.ask().
        """

        if response.tool_calls:
            return None

        logger.info("ðŸ•µ️  0 tool selected. Initiating validation process...")
        start_time = time.time()

        try:
            validator_input_prompt = await self._format_validator_prompt(self.messages, response.content)
            validator_messages = [
                Message.user_message(VALIDATOR_NEXT_STEP_PROMPT + "\n\n" + validator_input_prompt)
            ]

            logger.warning("ðŸ¤– Validator is now verifying the plan via a direct LLM call...")

            raw_content = await self.llm.ask(messages=validator_messages)

            logger.warning(f"Validation call complete! Time taken: {time.time() - start_time:.2f}s")

            if not raw_content:
                 raise ValueError("Validator LLM call returned no content.")

            logger.warning(f"ðŸ•µ️‍♀️ Validator output:\n{raw_content}")

            conclusion_pattern = r"(?:\*\*|###\s*)判别结论(?:\*\*|\s*)(.*?)(?=(?:\s*\*\*判别结论\*\*|\s*###\s*判别结论|\Z))"
            conclusion_match = re.search(conclusion_pattern, raw_content, re.DOTALL | re.IGNORECASE)
            if not conclusion_match:
                raise ValueError("Could not find '判别结论' in the validator's output.")

            conclusion_text = conclusion_match.group(1).strip()
            is_passed = "不满意" not in conclusion_text

            reason_pattern = r"(?:\*\*|###\s*)判别理由(?:\*\*|\s*)(.*?)(?=(?:\s*\*\*判别理由\*\*|\s*###\s*判别理由|\s*\*\*判别结论\*\*|\s*###\s*判别结论|\Z))"
            reason_match = re.search(reason_pattern, raw_content, re.DOTALL | re.IGNORECASE)
            reason_text = reason_match.group(1).strip() if reason_match else "No specific reason provided."

            return {
                "is_passed": is_passed,
                "conclusion": conclusion_text,
                "reason": reason_text,
                "full_report": raw_content
            }
        except Exception as e:
            logger.error(f"ðŸš¨ An error occurred during validation: {e}", exc_info=True)
            return {
                "is_passed": False,
                "conclusion": "验证失败",
                "reason": f"在验证过程中发生意外错误: {str(e)}",
                "full_report": ""
            }

    # The think method is unchanged
    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            if self.validation_passed:
                self.messages += [user_msg]
            else:
                self.validation_passed = True

        try:
            response = await self.llm.ask_tool(
                messages=self.messages,
                system_msgs=(
                    [Message.system_message(self.system_prompt)]
                    if self.system_prompt
                    else None
                ),
                tools=self.available_tools.to_params(),
                tool_choice=self.tool_choices,
            )

            if response is None:
                logger.warning(f"ðŸš¨ {self.name} received no response from LLM, finishing task.")
                self.state = AgentState.FINISHED
                return False

            validation_result = await self._run_validator_if_needed(response)

            if validation_result:
                if validation_result["is_passed"]:
                    self.validation_passed = True
                    self.state = AgentState.FINISHED
                    logger.warning(f"✅ Validation PASSED, finishing task.")
                    final_content = response.content or ""
                    if '</think>' in final_content:
                        final_content = final_content.split('</think>', 1)[1].strip()
                    self.memory.add_message(Message.assistant_message(final_content))
                    return False
                else:
                    self.validation_passed = False
                    logger.warning(f"❌ Validation FAILED. Conclusion: {validation_result['conclusion']}")
                    logger.warning(f"Reason: {validation_result['reason']}")

            raw_tool_calls = response.tool_calls or []
            expanded_calls = []
            for call in raw_tool_calls:
                try:
                    arguments_obj = json.loads(call.function.arguments or '{}')
                    if isinstance(arguments_obj, list):
                        logger.warning(f"⚠️ Expanding a bundled tool call for '{call.function.name}'...")
                        for item in arguments_obj:
                            new_call = copy.deepcopy(call)
                            new_call.id = f"call_{uuid.uuid4().hex}"
                            new_call.function.arguments = json.dumps(item, ensure_ascii=False)
                            expanded_calls.append(new_call)
                    else:
                        expanded_calls.append(call)
                except Exception as e:
                    logger.error(f"Failed to process or expand tool call: {e}")
                    expanded_calls.append(call)

            unique_tool_calls = []
            seen_calls = set()
            for call in expanded_calls:
                call_signature = (call.function.name, call.function.arguments)
                if call_signature not in seen_calls:
                    unique_tool_calls.append(call)
                    seen_calls.add(call_signature)
                else:
                    logger.warning(f"ðŸ¤” Duplicate tool call detected and removed after expansion: {call.function.name}")

            self.tool_calls = unique_tool_calls
            content = response.content or ""

            if not content and not self.tool_calls:
                logger.warning(f"ðŸ¤” {self.name} returned no content and no tool calls. Finishing to avoid loop.")
                self.state = AgentState.FINISHED
                return False

            logger.info(f"✨ {self.name}'s thoughts: {content}")
            logger.info(f"🛠️ {self.name} selected {len(self.tool_calls) if self.tool_calls else 0} tools to use")
            if self.tool_calls:
                logger.info(f"🧰 Tools being prepared: {[call.function.name for call in self.tool_calls]}")
                logger.info(f"🔧 Tool arguments: {[call.function.arguments for call in self.tool_calls]}")

            assistant_msg = (
                Message.from_tool_calls(content=content, tool_calls=self.tool_calls)
                if self.tool_calls else Message.assistant_message(content)
            )
            self.memory.add_message(assistant_msg)

            if not self.validation_passed and validation_result:
                feedback_message = Message.user_message(
                    f"你的上一个方案没有通过质量审核，请根据以下“判别理由”进行修正并重新规划。\n\n【判别理由】:\n{validation_result['reason']} \n\n {MANUS_NEXT_STEP_PROMPT}"
                )
                self.messages.append(feedback_message)

            return bool(content or self.tool_calls)

        except Exception as e:
            if hasattr(e, "__cause__") and isinstance(e.__cause__, TokenLimitExceeded):
                token_limit_error = e.__cause__
                logger.error(f"ðŸš¨ Token limit error (from RetryError): {token_limit_error}")
                self.memory.add_message(Message.assistant_message(f"Maximum token limit reached: {str(token_limit_error)}"))
                self.state = AgentState.FINISHED
                return False
            logger.error(f"ðŸš¨ Oops! The {self.name}'s thinking process hit a snag: {e}", exc_info=True)
            self.memory.add_message(Message.assistant_message(f"Error encountered while processing: {str(e)}"))
            return False

    # [关键修复] 'act' method is now drastically simplified.
    async def act(self) -> str:
        """
        Concurrently execute all tool calls. If a QPS error occurs, the specific
        call will be retried internally. Failed calls are logged but excluded
        from the final output string.
        """
        if not self.tool_calls:
            if self.tool_choices == ToolChoice.REQUIRED:
                raise ValueError(TOOL_CALL_REQUIRED)
            last_message = self.messages[-1] if self.messages else None
            return last_message.content if last_message else "No action to perform."

        logger.info(f"Concurrently executing {len(self.tool_calls)} tool calls.")

        # Create a task for each tool call. The retry logic is now inside `execute_tool`.
        tasks = [self.execute_tool(command) for command in self.tool_calls]

        # Run all tasks concurrently and gather their results.
        # `execute_tool` will return a `ToolResult` or `None`.
        results = await asyncio.gather(*tasks)

        successful_results_str = []
        for tool_call, result in zip(self.tool_calls, results):
            # First, process the result to record it in memory (success or failure).
            processed_str = self._process_tool_result(tool_call, result)

            # Then, only include successful results in the final output string
            # for the next thinking step.
            if isinstance(result, ToolResult) and not result.error:
                 successful_results_str.append(f"Tool: {tool_call.function.name} \n Arg:{tool_call.function.arguments} \n\n Result:{processed_str}")

        if not successful_results_str:
            return "All tool calls were executed but failed or produced no output."

        return "\n\n".join(successful_results_str)

    def _process_tool_result(self, command: ToolCall, result: Optional[ToolResult]) -> str:
        """
        Helper method to process the result of a single tool execution and update memory.
        Returns the string representation of the result.
        """
        self._current_base64_image = None
        processed_result_str = ""


        if not isinstance(result, ToolResult):
            # This handles cases where a tool incorrectly returns a string or another type on error.
            error_content = str(result) if result is not None else "Tool returned an unexpected empty result."
            processed_result_str = f"Error: {error_content}"
            logger.error(f"Tool '{command.function.name}' returned an unexpected type '{type(result)}' instead of 'ToolResult'. Content: {error_content}")

        elif result.error:
            processed_result_str = f"Error: {result.error}"
            logger.error(f"Tool '{command.function.name}' with args {command.function.arguments} failed with error: {result.error}")
        else:
            processed_result_str = result.output or ""

        if self.max_observe and isinstance(processed_result_str, str):
            processed_result_str = processed_result_str[:self.max_observe]

        if isinstance(result, ToolResult) and result.base64_image:
            self._current_base64_image = result.base64_image

        if isinstance(result, ToolResult) and not result.error:
            logger.info(f"ðŸŽ¯ Tool '{command.function.name}' completed! Result: {processed_result_str}")

        # Always add a tool message to memory, whether it's a success or an error.
        tool_msg = Message.tool_message(
            content=processed_result_str,
            tool_call_id=command.id,
            name=command.function.name,
            base64_image=self._current_base64_image,
        )
        self.memory.add_message(tool_msg)

        return processed_result_str


    async def execute_tool(self, command: ToolCall) -> Optional[ToolResult]:
        """
        Execute a single tool call with internal retry logic for QPS errors.
        Returns a ToolResult on success or final failure, or None on unexpected error.
        """
        if not command or not command.function or not command.function.name:
            return ToolResult(error="Invalid command format")

        name = command.function.name
        tool = self.available_tools.get_tool(name)
        if not tool:
            return ToolResult(error=f"Unknown tool '{name}'")

        args_str = command.function.arguments or "{}"

        for attempt in range(self.max_retries + 1):
            try:
                # 将 tool 的获取和参数解析放在循环内，以便在重连后能获取新工具
                tool = self.available_tools.get_tool(name)
                if not tool:
                    # 如果重连后工具仍然不存在，说明有问题
                    return ToolResult(error=f"Unknown tool '{name}' after {attempt} attempts.")

                args = json.loads(args_str)

                args = self._validate_and_clean_tool_args(name, args, getattr(tool, 'parameters', {}))

                # 如果参数在验证后不是字典，则无法继续执行，应作为错误处理。
                if not isinstance(args, dict):
                    raise TypeError(f"Tool arguments for '{name}' are not a valid dictionary after parsing: {args}")

                args = await tool.pre_execute(self, args)
                result = await self.available_tools.execute(name=name, tool_input=args)
                result = await tool.post_execute(self, result)

                return result

            except ConnectionLostError as e:
                if e.is_qps_limit:
                    if attempt < self.max_retries:
                        wait_time = 0.1  #等100ms后重新尝试
                        logger.warning(
                            f"QPS limit for tool '{name}'. Attempt {attempt + 1}/{self.max_retries}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue  # Go to the next iteration of the retry loop.
                    else:
                        error_msg = f"Tool '{name}' failed after {self.max_retries} retries due to QPS limits."
                        logger.error(error_msg)
                        return ToolResult(error=error_msg)
                else:
                    if attempt < self.max_retries:
                        logger.warning(
                            f"Connection lost for tool '{name}'. Attempting to reconnect and retry... "
                            f"(Attempt {attempt + 1}/{self.max_retries})"
                        )
                        # Trigger the reconnect mechanism from the correct task.
                        await mcp_clients_instance.reconnect(e.server_id)
                        await asyncio.sleep(1) # Give a moment for the connection to re-establish.
                        continue # Continue to the next retry attempt.
                    else:
                        error_msg = f"Tool '{name}' failed after {self.max_retries} reconnection attempts."
                        logger.error(error_msg, exc_info=e)
                        return ToolResult(error=error_msg)


            except json.JSONDecodeError as e:
                error_msg = f"Error parsing arguments for {name}: Invalid JSON. Arguments: {args_str}"
                logger.error(f"{error_msg} | Exception: {e}")
                return ToolResult(error=error_msg)

            except Exception as e:
                error_msg = f"Non-retryable error in tool '{name}': {type(e).__name__}: {str(e)}"
                logger.error(f"Caught non-retryable exception for tool '{name}' with args {args_str}", exc_info=e)
                return ToolResult(error=error_msg)

        # This point should theoretically not be reached, but as a fallback:
        return ToolResult(error=f"Tool '{name}' failed unexpectedly after all retries.")

    # The remaining methods are unchanged
    def _validate_and_clean_tool_args(self, tool_name: str, args: Any, tool_schema: dict) -> dict:
        """
        Validates and cleans arguments for a tool call.
        Ensures that args is a dictionary before processing.
        """
        #检查 args 是否为字典，防止因 LLM 生成无效JSON而引发的 TypeError 或 KeyError。
        if not isinstance(args, dict):
            logger.warning(
                f"Arguments for tool '{tool_name}' were not a dictionary (type: {type(args)}). "
                f"Content: {args}. Cannot validate or clean."
            )
            return args 

        if tool_schema and 'properties' in tool_schema:
            allowed_params = set(tool_schema['properties'].keys())
            actual_params = set(args.keys())

            extraneous_params = actual_params - allowed_params
            if extraneous_params:
                logger.warning(
                    f"Tool '{tool_name}' was called with extraneous parameters: {list(extraneous_params)}. "
                    f"These will be removed."
                )
                for param in extraneous_params:
                    del args[param]

        if tool_name == 'maps_distance':
            if 'origins' not in args:
                args['origins'] = ''
            if 'destination' not in args:
                args['destination'] = ''

            origins = args['origins']
            destination = args['destination']

            if isinstance(origins, str) and isinstance(destination, str):
                is_origins_multiple = '|' in origins
                is_destination_multiple = '|' in destination

                if is_destination_multiple and not is_origins_multiple:
                    logger.warning(
                        f"Correcting 'maps_distance' params: 'origins' and 'destination' appear to be swapped. Swapping them back."
                    )
                    args['origins'], args['destination'] = destination, origins

        return args

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """
        This now always returns False. The agent's completion is now
        determined exclusively by the validation logic in the `think` method.
        """
        return False

    async def cleanup(self):
        """Clean up resources used by the agent's tools."""
        logger.info(f"ðŸ§¹ Cleaning up resources for agent '{self.name}'...")
        for tool_name, tool_instance in self.available_tools.tool_map.items():
            if hasattr(tool_instance, "cleanup") and asyncio.iscoroutinefunction(
                tool_instance.cleanup
            ):
                try:
                    logger.debug(f"ðŸ§¼ Cleaning up tool: {tool_name}")
                    await tool_instance.cleanup()
                except Exception as e:
                    logger.error(
                        f"ðŸš¨ Error cleaning up tool '{tool_name}': {e}", exc_info=True
                    )
        logger.info(f"✨ Cleanup complete for agent '{self.name}'.")

    async def run(self, request: Optional[str] = None) -> str:
        """Run the agent with cleanup when done."""
        try:
            return await super().run(request)
        finally:
            await self.cleanup()
