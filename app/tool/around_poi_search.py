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

class AroundPOISearch(BaseTool):
    name: str = "around_poi_search"
    description: str = """Search for Points of Interest (POIs) around a specific location.
    This tool helps find nearby places based on geographical coordinates."""
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "lng": {
                "type": "string",
                "description": "(required) Longitude coordinate for location-based search.",
            },
            "lat": {
                "type": "string",
                "description": "(required) Latitude coordinate for location-based search.",
            },
            "query": {
                "type": "string",
                "description": "(optional) Keyword to search for specific POIs.",
                "default": "",
            },
            "max_distance": {
                "type": "string",
                "description": "(optional) Search radius in meters from the specified coordinates.",
                "default": "1000",
            },
        },
        "required": ["lng", "lat"],
    }
    
    _API_URL = "http://100.69.239.221:8000/map/mapapi/textsearch"
    
    async def execute(
        self,
        lng: str,
        lat: str,
        query: str = "",
        max_distance: str = "1000"
    ) -> Dict:
        """
        Execute a POI search and return nearby points of interest.
        
        Args:
            lng (str): Longitude coordinate.
            lat (str): Latitude coordinate.
            query (str, optional): Keyword to search for specific POIs. Default is empty string.
            max_distance (str, optional): Search radius in meters. Default is "1000".
            
        Returns:
            Dict: The POI search results.
        """
        # 验证经纬度
        try:
            float_lng = float(lng)
            float_lat = float(lat)
            
            if float_lng < -180 or float_lng > 180:
                raise ValueError(f"Invalid longitude: {lng}. Must be between -180 and 180.")
                
            if float_lat < -90 or float_lat > 90:
                raise ValueError(f"Invalid latitude: {lat}. Must be between -90 and 90.")
                
        except ValueError as e:
            if "could not convert string to float" in str(e):
                raise ValueError(f"Invalid coordinates format. Longitude and latitude must be numeric values.")
            raise e
        
        # 构建请求参数
        params = {
            "acc_key": "5U2SX-78P0M-AMG9U-E15PE-NJTBX-I7K3R",
            "app_id": "bundleId",
            "app_version": "111.111.111",
            "caller_id": "llab_asst",
            "coordinate_type": "gcj02",
            "extend": json.dumps({"online_uniq": 0}),
            "is_around": 1,
            "lang": "zh-CN",
            "map_type": "tmap",
            "max_distance": max_distance,
            "need_distance": 1,
            "place_type": 900,
            "platform": 3,
            "product_id": 91001,
            "query": query,
            "requester_type": "inner.largefix",
            "select_lat": lat,
            "select_lng": lng,
            "user_id": "00016205419",
            "user_loc_lat": lat,
            "user_loc_lng": lng
        }
        
        logger.info(f"Searching POIs at coordinates ({lng}, {lat}) with query: {query}")
        
        try:
            result = await self._send_request(self._API_URL, params)
            if result["errno"] == 0:
                res = []
                for poi in result["result"]:
                    res.append(poi["base_info"])
                return res
            else:
                return "没有找到周边poi"


            #return self._process_poi_data(result)
        except Exception as e:
            logger.error(f"POI search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for POIs: {str(e)}",
                "data": None
            }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _send_request(self, url: str, params: Dict) -> Dict:
        """
        Send a request to the POI API with retries.
        
        Args:
            url (str): The API endpoint URL.
            params (Dict): The request parameters.
            
        Returns:
            Dict: The API response.
        """
        timeout = aiohttp.ClientTimeout(total=30)  # 设置30秒超时
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.debug(f"Sending request to {url} with params: {json.dumps(params)}")
                
                async with session.get(url, params=params) as response:
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
    
    def _process_poi_data(self, response_data: Dict) -> Dict:
        """
        Process the POI data from the API response.
        
        Args:
            response_data (Dict): The API response data.
            
        Returns:
            Dict: The processed POI data.
        """
        try:
            if not isinstance(response_data, dict):
                raise Exception("Invalid response format: not a dictionary")
            
            # 检查API响应状态
            if "status" in response_data and response_data["status"] != 0:
                error_msg = response_data.get("message", "Unknown error")
                raise Exception(f"API returned error: {error_msg}")
            
            # 提取POI数据
            poi_list = response_data.get("data", {}).get("pois", [])
            
            # 处理数据为更友好的格式
            processed_pois = []
            for poi in poi_list:
                processed_poi = {
                    "name": poi.get("name", ""),
                    "address": poi.get("address", ""),
                    "type": poi.get("type", ""),
                    "distance": poi.get("distance", ""),
                    "longitude": poi.get("longitude", ""),
                    "latitude": poi.get("latitude", ""),
                    "phone": poi.get("phone", "")
                }
                processed_pois.append(processed_poi)
            
            return {
                "status": "success",
                "message": f"Found {len(processed_pois)} POIs",
                "data": processed_pois
            }
            
        except Exception as e:
            logger.error(f"Error processing POI data: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to process POI data: {str(e)}",
                "data": None
            }
