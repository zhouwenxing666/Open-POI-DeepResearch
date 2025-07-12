import json
import logging
import random
import subprocess
import time
from typing import Any, Dict, List, Optional

import aiohttp
from tenacity import (after_log, before_log, retry, stop_after_attempt,
                      wait_exponential)

from app.tool.base import BaseTool

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


class RoutePlanner(BaseTool):
    name: str = "route_planner"
    description: str = """Plan a route between two locations using geographic coordinates (latitude/longitude) and get distance, time, and navigation information.
    This tool helps find optimal routes with various preferences like time priority or avoiding traffic jams. If user requests information about places along the route, set need_geo to True."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "start_lat": {
                "type": "number",
                "description": "(required) Latitude of the starting location."
            },
            "start_lng": {
                "type": "number",
                "description": "(required) Longitude of the starting location."
            },
            "start_name": {
                "type": "string",
                "description": "(required) Name of the starting location. Defaults to 'Start Point'."
            },
            "end_lat": {
                "type": "number",
                "description": "(required) Latitude of the destination location."
            },
            "end_lng": {
                "type": "number",
                "description": "(required) Longitude of the destination location."
            },
            "end_name": {
                "type": "string",
                "description": "(required) Name of the destination location. Defaults to 'End Point'."
            },
            "start_city_id": {
                "type": "integer",
                "description": "(optional) City ID for the starting location. Defaults to 6."
            },
            "end_city_id": {
                "type": "integer",
                "description": "(optional) City ID for the destination location. Defaults to 6."
            },
            "preference": {
                "type": "string",
                "description": "Route preference (时间优先, 躲避拥堵, 少附加费, 高速优先, or leave empty for auto recommendation)."
            },
            "via_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "lat": {
                            "type": "number",
                            "description": "(required) Latitude of the waypoint location."
                        },
                        "lng": {
                            "type": "number",
                            "description": "(required) Longitude of the waypoint location."
                        },
                        "name": {
                            "type": "string",
                            "description": "(optional) Name of the waypoint location. Defaults to 'Via Point N'."
                        }
                    },
                    "required": ["lat", "lng"]
                },
                "description": "List of waypoints (each with lat, lng, and optional name) to include in the route (optional)."
            },
            "departure_time": {
                "type": "string",
                "description": "Planned departure time (optional)."
            },
            "order_type": {
                "type": "integer",
                "description": "Order type, 0 for real-time, 1 for managed order (optional, defaults to 0)."
            },
            #"need_geo": {
            #    "type": "boolean",
            #    "description": "(required) Whether to include geographic information about locations along the route. Set to True when user explicitly requests information about places along the route, otherwise set to False."
            #}
        },
        "required": ["start_lat", "start_lng", "end_lat", "end_lng", "start_name", "end_name"]
    }

    def __init__(self):
        super().__init__()

    def get_api_url(self, sid: Optional[str] = None) -> str:
        """获取路线规划API的URL"""
        base_url = "http://llab-asst-pre-hna.xiaojukeji.com/2025/api/v1/tools"
        return base_url

    def validate_coordinates(self, lat: float, lng: float) -> tuple:
        """验证坐标有效性"""
        try:
            lat = float(lat)
            lng = float(lng)
            # 检查纬度范围
            if not (-90 <= lat <= 90):
                raise ValueError(f"Invalid latitude: {lat}")
            # 检查经度范围
            if not (-180 <= lng <= 180):
                raise ValueError(f"Invalid longitude: {lng}")
            return lat, lng
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid coordinate format: {e}")

    async def execute(self, start_lat: float, start_lng: float,
                     end_lat: float, end_lng: float,
                     start_name: str,
                     end_name: str,
                     #need_geo: bool,
                     start_city_id: int = 6,
                     end_city_id: int = 6,
                     preference: str = "",
                     via_points: Optional[List[Dict]] = None,
                     departure_time: Optional[str] = None,
                     order_type: int = 0) -> Dict:
        """
        Execute a route planning request using coordinates and return detailed information.

        Args:
            start_lat (float): Latitude of the starting location.
            start_lng (float): Longitude of the starting location.
            end_lat (float): Latitude of the destination location.
            end_lng (float): Longitude of the destination location.
            start_name (str): Name of the starting location.
            end_name (str): Name of the destination location.
            need_geo (bool): Whether to include geographic information about locations along the route.
            start_city_id (int, optional): City ID for the starting location. Defaults to 6.
            end_city_id (int, optional): City ID for the destination location. Defaults to 6.
            preference (str, optional): Route preference.
            via_points (List[Dict], optional): List of waypoints (each dict with 'lat', 'lng', optional 'name').
            departure_time (str, optional): Planned departure time.
            order_type (int, optional): Order type (0 for real-time, 1 for managed order). Defaults to 0.

        Returns:
            Dict: The route planning results with detailed information.
        """
        # 验证必需参数
        need_geo = True
        if not all(param is not None for param in [start_lat, start_lng, end_lat, end_lng, start_name, end_name]):
            return {
                "status": "error",
                "message": "Missing required parameters",
                "data": None
            }

        # 验证坐标
        try:
            start_lat, start_lng = self.validate_coordinates(start_lat, start_lng)
            end_lat, end_lng = self.validate_coordinates(end_lat, end_lng)
        except ValueError as e:
            return {
                "status": "error",
                "message": f"Invalid coordinates: {str(e)}",
                "data": None
            }

        # 验证城市ID
        if not isinstance(start_city_id, int) or not isinstance(end_city_id, int):
            return {
                "status": "error",
                "message": "City IDs must be integers",
                "data": None
            }

        # 验证need_geo参数
        if not isinstance(need_geo, bool):
            return {
                "status": "error",
                "message": "need_geo must be a boolean value",
                "data": None
            }

        # 验证via_points
        if via_points:
            if not isinstance(via_points, list):
                return {
                    "status": "error",
                    "message": "via_points must be a list",
                    "data": None
                }

            for i, point in enumerate(via_points):
                if not isinstance(point, dict) or 'lat' not in point or 'lng' not in point:
                    return {
                        "status": "error",
                        "message": f"Invalid via_point at index {i}: must contain 'lat' and 'lng'",
                        "data": None
                    }
                try:
                    self.validate_coordinates(point['lat'], point['lng'])
                except ValueError as e:
                    return {
                        "status": "error",
                        "message": f"Invalid coordinates in via_point {i}: {str(e)}",
                        "data": None
                    }

        actual_start_name = start_name if start_name is not None else "Start Point"
        actual_end_name = end_name if end_name is not None else "End Point"

        logger.info(f"Planning route from {actual_start_name} ({start_lat},{start_lng}) to {actual_end_name} ({end_lat},{end_lng}) with NeedGeo={need_geo}")

        try:
            # 调用路线规划方法
            result, route_tip, error = await self._plan_route(
                start_lat, start_lng, end_lat, end_lng,
                start_city_id, end_city_id,
                preference, via_points, departure_time, order_type, need_geo
            )

            if error or not result:
                return {
                    "status": "error",
                    "message": f"Failed to plan route: {error.get('error', 'Unknown error') if error else 'No result'}",
                    "data": None
                }

            return {
                "status": "success",
                "route_preference": route_tip,
                "data": result
            }
        except Exception as e:
            logger.error(f"Route planning failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to plan route: {str(e)}",
                "data": None
            }

    # post_execute 方法执行在execute之后
    async def post_execute(self, agent: "ToolCallAgent", result: Any) -> Any:
        """
        After executing RoutePlanner, save the geo_points of each route to the agent's state.
        """
        # 注意: 这里的 result 是原始的工具执行结果
        if isinstance(result, dict) and result.get('status') == 'success':
            data = result.get("data", {})
            routes = data.get('routes', [])

            # 从 agent 状态中获取当前的工具调用信息
            current_tool_call = agent.tool_calls[-1]
            try:
                args = json.loads(current_tool_call.function.arguments)
                prefix = f"{args['start_lng']}_{args['start_lat']}_{args['end_lng']}_{args['end_lat']}"

                for r in routes:
                    route_id = r.get('route_id')
                    if route_id and "geo_points" in r:
                        key = f"{prefix}_{route_id}"
                        agent.route_points[key] = r["geo_points"]
                        del r["geo_points"]
                        logger.info(f"Saved geo_points for route {key} to agent state.")
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.warning(f"Could not extract args to save geo_points: {e}")

        return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _plan_route(self, start_lat: float, start_lng: float,
                         end_lat: float, end_lng: float,
                         start_city_id: int, end_city_id: int,
                         preference: str,
                         via_points: Optional[List[Dict]] = None,
                         departure_time: Optional[str] = None,
                         order_type: int = 0,
                         need_geo: bool = False) -> tuple:
        """
        Internal method to perform the route planning with retry capability.

        Args:
            start_lat (float): Starting latitude
            start_lng (float): Starting longitude
            end_lat (float): Destination latitude
            end_lng (float): Destination longitude
            start_city_id (int): Starting city ID
            end_city_id (int): Destination city ID
            preference (str): Route preference
            via_points (List[Dict], optional): List of waypoints
            departure_time (str, optional): Planned departure time
            order_type (int): Order type
            need_geo (bool): Whether to include geographic information

        Returns:
            tuple: (response_data, route_tip, error_dict_or_None)
        """
        sid = get_sid()
        uid = "299074167251767"
        trace_id = "business-trip-agent"

        if via_points is None:
            via_points = []
        if departure_time is None:
            departure_time = ''

        # 构建偏好设置 - 注意这里使用的是 "Perfer" (拼写错误但与API保持一致)
        prefer = {
            "RapidArrival": 1,
            "AutoRecommend": 1,
            "AvoidCharge": 1,
            "TimeFirst": 1,
            "HighwayFirst": 1,
            "AvoidJam": 1,
            "AvoidRestrict": 1
        }
        route_tip = '自动推荐'

        # 根据偏好调整设置
        if '时间优先' in preference:
            prefer = {"RapidArrival": 1, "AutoRecommend": 0, "AvoidCharge": 0, "TimeFirst": 1, "HighwayFirst": 0, "AvoidJam": 0, "AvoidRestrict": 0}
            route_tip = '时间优先'
        elif '躲避拥堵' in preference:
            prefer = {"RapidArrival": 0, "AutoRecommend": 0, "AvoidCharge": 0, "TimeFirst": 0, "HighwayFirst": 0, "AvoidJam": 1, "AvoidRestrict": 0}
            route_tip = '躲避拥堵'
        elif '少附加费' in preference:
            prefer = {"RapidArrival": 0, "AutoRecommend": 0, "AvoidCharge": 1, "TimeFirst": 0, "HighwayFirst": 0, "AvoidJam": 0, "AvoidRestrict": 0}
            route_tip = '少附加费'
        elif '高速优先' in preference:
            prefer = {"RapidArrival": 0, "AutoRecommend": 0, "AvoidCharge": 0, "TimeFirst": 0, "HighwayFirst": 1, "AvoidJam": 0, "AvoidRestrict": 0}
            route_tip = '高速优先'

        # 构建请求参数 - 匹配新的API格式
        param = {
            "tool_id": 1006,
            "tool_name": "tool_get_route_info",
            "trace_id": trace_id,
            "session_id": sid,
            "uid": uid,
            "data": {
                "SrcLat": float(start_lat),
                "SrcLng": float(start_lng),
                "DstLat": float(end_lat),
                "DstLng": float(end_lng),
                "SrcCityId": int(start_city_id),
                "DstCityId": int(end_city_id),
                "NeedGeo": need_geo,
                "Perfer": prefer  # 注意这里是 "Perfer" 不是 "Prefer"
            }
        }

        # 添加可选参数
        if via_points:
            # 构建途经点列表
            pass_point_list = []
            for point in via_points:
                pass_point_list.append({
                    'lat': float(point['lat']),
                    'lng': float(point['lng'])
                })
            param["data"]["PassPointList"] = pass_point_list

        if departure_time:
            param["data"]["DepartureTime"] = departure_time

        if order_type:
            param["data"]["OrderType"] = order_type

        try:
            headers = {
                "Access": "nsgdsbzdb-_-!",  # 注意这里是 "Access" 不是 "access"
                "Content-Type": "application/json",
                "Didi-Header-Rid": trace_id,  # 注意大小写
            }

            response_data = await self._send_api_request(self.get_api_url(sid), param, headers)
            logger.info(f"Route planning API response: {json.dumps(response_data, ensure_ascii=False, indent=2)}")

            if not response_data:
                error_msg = "Empty API response"
                logger.error(error_msg)
                return None, route_tip, {"error": error_msg}

            # 检查API错误
            if response_data.get("errno") != 0:
                error_message = response_data.get("errmsg", f"API returned errno: {response_data.get('errno')}")
                logger.error(f"API error: {error_message}")
                return None, route_tip, {"error": error_message, "errno": response_data.get("errno")}

            # 解析响应数据
            if 'data' not in response_data:
                error_msg = "Invalid API response structure: missing 'data' field"
                logger.error(error_msg)
                return None, route_tip, {"error": error_msg, "details": response_data}

            # 格式化响应数据
            formatted_data = self._format_response(response_data['data'])
            return formatted_data, route_tip, None

        except Exception as e:
            logger.error(f"API request during _plan_route failed: {str(e)}", exc_info=True)
            return None, route_tip, {"error": str(e)}

    def _format_response(self, data: Dict) -> Dict:
        """格式化API响应数据"""
        try:
            formatted_data = {
                "routes": [],
                #"estimate_info": data.get("resp", {}).get("estimateInfo", {}),
                #"raw_result": data.get("result", [])
            }

            # 处理路线结果
            #route_id_dict = dict()
            if "result" in data and isinstance(data["result"], list):


                for route_data in data["result"]:
                    #print("ttf_debug:", route_data)
                    route_info = {
                        "route_id": str(route_data.get("route_id", "")),
                        "路线标签": route_data.get("labal", ""),  # 注意API返回的是 "labal" 不是 "label"
                        "路线距离": f"{round(route_data.get('dist', 0) / 1000, 2)}公里",  # 米转公里，保留两位小数并加上单位
                        "预估时间": f"{round(route_data.get('duration', 0) / 60, 2)}分钟",  # 秒转分钟，保留两位小数并加上单位
                        "geo_points": route_data.get("geo", [])
                    }
                    #print("ttf_debug_routes:", route_info)
                    formatted_data["routes"].append(route_info)
#                    if "route_id" in route_data:
#                        route_id_dict[route_data["route_id"]] =  route_data.get("geo", [])
#
            """
            # 处理estimate info
            if "resp" in data and "estimateInfo" in data["resp"]:
                estimate_info = data["resp"]["estimateInfo"]
                print("ttf_debug:", estimate_info)
                if "route" in estimate_info:
                    formatted_data["estimate_routes"] = []
                    for route in estimate_info["route"]:
                        route_features = route.get("rf", {})
                        motorwayCharge = 0
                        trafficLightNum = 0
                        for key, val in route_features.items():
                            if key == "motorwayCharge":
                                motorwayCharge = val
                            elif key == "trafficLightNum":
                                trafficLightNum = val


                        route_id = str(route.get("routeID", ""))
                        estimate_route = {
                            "route_id": str(route.get("routeID", "")),
                            "route_label": route.get("routeLabel", ""),
                            "预估时间": f"{route.get('ETASec', 0)/60.0}分钟",
                            "路线距离": f"{route.get('EDAMeter', 0) /1000}公里",
                            "红绿灯数量": trafficLightNum,
                            "高速费":motorwayCharge,
                            "geo_points": route.get("geo", [])
                        }
                        formatted_data["routes"].append(estimate_route)
                """

            return formatted_data

        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return {"error": f"Failed to format response: {str(e)}", "raw_data": data}

    async def _send_api_request(self, url: str, payload: Dict, headers: Dict) -> Dict:
        """Send a request to the route planning API"""
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.debug(f"Sending POST request to {url} with payload: {json.dumps(payload, ensure_ascii=False)}")
            logger.debug(f"Headers: {headers}")

            async with session.post(url, headers=headers, json=payload) as response:
                status_code = response.status
                response_text = await response.text()

                if status_code != 200:
                    logger.error(f"API request failed with status {status_code}: {response_text}")
                    raise Exception(f"API request failed with status {status_code}: {response_text}")

                try:
                    return json.loads(response_text)
                except json.JSONDecodeError as jde:
                    logger.error(f"Failed to decode JSON response: {response_text}", exc_info=True)
                    raise Exception(f"Invalid JSON response from API: {str(jde)}")

# Example usage
async def main():
    # Configure logging for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    planner = RoutePlanner()

    # Test case: Basic route
    print("\n--- Test Case: Basic Route ---")
    result = await planner.execute(
        start_lat=30.50683, start_lng=114.24195,
        end_lat=30.607393, end_lng=114.424505,
        start_name="起点", end_name="终点",
        start_city_id=6, end_city_id=6,
        need_geo=True
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
