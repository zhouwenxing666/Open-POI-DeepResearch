import asyncio
import json
from typing import Dict, List, Optional, Union
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log

from app.config import config
from app.tool.base import BaseTool
import app.tool.hotel_data_process as hotel_data_process

# 设置日志记录器
logger = logging.getLogger(__name__)

class HotelSearch(BaseTool):
    name: str = "hotel_search"
    description: str = """Search for hotels based on location, date, and other criteria.
    This tool helps find available hotels in a specific city with customizable filters."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "city_name": {
                "type": "string",
                "description": "(required) The name of the city where you want to find hotels.",
            },
            "check_in_date": {
                "type": "string",
                "description": "(required) Check-in date in format YYYY-MM-DD.",
            },
            "check_out_date": {
                "type": "string",
                "description": "(required) Check-out date in format YYYY-MM-DD.",
            },
            "hotel_name": {
                "type": "string",
                "description": "(optional) Hotel name or location keyword to filter results.",
                "default": "",
            },
            "level_id": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "(optional) List of hotel star levels to filter by (1-5).",
                "default": [1, 2, 3, 4, 5],
            },
            "lng": {
                "type": "string",
                "description": "(optional) Longitude coordinate for location-based search.",
                "default": "",
            },
            "lat": {
                "type": "string",
                "description": "(optional) Latitude coordinate for location-based search.",
                "default": "",
            },
            "distance_range": {
                "type": "string",
                "description": "(optional) Search radius in meters from the specified coordinates.",
                "default": "10000",
            },
            "sort": {
                "type": "integer",
                "description": "(optional) Sort order for results (0: default sorting).",
                "default": 0,
            },
        },
        "required": ["city_name", "check_in_date", "check_out_date"],
    }
    
    _API_URL = "http://ainlp.intra.xiaojukeji.com/hotel-flight/hotel/search"

    async def execute(
        self,
        city_name: str,
        check_in_date: str,
        check_out_date: str,
        hotel_name: str = "",
        level_id: List[int] = [1, 2, 3, 4, 5],
        lng: str = "",
        lat: str = "",
        distance_range: str = "10000",
        sort: int = 0
    ) -> Dict:
        """
        Execute a hotel search and return available hotels.

        Args:
            city_name (str): The name of the city.
            check_in_date (str): Check-in date in format YYYY-MM-DD.
            check_out_date (str): Check-out date in format YYYY-MM-DD.
            hotel_name (str, optional): Hotel name or location keyword. Default is empty string.
            level_id (List[int], optional): List of hotel star levels. Default is [1, 2, 3, 4, 5].
            lng (str, optional): Longitude coordinate. Default is empty string.
            lat (str, optional): Latitude coordinate. Default is empty string.
            distance_range (str, optional): Search radius in meters. Default is "10000".
            sort (int, optional): Sort order for results. Default is 0.

        Returns:
            Dict: The hotel search results.
        """
        # 验证日期格式
        try:
            from datetime import datetime
            datetime.strptime(check_in_date, "%Y-%m-%d")
            datetime.strptime(check_out_date, "%Y-%m-%d")
            
            # 检查入住日期是否早于退房日期
            if datetime.strptime(check_in_date, "%Y-%m-%d") >= datetime.strptime(check_out_date, "%Y-%m-%d"):
                raise ValueError("Check-in date must be earlier than check-out date")
        except ValueError as e:
            raise ValueError(f"Date validation error: {str(e)}")
        
        # 验证level_id
        for level in level_id:
            if not isinstance(level, int) or level < 1 or level > 5:
                raise ValueError(f"Invalid hotel level: {level}. Must be an integer between 1 and 5.")
        
        if not city_name.endswith("市"):
            city_name += "市"
        # 构建请求负载
        payload = {
            "city_name": city_name,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "hotel_name": hotel_name,
            "level_id": level_id,
            "lng": lng,
            "lat": lat,
            "distance_range": distance_range,
            "sort": sort
        }
        
        logger.info(f"Searching hotels in {city_name} from {check_in_date} to {check_out_date}, {payload}")
        
        try:
            result = await self._send_request(self._API_URL, payload)
            hotel_list = result.get("data", {}).get("items", {})
            hotels_df = hotel_data_process.process_hotel_data(hotel_list)
            hotels_text = hotel_data_process.df_to_text(hotels_df)
            #print("debug...", result.get("data", {}).get("items", {}))
            return hotels_text
        except Exception as e:
            logger.error(f"Hotel search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for hotels: {str(e)}",
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
        Send a request to the hotel API with retries.
        
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
