from pydantic import Field

# from app.agent.browser import BrowserAgent
from app.config import config
from app.prompt.browser import NEXT_STEP_PROMPT as BROWSER_NEXT_STEP_PROMPT
from app.prompt.validator import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.browser_use_tool import BrowserUseTool
from app.tool.python_execute import PythonExecute
from app.tool.str_replace_editor import StrReplaceEditor
from app.tool.hotel_search import HotelSearch
from app.tool.flight_search import FlightSearch
from app.tool.train_search import TrainSearch
from app.tool.location_search import LocationSearch
from app.tool.route_planner import RoutePlanner
from app.tool.current_location import CurrentLocation
from app.tool.location_around_search import LocationAroundSearch
from app.tool.reverse_geocoding import  ReverseGeocoding
from app.tool.around_poi_search import  AroundPOISearch
from app.tool.web_search import WebSearch
from app.agent.validator_toolcall import ToolCallAgent



class Validator(ToolCallAgent):
    """
    A versatile agent that evaluates response quality using multiple tools.

    This agent extends ToolCallAgent with a set of tools specifically designed for
    assessing the quality of responses.
    """

    name: str = "Validator"
    description: str = (
        "A versatile agent that evaluates response quality using multiple tools"
    )

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 20

    # Add general-purpose tools to the tool collection
    # BrowserUseTool(),
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
        TrainSearch(), HotelSearch(), FlightSearch(), LocationSearch(), WebSearch(), RoutePlanner()
        )
    )

    async def format_prompt(self, messages, response):
        tool_outputs = []

        final_prompt = "【用户的问题】: " + messages[0].content+ "\n\n"

        final_message = response

        if isinstance(final_message, str) and '</think>' in final_message:
            # reason_message = final_message.split('</think>', 1)[0].strip()
            # final_prompt += "【待判别的推理】: " + reason_message + "\n\n"
            final_message = final_message.split('</think>', 1)[-1].strip()
            final_prompt += "【待判别的回复】: " + final_message + "\n\n"
        else:
            final_prompt += "【待判别的回复】: " + final_message + "\n\n"

        for item in messages:
            if item.role == 'tool':
                tool_name = item.name
                content = item.content

                # 提取实际内容（去掉前面的描述性文字）
                if isinstance(content, str) and 'Observed output of cmd' in content:
                    content = content.split(':', 1)[-1].strip()

                # 尝试解析JSON内容（如果内容是JSON字符串）
                try:
                    import json
                    parsed_content = json.loads(content)
                    formatted_content = json.dumps(parsed_content, indent=2, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    formatted_content = str(content)

                # 构建格式化输出
                tool_output = f"""
                【{tool_name}】输出结果：
                {formatted_content}
                {'-'*40}
                """
                tool_outputs.append(tool_output)

        # 将所有工具输出合并成一个字符串
        final_prompt += "【参考信息】，其中【】中为信息来源名称：\n"
        final_prompt += "\n".join(tool_outputs)
        return final_prompt

    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        # Store original prompt
        original_prompt = self.next_step_prompt
        #print("next_step_prompt:", self.next_step_prompt)

        result = await super().think()

        # Restore original prompt
        self.next_step_prompt = original_prompt

        return result
