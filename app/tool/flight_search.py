import asyncio
import json
from typing import Dict, List, Optional, Union
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log

from app.config import config
from app.tool.base import BaseTool
import app.tool.flight_data_process as flight_data_process

# 设置日志记录器
logger = logging.getLogger(__name__)

class FlightSearch(BaseTool):
    name: str = "flight_search"
    description: str = """Search for available flights between cities on a specific date.
    This tool helps find flight options with details like departure time, arrival time, and prices."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "departure_city_name": {
                "type": "string",
                "description": "(required) The name of the departure city.",
            },
            "arrival_city_name": {
                "type": "string",
                "description": "(required) The name of the arrival city.",
            },
            "date": {
                "type": "string",
                "description": "(required) Flight date in format YYYY-MM-DD hh:mm:ss.",
            },
            "search_type": {
                "type": "integer",
                "description": "(optional) Type of search to perform. Default is 0.",
                "default": 0,
            },
            "support_price_type": {
                "type": "integer",
                "description": "(optional) Price type filter. Default is 0.",
                "default": 0,
            },
            "support_rc_rule": {
                "type": "integer",
                "description": "(optional) Refund and change rule filter. Default is 0.",
                "default": 0,
            },
        },
        "required": ["departure_city_name", "arrival_city_name", "date"],
    }
    
    _API_URL = "http://ainlp.intra.xiaojukeji.com/hotel-flight/flight/search"

    async def execute(
        self,
        departure_city_name: str,
        arrival_city_name: str,
        date: str,
        search_type: int = 0,
        support_price_type: int = 0,
        support_rc_rule: int = 0
    ) -> Dict:
        """
        Execute a flight search and return available flights.

        Args:
            departure_city_name (str): The name of the departure city in chinese like "北京市", endswith "市".
            arrival_city_name (str): The name of the arrival city in chinese like "北京市",  endswith "市".
            date (str): Flight date in format YYYY-MM-DD hh:mm:ss.
            search_type (int, optional): Type of search to perform. Default is 0.
            support_price_type (int, optional): Price type filter. Default is 0.
            support_rc_rule (int, optional): Refund and change rule filter. Default is 0.

        Returns:
            Dict: The flight search results.
        """
        # 验证日期格式
        try:
            from datetime import datetime
            datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ValueError(f"Incorrect date format. Please use YYYY-MM-DD hh:mm:ss format. Received: {date}")
        
        # 构建请求负载
        #if not departure_city_name.endswith("市"):
        #    departure_city_name += "市"
        #
        #if not arrival_city_name.endswith("市"):
        #    arrival_city_name += "市"
        payload = {
            "departure_city_name": departure_city_name,
            "arrival_city_name": arrival_city_name,
            "date": date.split(" ")[0].strip(),
            "search_type": search_type,
            "support_price_type": support_price_type,
            "support_rc_rule": support_rc_rule
        }
        #payload["departure_city_name"] = "南京市"
        #payload["arrival_city_name"] = "北京市"
        #payload["date"] = "2025-03-18"
        
        
        logger.info(f"Searching flights from {departure_city_name} to {arrival_city_name} on {date}, {payload}")
        
        try:
            result = await self._send_request(self._API_URL, payload)
            flight_list = result.get("data",{}).get("flight_list", {})
            flights_df = flight_data_process.process_flight_data(flight_list)
            flights_str = flight_data_process.format_for_display_as_text(flights_df)
            print(flights_str)
            #print("debug all....", json.dumps(flight_list))

            #route_info = []
            #for flight in flight_list:
            #    route_list = flight.get("flight_info",{}).get("route_list", {})
            #    price_list = flight.get("price_list", {})
            #    for route, price in zip(route_list, price_list):
            #        pass
            return flights_str
            #return result
        except Exception as e:
            logger.error(f"Flight search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for flights: {str(e)}",
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
        Send a request to the flight API with retries.
        
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
