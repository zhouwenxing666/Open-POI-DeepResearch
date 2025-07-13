from typing import Dict, List, Optional

from pydantic import Field, model_validator

from app.agent.browser import BrowserContextHelper
from app.agent.toolcall import ToolCallAgent
from app.config import config
from app.logger import logger
from app.prompt.manus import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.deepsearch_agent_fixed import DeepSearchAgent

# 确保从正确的路径导入单例和初始化函数
from app.tool.mcp import mcp_clients_instance, initialize_mcp_clients


class Manus(ToolCallAgent):
    """A versatile general-purpose agent with support for both local and MCP tools."""

    name: str = "Manus"
    description: str = "A versatile agent that can solve various tasks using multiple tools including MCP-based tools"

    system_prompt: str = SYSTEM_PROMPT.format(directory=config.workspace_root)
    next_step_prompt: str = NEXT_STEP_PROMPT

    max_observe: int = 10000
    max_steps: int = 20

    # [新增] 添加一个状态标志，用于跟踪MCP工具是否已初始化
    _mcp_tools_initialized: bool = False

    # [保留] Agent自身拥有的工具集合，用于合并本地和MCP工具
    available_tools: ToolCollection = Field(default_factory=ToolCollection)

    # special_tool_names: list[str] = Field(default_factory=lambda: [Terminate().name])
    browser_context_helper: Optional[BrowserContextHelper] = None

    @model_validator(mode="after")
    def initialize_helper(self) -> "Manus":
        """Initialize basic components and local tools."""
        self.browser_context_helper = BrowserContextHelper(self)

        # 初始化时，在这里添加本地（非MCP）工具。
        local_tools = [DeepSearchAgent()]  # 这里可以放所有非MCP的本地工具
        self.available_tools.add_tools(*local_tools)

        # 在这里初始化标志的状态
        self._mcp_tools_initialized = False

        return self

    async def cleanup(self):
        """Clean up Manus agent resources."""
        if self.browser_context_helper:
            await self.browser_context_helper.cleanup_browser()

    async def _update_tools_from_mcp(self):
        """
        Refreshes the agent's tool list from the global MCP client instance.
        This ensures the agent always has the latest tools from all connected servers.
        """
        # 1. 筛选出所有MCP工具，并从当前工具映射中移除
        mcp_tool_names = [
            name for name, tool in self.available_tools.tool_map.items()
            if hasattr(tool, 'server_id') # MCPClientTool has server_id
        ]
        for name in mcp_tool_names:
            self.available_tools.remove_tool(name)

        # 2. 从全局单例中获取最新的MCP工具列表
        # [修正] 直接访问全局单例 `mcp_clients_instance`，而不是 `self.mcp_clients_instance`
        latest_mcp_tools = list(mcp_clients_instance.tools)

        # 从 new_tools 中移除不需要的工具
        filtered_mcp_tools = [
            tool for tool in latest_mcp_tools
            if tool.name not in [
                "maps_schema_navi",
                "maps_schema_take_taxi",
                "maps_schema_personal_map",
                "maps_weather"
            ]
        ]

        # 3. 将最新的MCP工具添加到Agent的可用工具中
        if filtered_mcp_tools:
            self.available_tools.add_tools(*filtered_mcp_tools)

        logger.info(f"Refreshed tools. Total available: {len(self.available_tools.tools)}")
        # 输出可用工具的集合
        logger.info(f"Available tools: {[tool.name for tool in self.available_tools.tools]}")


    async def think(self) -> bool:
        """Process current state and decide next actions with appropriate context."""
        # 使用状态标志实现mcp客户端一次性加载
        if not self._mcp_tools_initialized:
            logger.info("First run: Initializing MCP clients and loading tools...")
            # 1. 确保全局MCP客户端已连接
            await initialize_mcp_clients()
            # 2. 设置标志，防止再次执行
            self._mcp_tools_initialized = True

        # 每次都从全局单例更新工具，以应对中途重连的情况
        await self._update_tools_from_mcp()

        original_prompt = self.next_step_prompt
        recent_messages = self.memory.messages[-3:] if self.memory.messages else []

        result = await super().think()

        # Restore original prompt
        self.next_step_prompt = original_prompt

        return result
