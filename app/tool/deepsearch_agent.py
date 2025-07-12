import asyncio
import json
import time
import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, TYPE_CHECKING

import aiohttp
from itertools import groupby

from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log

from app.tool.base import BaseTool, ToolResult

# 避免循环导入
if TYPE_CHECKING:
    from app.agent.toolcall import ToolCallAgent


logger = logging.getLogger(__name__)

class DeepSearchAgent(BaseTool):
    name: str = "deep_search"
    description: str = """Perform deep search and analysis using an autonomous agent.
    This tool uses an iterative process of planning, searching, reasoning, reflecting, and summarizing to provide comprehensive answers."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The question or topic to deepsearch and analyze in depth.",
            },
            "user_original_query": {
                "type": "string",
                "description": "(optional) The original user query for context.",
            }
        },
        "required": ["query", "user_original_query"],
    }

    #_SEARCH_API_URL = "http://10.191.60.13:8050/api/chat"
    _SEARCH_API_URL = "http://10.191.60.13:8055/api/chat"  #qwen3-14b
    _LOG_DIR = "logs"


    def __init__(self):
        super().__init__()
        # 确保日志目录存在
        os.makedirs(self._LOG_DIR, exist_ok=True)


    async def execute(self, query: str, user_original_query: str) -> Dict:
        """
        Execute deep search analysis for the given query.

        Args:
            query (str): The question or topic to deepsearch and analyze.
            user_original_query (str): The original user query for context.

        Returns:
            Dict: The comprehensive analysis results including all steps and final answer.
        """
        logger.info(f"Executing deep search for query: '{query}' with original query: '{user_original_query}'")
        # 验证查询不为空
        if not query.strip():
            raise ValueError("Query cannot be empty")

        logger.info(f"Starting deep search for query: '{query}'")
        posted_query = {
            "当前处理问题": query,
            "用户原始问题": user_original_query
        }
        post_data = json.dumps(posted_query, ensure_ascii=False)

        try:
            retry = 0
            while retry <= 5:
                retry += 1
                result = await self._send_request(post_data)
                formatted_result = self._format_final_result(result, post_data)
                if formatted_result["status"] == "success" and formatted_result["final_answer"]:
                    logger.info(f"Deep search completed successfully for query: '{query}'")
                    return ToolResult(output=formatted_result)
                else:
                    logger.warning(f"Empty final answer received, retrying... (attempt {retry}/5)")
                    # time.sleep(5)
                    await asyncio.sleep(5)

            # 执行深度搜索分析
            return ToolResult(
                error=f"Failed to retrieve a valid answer after {retry} attempts.",
                output={"query": query, "final_answer": None}
            )

        except Exception as e:
            logger.error(f"Deep search failed: {str(e)}")
            return ToolResult(
                error=f"Failed to perform deep search: {str(e)}",
                output={"query": query, "final_answer": None}
            )


    # post_execute 钩子，用于格式化最终输出，deepsearch在execute之后的处理都可以写在这
    async def post_execute(self, agent: "ToolCallAgent", result: Any) -> Any:
        """
        After executing DeepSearch, format the raw dictionary result into a
        user-friendly string for display.
        """
        if not isinstance(result, ToolResult) or result.error:
            # 如果不是 ToolResult，或者已经有错误，直接返回
            logger.error(f"DeepSearch post_execute received not ToolResult: {result}")
            return result

        raw_dict = result.output # 从 ToolResult 中获取原始的 dict
        if not isinstance(raw_dict, dict):
            # 如果 output 不是 dict，说明上游有问题，直接返回
            logger.error(f"DeepSearch post_execute received non-dict output: {raw_dict}")
            return result


        if "final_answer" not in raw_dict or not raw_dict["final_answer"]:
            return ToolResult(error="调用deep_search出现错误，未找到最终答案。")

        # if "final_answer" not in result or not result["final_answer"]:
        #     return "调用deep_search出现错误，未找到最终答案。"

        try:
            final_answer = raw_dict["final_answer"]

            detailed_logs = raw_dict.get("detailed_logs", [])
            query_info = raw_dict.get("query", "")
            logger.info(f"train_data deepsearch query:{query_info}  Detailed logs: {detailed_logs}")

            step_queries = ["<font size=4 face='黑体'>开始深度搜索...</font>"]
            step_queries.append("<font size=4 face='黑体'>完成深度搜索：</font>\n" + final_answer)

            formatted_string = "\n".join(step_queries)
            return ToolResult(output=formatted_string)

            # 返回格式化后的字符串
            # return "\n".join(step_queries)

        except Exception as e:
            logger.error(f"Error formatting deep_search result in post_execute: {e}")
            # 返回一个友好的错误信息
            # 返回一个包含错误信息的 ToolResult 对象
            return ToolResult(error=f"处理deep_search结果时出错: {e}")
            # return f"处理deep_search结果时出错: {e}"


    async def _send_request(self, question:str):
        """
        Send a request to the deep search API.

        Args:
            question (str): The question to search.

        Returns:
            dict: The response from the API.
        """
        payload = {
            "prompt": question,
        }

        timeout = aiohttp.ClientTimeout(total=600)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self._SEARCH_API_URL, json=payload) as response:
                response.raise_for_status()
                content = await response.read()

            data = json.loads(content)
            return data
                # if response.status != 200:
                #     raise Exception(f"API request failed with status {response.status}")
                # return await response.json()


    def _extract_dict(self, text):
        summaries = []
        # print(f"all data: {text}")
        log_dict = self._extract_outermost_dicts(text)

        print(f"log_dict: {log_dict}")
        # step_dict = []
        for idx, d in enumerate(log_dict):
            # print(f"Processing dict: {d}")
            try:
                parsed = json.loads(d, strict=False)
                if idx > 0:
                    if d == log_dict[idx-1]:
                        continue
                # step_dict.append(parsed)
                if isinstance(parsed, dict) and "summary" in parsed:
                    summaries.append(parsed["summary"])
            except Exception:
                continue  # 忽略无法解析为 JSON 的内容
        if summaries:
            first_summary = summaries[0]
            return first_summary, log_dict
        else:
            print("没有找到 summary")
            return None, log_dict

    def _format_final_result(self, result: dict, query: str) -> Dict:

        """
        Format the final result from the deep search response.

        Args:
            result (str): The raw result from the deep search API.
            query (str): The original query.

        Returns:
            Dict: The formatted result including all steps and final answer.
        """
        # 提取最后一个 summary
        # print(type(result))
        first_summary, log_dict = self._extract_dict(str(result["message"]))
        # print(f"first_summary: {first_summary}")
        if not first_summary:
            return {
                "status": "error",
                "message": "No summary found in the response",
                "query": query,
                "final_answer": "",
                "detailed_logs": log_dict
            }

        return {
            "status": "success",
            "message": f"Deep search completed summaries found.",
            "query": query,
            "final_answer": first_summary,
            "detailed_logs": log_dict
        }



    def _extract_outermost_dicts(self, s):
        result = []

        # print(s.split("\n"))
        lines = s.split("\n")
        for line in lines:
            if "{" not in line or not line:
                continue
            if line.startswith("[{"):
                result.append(line)
                continue
            if 'planning:{"command"' in line:
                # 处理 planning: 开头的行
                line = line.split('planning:')[-1]

            elif 'web_search:{"questiones"' in line:
                # 处理 web_search: 开头的行
                line = line.split('web_search:')[-1]
            else:
                continue
            if line not in result:
                result.append(line)
        return result



if __name__ == "__main__":
    # 示例用法
    tool = DeepSearch()
    query = "What are the latest advancements in AI?"

    # 执行深度搜索
    result = asyncio.run(tool.execute(query))
    # print(result)
    # 打印结果
    # print(json.dumps(result, indent=2, ensure_ascii=False))

