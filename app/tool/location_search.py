import json
import logging
import aiohttp
import time
import random
from typing import Dict, List, Any
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log

from app.config import config
from app.tool.base import BaseTool
import subprocess
import re

# 设置日志记录器
logger = logging.getLogger(__name__)

def get_sid():
    new_sess_cmd = "curl --location --request POST 'http://llab-asst-pre-hna.xiaojukeji.com/2025/w/sid/new/v1' \
        --header 'Content-Type: application/json' \
        --header 'token:  iuVXnPxtswrcoSnlpglvZGWv3KwksigsC8H-5jI_FUAczDlqxFAQhOG7_HEjqt9Kd-rcd_AiL8kzeJhIzN0HKSoofr6DJZK6aRPGctKNVUiXJGNV0mePmG2U3lTCWO36ZnhEHcbqJC-vGG8kGO9kidBss5Q5Zm_V-CSrsZMHt7_7_8dO6mF8XZS81Yv6JpHkRT5Gd4wfknN_z_4ZAAD__w==' \
        --header 'lng: 116.309057' \
        --header 'lat: 40.076859' \
        --header 'cityId: 1' \
        --header 'user_type: 1' \
        --header 'uid: 299074722767543'"

    while 1:
        try:
            new_sess_resp = subprocess.check_output(new_sess_cmd, shell=True)
            sid = json.loads(new_sess_resp).get('data').get('sid')
            print("get_sid:", sid)
            break
        except Exception as e:
            print("get_sid, error")
            print(e)
            time.sleep(0.2)
    return sid

class LocationSearch(BaseTool):
    name: str = "location_search"
    description: str = """Search for location details based on a query string.
    This tool helps find precise location information including coordinates, name, and address."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The location or place name to search for."
            },
            "city_name":{
                "type": "string",
                "description": "(required) The city name for the search, e.g., '北京','深圳','重庆'. Use the city name from the user's query if provided. If not, infer it from the conversation context or use the city from the 'CurrentLocation' tool's output."
            }
        },
        "required": ["query","city_name"],
    }

    def __init__(self):
        super().__init__()

    def get_api_url(self):
        """获取搜索API的URL"""
        #base_url = config.get_asst_engine_url()
        base_url = "http://llab-asst-pre-hna.xiaojukeji.com/2025/api/v1/tools/"
        return base_url

    # pre_execute 方法执行在execute之前 给city_name值进行处理，若带有“市”、“省”、“自治区”、“特别行政区”等后缀，则去掉
    async def pre_execute(self, agent: "ToolCallAgent", tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook to automatically add 'city_name' if it's missing.
        """
        city_name = tool_input.get("city_name")
        # 如果模型生成的city_name是"北京市"这类的，则去掉“市”，只保留城市名
        patterns_to_remove = "市|省|自治区|特别行政区"

        # 更新tool_input中的city_name
        if city_name and isinstance(city_name, str):
            # 去掉前后空格
            city_name = city_name.strip()
            # 去掉“市”、“省”、“自治区”、“特别行政区”等后缀
            city_name = re.sub(f"({patterns_to_remove})$", "", city_name)
            # 更新tool_input中的city_name
            tool_input["city_name"] = city_name

        # 如果模型没有生成city_name不存在或不是字符串类型，则尝试从当前位置信息中获取
        else:
            logger.info("City name not provided in tool_input. Attempting to get it from current location.")
            try:
                current_location_tool = CurrentLocation()
                location_data = await current_location_tool.execute()

                if location_data.get("status") == "success" and location_data["data"].get("city_name"):
                    new_city_name = location_data["data"]["city_name"]
                    new_city_name = remove_admin_suffix(new_city_name)

                    logger.info(f"Successfully determined current city: {new_city_name}")
                    # --- 修改输入的参数字典 ---
                    tool_input["city_name"] = new_city_name
                # 如果当前位置访问失败，则最后兜底使用北京市
                else:
                    logger.warning("Failed to get current location city. Defaulting to '北京'.")
                    tool_input["city_name"] = "北京"
            except Exception as e:
                logger.error(f"Error getting current location for city name: {e}. Defaulting to '北京'.")
                tool_input["city_name"] = "北京"
        # --- 返回修改后的参数字典 ---
        return tool_input

    async def execute(self, query: str, city_name: str) -> Dict:
        """
        Execute a location search and return detailed information.

        Args:
            query (str): The location or place name to search for.

        Returns:
            Dict: The location search results with detailed information.
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")
        logger.info(f"Searching location information for: {query}")

        try:
            result = await self._search_location(query, city_name)

            return {
                "status": "success",
                "data": result
            }
        except Exception as e:
            logger.error(f"Location search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for location: {str(e)}",
                "data": None
            }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _search_location(self, query: str, city_name: str) -> Dict:
        """
        Internal method to perform the location search with retry capability.

        Args:
            query (str): The location query.

        Returns:
            Dict: The raw API response with location details.
        """
        # 生成请求所需的唯一标识符
        sid = get_sid()
        uid = "299074722767543"
        trace_id = "t" + str(int(time.time() * 1000)) + str(random.randint(10000, 99999))
        param = {
            "tool_id": 1002,
            "tool_name": "tool_get_sug_list",
            "trace_id": trace_id,
            "session_id": sid,
            "uid": uid,
            "data": {
                "query": query,
                "isSearch": "1",  # 默认启用一步导航
                "placeType": 2,    # 默认为终点类型
                "cityName": city_name  #默认为大模型根据query生成的，若没有生成则为当前所在地city_name
            }
        }

        # 准备请求头
        try:
            #from app.config import config
            #import dependencies
            headers = {"content-type": "application/json", "access": "nsgdsbzdb-_-!",
                       "didi-header-rid": "trace-id",
                       "default-address":"addr"}
            #headers.update(dependencies.get_requests_header())
        except ImportError:
            # 如果无法导入依赖，使用基本请求头
            headers = {"content-type": "application/json"}

        try:
            # 发送API请求
            response = await self._send_api_request(self.get_api_url(), param, headers)
            #print("location_search:", response)

            if not response or 'data' not in response:
                raise Exception("Invalid API response structure")

            # 直接返回API响应中的数据部分
            pois = (response.get('data', {})).get("result",{})[:3]
            print("pois:", pois)
            return_pois = []
            for poi in pois:
                return_pois.append({
                    "name": poi["displayname"],
                    "address":poi["addressAll"],
                    "lng":poi["lng"],
                    "lat":poi["lat"],
                    "city_id":poi["city"],
                    "city_name": poi["city_name"],
                    "poi_id": poi["poi_id"]
                })

                if "sub_poi_list" in poi and poi["sub_poi_list"] is not None:
                    for sub_poi in poi["sub_poi_list"]:
                        return_pois.append({
                            "name": sub_poi["displayname"],
                            "address":sub_poi["addressAll"],
                            "lng":sub_poi["lng"],
                            "lat":sub_poi["lat"],
                            "city_id":sub_poi["city"],
                            "city_name": sub_poi["city_name"],
                            "poi_id": sub_poi["poi_id"]
                        })


            return return_pois

        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise Exception(f"Failed to get location suggestions: {str(e)}")

    async def _send_api_request(self, url: str, payload: Dict, headers: Dict) -> Dict:
        """Send a request to the location API"""
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.debug(f"Sending request to {url} with payload: {json.dumps(payload)}")

            async with session.post(url, headers=headers, json=payload) as response:
                status_code = response.status

                if status_code != 200:
                    response_text = await response.text()
                    print("ttf_debug:", response_text)
                    raise Exception(f"API request failed with status {status_code}: {response_text}...")

                return await response.json()
