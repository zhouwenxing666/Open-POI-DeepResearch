import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, cast

from mcp import ClientSession, McpError, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import ListToolsResult, TextContent

from app.config import config
from app.logger import logger
from app.tool.base import BaseTool, ToolResult
from app.tool.tool_collection import ToolCollection
from anyio import ClosedResourceError

class ConnectionLostError(Exception):
    """Custom exception to signal that the MCP connection was lost or a retryable error occurred."""
    def __init__(self, server_id: str, original_exception: Optional[Exception] = None, message: str = "", is_qps_limit: bool = False):
        self.server_id = server_id
        self.original_exception = original_exception
        self.is_qps_limit = is_qps_limit
        _message = message or f"Connection to MCP server '{server_id}' was lost."
        super().__init__(_message)


class MCPClientTool(BaseTool):
    """Represents a tool proxy that can be called on the MCP server from the client side."""

    session: Optional[ClientSession] = None
    server_id: str = ""
    original_name: str = ""
    parent_client: Optional["MCPClients"] = None

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool by making a remote call to the MCP server."""
        if not self.session or not self.parent_client:
            return ToolResult(
                error="Not connected to MCP server or parent client is missing"
            )

        try:
            logger.info(
                 f"Executing tool: {self.original_name} on server '{self.server_id}' with args: {kwargs}"
            )
            result = await self.session.call_tool(self.original_name, kwargs)
            content_str = ", ".join(
                item.text for item in result.content if isinstance(item, TextContent)
            )

            if "CUQPS_HAS_EXCEEDED_THE_LIMIT" in content_str:
                error_message = f"QPS limit exceeded for tool '{self.original_name}' on server '{self.server_id}' with args {kwargs}"
                logger.warning(error_message)
                raise ConnectionLostError(server_id=self.server_id, message=error_message, is_qps_limit=True)

            logger.info(
                f"Tool '{self.original_name}' executed successfully. Output: {content_str[:200]}..."
            )
            return ToolResult(output=content_str or "No output returned.")

        except (McpError, ClosedResourceError) as e:
            error_message = f"MCP connection error for tool '{self.original_name}' on server '{self.server_id}': {e}"
            logger.warning(error_message, exc_info=True)
            # 确保在真正的连接错误时，is_qps_limit 为 False
            raise ConnectionLostError(server_id=self.server_id, original_exception=e, message=error_message, is_qps_limit=False)

        except Exception as e:
            if isinstance(e, ConnectionLostError):
                raise
            error_message = (
                f"An unexpected error occurred while calling tool '{self.original_name}' "
                f"on server '{self.server_id}' with args {kwargs}: {str(e)}"
            )
            logger.error(error_message, exc_info=True)
            return ToolResult(error=error_message)


class MCPClients(ToolCollection):
    """
    A collection of tools that connects to multiple MCP servers and manages available tools.
    Includes self-healing capabilities by automatically reconnecting on fatal errors.
    """

    sessions: Dict[str, ClientSession] = {}
    exit_stacks: Dict[str, AsyncExitStack] = {}
    server_configs: Dict[str, Dict[str, Any]] = {}
    reconnect_locks: Dict[str, asyncio.Lock] = {}
    HEARTBEAT_INTERVAL = 180
    heartbeat_tasks: Dict[str, asyncio.Task] = {}

    description: str = "MCP client tools for server interaction"

    def __init__(self):
        super().__init__()
        self.name = "mcp"

    async def connect_sse(self, server_url: str, server_id: str = "") -> None:
        """Connect to an MCP server using SSE transport."""
        if not server_url:
            raise ValueError("Server URL is required.")
        server_id = server_id or server_url

        self.server_configs[server_id] = {"type": "sse", "url": server_url}
        self.reconnect_locks.setdefault(server_id, asyncio.Lock())

        if server_id in self.sessions:
            await self.disconnect(server_id)

        logger.info(f"Connecting to SSE server '{server_id}' at {server_url}...")
        exit_stack = AsyncExitStack()

        try:
            streams_context = sse_client(url=server_url)
            streams = await exit_stack.enter_async_context(streams_context)
            session = await exit_stack.enter_async_context(ClientSession(*streams))

            self.exit_stacks[server_id] = exit_stack
            self.sessions[server_id] = session

            await self._initialize_and_list_tools(server_id)
            self._start_heartbeat(server_id, session)

        except Exception as e:
            logger.error(f"Failed to establish connection for server '{server_id}': {e}", exc_info=True)
            await exit_stack.aclose()
            raise

    def _start_heartbeat(self, server_id: str, session: ClientSession):
        """Creates and starts a background task to send periodic pings."""
        logger.info(f"Starting heartbeat for server '{server_id}'...")
        if server_id in self.heartbeat_tasks:
            self.heartbeat_tasks[server_id].cancel()

        coro = self._heartbeat_task_coro(server_id, session)
        task = asyncio.create_task(coro)
        self.heartbeat_tasks[server_id] = task

    async def _heartbeat_task_coro(self, server_id: str, session: ClientSession):
        """The background coroutine that sends pings."""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await session.list_tools()
                logger.info(f"Heartbeat check successful for server '{server_id}'.")
            except asyncio.CancelledError:
                logger.info(f"Heartbeat for server '{server_id}' was cancelled.")
                break
            except (McpError, ClosedResourceError) as e:
                logger.warning(
                    f"Heartbeat check failed for server '{server_id}': {e}. Connection likely lost."
                )
                logger.warning(f"Triggering reconnect for server '{server_id}' due to failed heartbeat.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in heartbeat task for server '{server_id}': {e}", exc_info=True)
                break

    async def connect_stdio(
        self, command: str, args: List[str], server_id: str = ""
    ) -> None:
        """Connect to an MCP server using stdio transport."""
        if not command:
            raise ValueError("Server command is required.")
        server_id = server_id or command

        self.server_configs[server_id] = {
            "type": "stdio",
            "command": command,
            "args": args,
        }
        self.reconnect_locks.setdefault(server_id, asyncio.Lock())

        if server_id in self.sessions:
            await self.disconnect(server_id)

        logger.info(
            f"Connecting to stdio server '{server_id}' with command '{command}'..."
        )
        exit_stack = AsyncExitStack()

        try:
            server_params = StdioServerParameters(command=command, args=args)
            stdio_transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await exit_stack.enter_async_context(ClientSession(read, write))

            self.exit_stacks[server_id] = exit_stack
            self.sessions[server_id] = session

            await self._initialize_and_list_tools(server_id)
        except Exception as e:
            logger.error(f"Failed to establish stdio connection for '{server_id}': {e}", exc_info=True)
            await exit_stack.aclose()
            raise

    async def reconnect(self, server_id: str) -> None:
        """Disconnects and reconnects to a server using its stored configuration."""
        if server_id not in self.server_configs:
            logger.error(
                f"Cannot reconnect to server '{server_id}': No configuration found."
            )
            return

        lock = self.reconnect_locks.get(server_id)
        if not lock or lock.locked():
            logger.info(
                f"Reconnection for server '{server_id}' is already in progress or lock not found. Skipping."
            )
            return

        async with lock:
            logger.info(f"Attempting to reconnect to server '{server_id}'...")
            try:
                # 1. 取消旧的心跳任务
                old_task = self.heartbeat_tasks.pop(server_id, None)
                if old_task and not old_task.done():
                    old_task.cancel()
                    try:
                        await asyncio.sleep(0) # Allow cancellation to propagate
                    except asyncio.CancelledError:
                        pass # Expected

                # 2. 安全地关闭并清理旧的连接资源
                old_exit_stack = self.exit_stacks.pop(server_id, None)
                self.sessions.pop(server_id, None) # 移除会话引用

                if old_exit_stack:
                    logger.info(f"Closing old connection resources for server '{server_id}'...")
                    try:
                        # 显式、异步地关闭资源栈，这将正确处理底层的 TaskGroup
                        await old_exit_stack.aclose()
                    except Exception as e:
                        # 即使关闭失败也要记录并继续，因为我们的目标是重新连接
                        logger.warning(
                            f"Error while closing old exit_stack for server '{server_id}': {e}",
                            exc_info=True
                        )

                # 3. 移除与该服务器相关的所有工具
                self.remove_tools_by_server(server_id)
                logger.info(f"Successfully cleaned up old state for server '{server_id}'.")


                # 4. 重新连接
                config = self.server_configs[server_id]
                if config["type"] == "sse":
                    await self.connect_sse(config["url"], server_id)
                elif config["type"] == "stdio":
                    await self.connect_stdio(
                        config["command"], config["args"], server_id
                    )

                logger.info(f"Successfully reconnected to server '{server_id}'.")
            except Exception as e:
                logger.error(
                    f"Failed to reconnect to server '{server_id}': {e}", exc_info=True
                )

    async def _initialize_and_list_tools(self, server_id: str) -> None:
        """Initialize session and populate tool map."""
        session = self.sessions.get(server_id)
        if not session:
            raise RuntimeError(f"Session not initialized for server {server_id}")

        await session.initialize()
        response = await session.list_tools()

        self.remove_tools_by_server(server_id)

        for tool_def in response.tools:
            original_name = tool_def.name

            server_tool = MCPClientTool(
                name=original_name,
                description=tool_def.description,
                parameters=tool_def.inputSchema,
                session=session,
                server_id=server_id,
                original_name=original_name,
                parent_client=self,
            )
            self.add_tool(server_tool)

        self.tools = tuple(self.tool_map.values())
        logger.info(
            f"Connected to server '{server_id}' with tools: {[tool.name for tool in response.tools]}"
        )

    def remove_tools_by_server(self, server_id: str):
        """Removes all tools associated with a specific server."""
        tools_to_remove = [
            k
            for k, v in self.tool_map.items()
            if isinstance(v, MCPClientTool) and v.server_id == server_id
        ]
        if tools_to_remove:
            logger.info(
                f"Removing {len(tools_to_remove)} tools from server '{server_id}': {tools_to_remove}"
            )
            for tool_name in tools_to_remove:
                self.remove_tool(tool_name)
            self.tools = tuple(self.tool_map.values())

    async def disconnect(self, server_id: str = "") -> None:
        """Disconnect from a specific MCP server or all servers if no server_id provided."""
        if server_id:
            task = self.heartbeat_tasks.pop(server_id, None)
            if task:
                task.cancel()
                try:
                    await asyncio.sleep(0)
                except asyncio.CancelledError:
                    pass

            if server_id in self.sessions:
                logger.info(f"Disconnecting from MCP server '{server_id}'...")
                exit_stack = self.exit_stacks.pop(server_id, None)
                if exit_stack:
                    try:
                        await exit_stack.aclose()
                    except Exception as e:
                        logger.error(
                            f"Error during exit_stack.aclose() for server '{server_id}': {e}",
                            exc_info=True,
                        )

                self.sessions.pop(server_id, None)
                self.remove_tools_by_server(server_id)
                logger.info(f"Disconnected from MCP server '{server_id}'.")
        else:
            server_ids = list(self.sessions.keys())
            logger.info(f"Disconnecting from all {len(server_ids)} MCP servers...")
            await asyncio.gather(*(self.disconnect(sid) for sid in server_ids))
            self.tool_map = {}
            self.tools = tuple()
            logger.info("Disconnected from all MCP servers.")


# --- 单例模式 ---
mcp_clients_instance = MCPClients()
_mcp_init_lock = asyncio.Lock()
_mcp_is_initialized = False


async def initialize_mcp_clients():
    global _mcp_is_initialized
    if _mcp_is_initialized:
        return
    async with _mcp_init_lock:
        if _mcp_is_initialized:
            return
        logger.info("Initializing MCP clients for the first time...")
        for server_id, server_config in config.mcp_config.servers.items():
            try:
                if server_config.type == "sse":
                    if server_config.url:
                        await mcp_clients_instance.connect_sse(
                            server_config.url, server_id
                        )
                elif server_config.type == "stdio":
                    if server_config.command:
                        await mcp_clients_instance.connect_stdio(
                            server_config.command, server_config.args or [], server_id
                        )
            except Exception as e:
                logger.error(
                    f"Failed to connect to MCP server {server_id} during initial setup: {e}"
                )
        _mcp_is_initialized = True
        logger.info("Global MCP clients initialized.")


async def cleanup_mcp_clients():
    global _mcp_is_initialized
    if _mcp_is_initialized:
        logger.info("Cleaning up global MCP clients...")
        await mcp_clients_instance.disconnect()
        _mcp_is_initialized = False
