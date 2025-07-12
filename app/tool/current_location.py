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

class CurrentLocation(BaseTool):
    name: str = "current_location"
    description: str = """Retrieve the user's current location information.
    This tool provides details about where the user is currently located, including coordinates, address, and nearby points of interest."""
    parameters: dict = {
        "type": "object",
        "properties": {},  # No parameters needed as we're getting current location
        "required": [],
    }

    def __init__(self):
        super().__init__()

    def get_api_url(self):
        """获取定位API的URL"""
        #base_url = config.get_asst_engine_url()
        base_url = "https://llab-asst-pre-hna.xiaojukeji.com/2025/api/v1/tools/"
        return base_url

    async def execute(self) -> Dict:
        """
        Execute a location retrieval operation to get user's current location.

        Returns:
            Dict: The current location information with detailed data.
        """
        logger.info("Retrieving user's current location")

        try:
            result = await self._get_current_location()

            return {
                "status": "success",
                "data": result
            }
        except Exception as e:
            logger.error(f"Current location retrieval failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to retrieve current location: {str(e)}",
                "data": None
            }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _get_current_location(self) -> Dict:
        """
        Internal method to retrieve the current location with retry capability.

        Returns:
            Dict: The processed API response with location details.
        """
        # 生成请求所需的唯一标识符
        sid = get_sid()
        uid = "299074722767543"
        trace_id = "t" + str(int(time.time() * 1000)) + str(random.randint(10000, 99999))

        # 准备API请求参数
        param = {
            "tool_id": 1001,
            "tool_name": "tool_get_start_info",
            "trace_id": trace_id,
            "session_id": sid,
            "uid": uid,
            "data": {"RequestSourceType": "default"}
        }

        # 准备请求头
        try:
            #from app.config import config
            #import dependencies
            headers = {"content-type": "application/json", "access": "nsgdsbzdb-_-!",
                       "didi-header-rid": trace_id}
            #headers.update(dependencies.get_requests_header())
        except ImportError:
            # 如果无法导入依赖，使用基本请求头
            headers = {"content-type": "application/json"}

        try:
            # 发送API请求
            response = await self._send_api_request(self.get_api_url(), param, headers)
            print("response:", response)

            if not response or 'data' not in response:
                raise Exception("Invalid API response structure")

            # 处理API响应中的数据
            results = response.get('data', {})
            rec_start_points = results.get('rec_start_points')

            if rec_start_points is None or len(rec_start_points) == 0:
                rec_start_points = results.get('rgeo_result')

            if not rec_start_points or len(rec_start_points) == 0:
                raise Exception("No location information found")

            # 获取第一个推荐位置
            location = rec_start_points[0]
            location['city_id'] = location.get('city')

            # 构造返回数据结构
            return_location = {
                "name": location.get("name"),
                "address": location.get("address"),
                "lng": location.get("lng"),
                "lat": location.get("lat"),
                "city_id": location.get("city_id"),
                "city_name": location.get("city_name", ""),
                "poi_id": location.get("poi_id")
            }

            return return_location

        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise Exception(f"Failed to get current location: {str(e)}")

    async def _send_api_request(self, url: str, payload: Dict, headers: Dict) -> Dict:
        """Send a request to the location API"""
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.debug(f"Sending request to {url} with payload: {json.dumps(payload)}")

            async with session.post(url, headers=headers, json=payload) as response:
                status_code = response.status

                if status_code != 200:
                    response_text = await response.text()
                    raise Exception(f"API request failed with status {status_code}: {response_text}...")

                return await response.json()


async def get_current_location():
    current_list = []
    
    try:
        current_location = CurrentLocation()
        current = await current_location.execute()  # 添加 await

        data = current["data"]
        if data["name"] is not None:
            current_list.append("名称:" + data["name"])
        if data["address"]:
            current_list.append("地址:" + data["address"])

        if data["lng"] and data["lat"]:
            current_list.append("经度:" + str(data["lng"]))
            current_list.append("纬度:" + str(data["lat"]))

        if data["city_name"]:
            current_list.append("城市名称:" + data["city_name"])

        if data["city_id"]:
            current_list.append("城市ID:" + str(data["city_id"]))

        if current_list:
            current_list = ["当前位置："] + current_list
        current = "\n".join(current_list)
        print("current:", current)
        return current

    except Exception as e:
        print(f"获取位置失败: {e}")
        return None
