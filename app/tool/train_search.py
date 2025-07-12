import asyncio
import json
from typing import Dict, List, Optional, Union
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log

from app.config import config
from app.tool.base import BaseTool
import app.tool.train_data_process as train_data_process

# 设置日志记录器
logger = logging.getLogger(__name__)

class TrainSearch(BaseTool):
    name: str = "train_search"
    description: str = """Search for train tickets between stations on a specific date.
    This tool helps find available train options with customizable filters for train types and departure times."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "depart_station": {
                "type": "string",
                "description": "(required) The name of the departure station.",
            },
            "arrive_station": {
                "type": "string",
                "description": "(required) The name of the arrival station.",
            },
            "depart_date": {
                "type": "string",
                "description": "(required) Departure date in format YYYY-MM-DD.",
            },
            "filter_train_type": {
                "type": "array",
                "items": {"type": "string"},
                "description": "(optional) List of train types to filter by (G, D, T, K, Z).",
                "default": ["G", "D", "T", "K", "Z"],
            },
            "depart_time_earliest": {
                "type": "string",
                "description": "(optional) Earliest departure time in format HH:MM.",
                "default": "",
            },
            "depart_time_latest": {
                "type": "string",
                "description": "(optional) Latest departure time in format HH:MM.",
                "default": "",
            },
        },
        "required": ["depart_station", "arrive_station", "depart_date"],
    }
    
    _API_URL = "http://ainlp.intra.xiaojukeji.com/hotel-flight/train/search"

    async def execute(
        self,
        depart_station: str,
        arrive_station: str,
        depart_date: str,
        filter_train_type: List[str] = ["G", "D", "T", "K", "Z"],
        depart_time_earliest: str = "",
        depart_time_latest: str = ""
    ) -> Dict:
        """
        Execute a train ticket search and return available options.

        Args:
            depart_station (str): The name of the departure station.
            arrive_station (str): The name of the arrival station.
            depart_date (str): Departure date in format YYYY-MM-DD.
            filter_train_type (List[str], optional): List of train types to filter by. 
                Default is ["G", "D", "T", "K", "Z"].
            depart_time_earliest (str, optional): Earliest departure time in format HH:MM.
                Default is empty string.
            depart_time_latest (str, optional): Latest departure time in format HH:MM.
                Default is empty string.

        Returns:
            Dict: The train search results.
        """

        #depart_date = "2025-03-18"
        # 验证日期格式
        try:
            from datetime import datetime
            datetime.strptime(depart_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Incorrect date format. Please use YYYY-MM-DD format. Received: {depart_date}")
        
        # 验证时间格式
        if depart_time_earliest:
            try:
                datetime.strptime(depart_time_earliest, "%H:%M")
            except ValueError:
                raise ValueError(f"Incorrect time format. Please use HH:MM format. Received: {depart_time_earliest}")
        
        if depart_time_latest:
            try:
                datetime.strptime(depart_time_latest, "%H:%M")
            except ValueError:
                raise ValueError(f"Incorrect time format. Please use HH:MM format. Received: {depart_time_latest}")
        
        if depart_time_earliest.strip() == "":
            depart_time_earliest = "00:00"
        if depart_time_latest.strip() == "":
            depart_time_latest = "23:59"
        # 构建请求负载
        payload = {
            "depart_station": depart_station,
            "arrive_station": arrive_station,
            "depart_date": depart_date,
            "filter_train_type": filter_train_type,
            "depart_time_earliest": depart_time_earliest,
            "depart_time_latest": depart_time_latest
        }
        
        logger.info(f"Searching trains from {depart_station} to {arrive_station} on {depart_date}, {payload}")
        
        try:
            result = await self._send_request(self._API_URL, payload)
            trains_df = train_data_process.process_train_data(result.get("data", {}))


            #print("debug.....", result.get("data", {}))
            return train_data_process.df_to_text(trains_df)
        except Exception as e:
            logger.error(f"Train search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for trains: {str(e)}",
                "data": None
            }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _send_request(self, url: str, payload: Dict) -> Dict:
        """
        Send a request to the train API with retries.
        
        Args:
            url (str): The API endpoint URL.
            payload (Dict): The request payload.
            
        Returns:
            Dict: The API response.
        """
        headers = {"Content-Type": "application/json"}
        timeout = aiohttp.ClientTimeout(total=30)  # 设置30秒超时
        
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
        # 添加验证逻辑，确保响应包含预期的字段
        if not isinstance(response_data, dict):
            raise Exception("Invalid response: not a dictionary")
            
        # 示例验证，可根据实际API响应结构进行调整
        if "status" in response_data and response_data["status"] != "success":
            error_msg = response_data.get("message", "Unknown error")
            raise Exception(f"API returned error: {error_msg}")
            
        return response_data
