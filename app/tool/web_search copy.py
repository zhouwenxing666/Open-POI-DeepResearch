import asyncio
import json
from typing import Dict, List, Optional, Union
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log

from app.config import config
from app.tool.base import BaseTool

# 设置日志记录器
logger = logging.getLogger(__name__)

class WebSearch(BaseTool):
    name: str = "web_search"
    description: str = """Search for information using keywords.
    This tool helps find relevant travel articles, guides, and information from the web."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "(required) The search keyword or phrase for travel information.",
            },
            "source": {
                "type": "string",
                "description": "(optional) The source to search from. Default is 'bocha'.",
                "default": "bocha",
            },
            "using_firecrawl": {
                "type": "boolean",
                "description": "(optional) Whether to use firecrawl for search. Default is false.",
                "default": False,
            },
            "page_size": {
                "type": "integer",
                "description": "(optional) Number of results per page. Default is 10.",
                "default": 10,
            },
            "page_num": {
                "type": "integer",
                "description": "(optional) Page number to retrieve. Default is 0.",
                "default": 0,
            }
        },
        "required": ["keyword"],
    }

    _API_URL = "http://ainlp.intra.xiaojukeji.com/search-engine/search"

    async def execute(
        self,
        keyword: str,
        source: str = "bocha",
        using_firecrawl: bool = False,
        page_size: int = 10,
        page_num: int = 0
    ) -> Dict:
        """
        Execute a travel information search and return relevant results.

        Args:
            keyword (str): The search keyword or phrase for travel information.
            source (str, optional): The source to search from. Default is 'bocha'.
            using_firecrawl (bool, optional): Whether to use firecrawl for search. Default is False.
            page_size (int, optional): Number of results per page. Default is 10.
            page_num (int, optional): Page number to retrieve. Default is 0.

        Returns:
            Dict: The travel information search results.
        """
        # 验证关键词不为空
        if not keyword.strip():
            raise ValueError("Search keyword cannot be empty")

        # 构建请求负载
        payload = {
            "keyword": keyword,
            "source": source,
            "using_firecrawl": using_firecrawl,
            "page_size": page_size,
            "page_num": page_num
        }

        logger.info(f"Searching travel information for keyword: '{keyword}', source: {source}, page: {page_num}")

        try:
            result = await self._send_request(self._API_URL, payload)

            # 处理搜索结果
            #if "errmsg" in result and result["errmsg"] != "SUCCESS":
            #    return {"status": "error", "message": result["errmsg"]}

            # 格式化搜索结果
            #formatted_results = self._format_search_results(result)
            #return formatted_results
            return result

        except Exception as e:
            logger.error(f"Travel information search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for travel information: {str(e)}",
                "data": None
            }

    def _format_search_results(self, result: Dict) -> Dict:
        """
        Format the search results for display.

        Args:
            result (Dict): The raw API response.

        Returns:
            Dict: Formatted search results.
        """
        try:
            if "data" not in result or not result["data"]:
                return {"status": "success", "message": "No results found", "results": []}

            search_data = result.get("data", {})
            search_results = search_data.get("results", [])

            formatted_results = []
            for item in search_results:
                formatted_item = {
                    "title": item.get("title", "No title"),
                    "content": item.get("content", "No content"),
                    "url": item.get("url", ""),
                    "source": item.get("source", ""),
                    "time": item.get("time", "")
                }
                formatted_results.append(formatted_item)

            return {
                "status": "success",
                "total_results": search_data.get("total", 0),
                "results": formatted_results
            }
        except Exception as e:
            logger.error(f"Error formatting search results: {str(e)}")
            return {"status": "error", "message": f"Error formatting results: {str(e)}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _send_request(self, url: str, payload: Dict) -> Dict:
        """
        Send a request to the search API with retries.

        Args:
            url (str): The API endpoint URL.
            payload (Dict): The request payload.

        Returns:
            Dict: The API response.
        """
        headers = {"Content-Type": "application/json"}
        timeout = aiohttp.ClientTimeout(total=5)  # 设置30秒超时

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.debug(f"Sending request to {url} with payload: {json.dumps(payload)}")

                async with session.post(url, headers=headers, json=payload) as response:
                    status_code = response.status
                    content_type = response.headers.get('Content-Type', '')

                    logger.debug(f"Received response with status {status_code} and content-type {content_type}")

                    # 检查状态码
                    if status_code != 200:
                        response_text = await response.text()
                        logger.error(f"API request failed with status {status_code}. Response: {response_text[:500]}")
                        raise Exception(f"API request failed with status {status_code}. Response: {response_text[:200]}...")

                    # 检查内容类型
                    if 'application/json' not in content_type:
                        response_text = await response.text()
                        logger.error(f"API returned non-JSON response. Content-Type: {content_type}. Response: {response_text[:500]}")

                        # 尝试解析为JSON，即使Content-Type不是application/json
                        try:
                            return json.loads(response_text)
                        except json.JSONDecodeError:
                            raise Exception(f"API returned non-JSON response. Content-Type: {content_type}. Response: {response_text[:200]}...")

                    # 正常JSON解析
                    try:
                        result = await response.json()
                        return result
                    except aiohttp.ContentTypeError as e:
                        response_text = await response.text()
                        logger.error(f"ContentTypeError while parsing JSON. Response: {response_text[:500]}")
                        raise Exception(f"Failed to parse JSON response: {str(e)}. Response text: {response_text[:200]}...")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {str(e)}")
            raise Exception(f"HTTP request failed: {str(e)}")
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            raise Exception("Request timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Unexpected error during API request: {str(e)}")
            raise Exception(f"Unexpected error: {str(e)}")

    def _validate_response(self, response_data: Dict) -> Dict:
        """
        Validate the response data structure.

        Args:
            response_data (Dict): The API response data.

        Returns:
            Dict: The validated response data.

        Raises:
            Exception: If the response data is invalid.
        """
        if not isinstance(response_data, dict):
            raise Exception("Invalid response: not a dictionary")

        if "errmsg" in response_data and response_data["errmsg"] != "SUCCESS":
            error_msg = response_data.get("errmsg", "Unknown error")
            raise Exception(f"API returned error: {error_msg}")

        return response_data
