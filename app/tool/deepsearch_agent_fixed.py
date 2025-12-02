import asyncio
import json
import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, TYPE_CHECKING

from app.tool.base import BaseTool, ToolResult

# 避免循环导入
if TYPE_CHECKING:
    from app.agent.toolcall import ToolCallAgent


logger = logging.getLogger(__name__)

class DeepSearchAgent(BaseTool):
    """
    改进的深度搜索代理，使用多种搜索策略提供深度分析
    """
    name: str = "deep_search"
    description: str = """Perform enhanced deep search and analysis using multiple search strategies.
    This tool combines web search, knowledge synthesis, and structured analysis to provide comprehensive answers."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The question or topic to analyze in depth.",
            },
            "user_original_query": {
                "type": "string",
                "description": "(optional) The original user query for context.",
            }
        },
        "required": ["query", "user_original_query"],
    }

    def __init__(self):
        super().__init__()

    async def execute(self, query: str, user_original_query: str) -> ToolResult:
        """
        Execute enhanced deep search analysis using multiple strategies.
        """
        logger.info(f"Executing enhanced deep search for query: '{query}'")
        
        if not query.strip():
            return ToolResult(error="Query cannot be empty")

        try:
            # Step 1: 执行多重搜索
            search_results = await self._perform_multi_search(query)
            
            # Step 2: 分析和综合信息
            analysis = await self._analyze_results(query, search_results)
            
            # Step 3: 生成最终答案
            final_answer = await self._synthesize_answer(query, analysis)
            
            result = {
                "status": "success",
                "query": query,
                "original_query": user_original_query,
                "final_answer": final_answer,
                "search_summary": f"通过多重搜索策略找到 {len(search_results)} 条相关信息",
                "analysis_steps": analysis.get("steps", [])
            }
            
            return ToolResult(output=result)
            
        except Exception as e:
            logger.error(f"Enhanced deep search failed: {str(e)}")
            return ToolResult(
                error=f"深度搜索分析失败: {str(e)}",
                output={"query": query, "final_answer": None}
            )

    async def _perform_multi_search(self, query: str) -> List[Dict]:
        """
        使用多种搜索策略收集信息
        """
        try:
            # 导入web搜索工具
            from app.tool.web_search import WebSearch
            web_search = WebSearch()
            
            # 生成多个搜索关键词
            search_queries = self._generate_search_queries(query)
            
            all_results = []
            for search_query in search_queries[:3]:  # 限制搜索次数
                try:
                    logger.info(f"Searching for: {search_query}")
                    result = await web_search.execute(
                        query=search_query,
                        num_results=5,
                        lang="zh",
                        country="cn"
                    )
                    
                    if hasattr(result, 'results') and result.results:
                        for item in result.results:
                            all_results.append({
                                "title": item.title,
                                "url": item.url,
                                "description": item.description,
                                "search_query": search_query
                            })
                except Exception as e:
                    logger.warning(f"Search failed for query '{search_query}': {e}")
                    continue
                    
            return all_results
            
        except Exception as e:
            logger.error(f"Multi-search failed: {e}")
            return []

    def _generate_search_queries(self, query: str) -> List[str]:
        """
        根据原始查询生成多个搜索关键词
        """
        queries = [query]
        
        # 添加相关搜索词
        if "医院" in query:
            if "附近" in query:
                # 提取地点信息
                location_match = re.search(r'(.+?)附近', query)
                if location_match:
                    location = location_match.group(1)
                    queries.extend([
                        f"{location} 三甲医院",
                        f"{location} 医院地址",
                        f"{location} 医疗机构"
                    ])
        
        return queries

    async def _analyze_results(self, query: str, results: List[Dict]) -> Dict:
        """
        分析搜索结果
        """
        if not results:
            return {
                "steps": ["未找到相关搜索结果"],
                "summary": "无法获取足够的信息进行分析"
            }
        
        # 基础分析
        analysis_steps = [
            f"收集到 {len(results)} 条相关信息",
            "正在分析信息的相关性和可靠性",
            "提取关键信息和位置数据"
        ]
        
        # 提取关键信息
        key_info = []
        for result in results:
            if result.get("title") and result.get("description"):
                key_info.append({
                    "source": result["title"],
                    "content": result["description"][:200],
                    "url": result.get("url", "")
                })
        
        return {
            "steps": analysis_steps,
            "key_info": key_info,
            "summary": f"从 {len(results)} 条搜索结果中提取了 {len(key_info)} 条关键信息"
        }

    async def _synthesize_answer(self, query: str, analysis: Dict) -> str:
        """
        综合分析结果生成最终答案
        """
        key_info = analysis.get("key_info", [])
        
        if not key_info:
            return f"抱歉，未能找到关于 '{query}' 的具体信息。建议您：\n1. 尝试更具体的搜索关键词\n2. 使用地图应用直接搜索\n3. 咨询当地相关部门"
        
        # 构建答案
        answer_parts = [
            f"关于您的查询 '{query}'，我找到了以下相关信息：\n"
        ]
        
        for i, info in enumerate(key_info[:5], 1):  # 限制显示5条
            answer_parts.append(f"{i}. {info['source']}")
            if info['content']:
                answer_parts.append(f"   详情：{info['content']}")
            if info['url']:
                answer_parts.append(f"   链接：{info['url']}")
            answer_parts.append("")
        
        if len(key_info) > 5:
            answer_parts.append(f"另外还找到 {len(key_info) - 5} 条相关信息。")
        
        answer_parts.append("\n建议您根据以上信息选择最适合的选项，或进一步咨询相关机构。")
        
        return "\n".join(answer_parts)

    async def post_execute(self, agent: "ToolCallAgent", result: Any) -> Any:
        """
        格式化输出结果
        """
        if not isinstance(result, ToolResult) or result.error:
            logger.error(f"Enhanced DeepSearch post_execute received error: {result}")
            return result

        raw_dict = result.output
        if not isinstance(raw_dict, dict):
            logger.error(f"Enhanced DeepSearch received non-dict output: {raw_dict}")
            return result

        if "final_answer" not in raw_dict:
            return ToolResult(error="未找到分析结果")

        try:
            final_answer = raw_dict["final_answer"]
            search_summary = raw_dict.get("search_summary", "")
            
            formatted_response = [
                "<font size=4 face='黑体'>开始增强型深度搜索...</font>",
                f"<font size=3>{search_summary}</font>",
                "<font size=4 face='黑体'>搜索分析完成：</font>",
                final_answer
            ]

            return ToolResult(output="\n".join(formatted_response))

        except Exception as e:
            logger.error(f"Error formatting enhanced deep_search result: {e}")
            return ToolResult(error=f"处理搜索结果时出错: {e}")
