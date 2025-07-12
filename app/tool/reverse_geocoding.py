import asyncio
import json
from typing import Dict, Optional
import aiohttp
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log
from app.config import config
from app.tool.base import BaseTool

# 设置日志记录器
logger = logging.getLogger(__name__)

class ReverseGeocoding(BaseTool):
    name: str = "reverse_geocoding"
    description: str = """Get location information based on geographical coordinates.
    This tool helps find address and location name from longitude and latitude coordinates."""

    parameters: dict = {
        "type": "object",
        "properties": {
            "lng": {
                "type": "string",
                "description": "(required) Longitude coordinate.",
            },
            "lat": {
                "type": "string",
                "description": "(required) Latitude coordinate.",
            },
        },
        "required": ["lng", "lat"],
    }

    _API_URL = "http://100.69.239.97:30603/mapapi/reversegeo"

    async def execute(
        self,
        lng: str,
        lat: str,
    ) -> Dict:
        """
        Execute a reverse geocoding request to get location information from coordinates.

        Args:
            lng (str): Longitude coordinate.
            lat (str): Latitude coordinate.

        Returns:
            Dict: The location information including address and name.
        """
        # 验证经纬度格式
        try:
            float_lng = float(lng)
            float_lat = float(lat)
            if float_lng < -180 or float_lng > 180:
                raise ValueError(f"Invalid longitude: {lng}. Must be between -180 and 180.")
            if float_lat < -90 or float_lat > 90:
                raise ValueError(f"Invalid latitude: {lat}. Must be between -90 and 90.")
        except ValueError as e:
            raise ValueError(f"Coordinate validation error: {str(e)}")

        # 构建请求参数
        params = {
            "access_key": "1",
            "product_id": "91001",
            "acc_key": "5U2SX-78P0M-AMG9U-E15PE-NJTBX-I7K3R",
            "app_version": "6.2.4.906231759",
            "platform": "1",
            "app_id": "bundleId",
            "map_type": "dmap",
            "coordinate_type": "gcj02",
            "requester_type": "101",
            "user_id": "1150110400881098757",
            "token": "_VM6PtAppgqw0q_2l0ISUf5q7oltXqCu3LSjyXrgxnIkzDtOxUAMRuG9nNqKfmfG48QtPXvgER7NIIGoIvaOcm99jr6TKYq2aBHGdMqNuVKrJBmzUZ6xZ6p1DWk1ZqeuFBQPjxhPFBjPVGyKniPGptHCjdcbeFAnP1-_3y8HpT_jjfLRI4d678Y7he9beiibJ8bHnfy89v8AAAD__w==",
            "lang": "zh-CN",
            "select_lng": lng,
            "select_lat": lat
        }

        logger.info(f"Getting location information for coordinates: lng={lng}, lat={lat}")

        try:
            result = await self._send_request(self._API_URL, params)
            if result["errno"] == 0:
                return result["rgeo_result"]
            else:
                return "没发现相关位置信息"
            #return result
            #location_info = self._process_location_data(result)
            #return location_info
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to get location information: {str(e)}",
                "data": None
            }

    def _process_location_data(self, response_data: Dict) -> Dict:
        """
        Process the location data from API response.

        Args:
            response_data (Dict): The API response data.

        Returns:
            Dict: Processed location information.
        """
        try:
            # 根据实际API响应结构进行调整
            data = response_data.get("data", {})
            result = {
                "status": "success",
                "address": data.get("address", ""),
                "name": data.get("name", ""),
                "district": data.get("district", ""),
                "city": data.get("city", ""),
                "province": data.get("province", ""),
                "poi_list": data.get("poi_list", [])
            }
            return result
        except Exception as e:
            logger.error(f"Error processing location data: {str(e)}")
            raise Exception(f"Failed to process location data: {str(e)}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _send_request(self, url: str, params: Dict) -> Dict:
        """
        Send a request to the reverse geocoding API with retries.

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
