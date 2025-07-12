import json
import logging
import aiohttp
import time
import random
import requests
from typing import Dict, List, Any
from tenacity import retry, stop_after_attempt, wait_exponential, before_log, after_log
from app.config import config
from app.tool.base import BaseTool
import subprocess

# 设置日志记录器
logger = logging.getLogger(__name__)

class LocationAroundSearch(BaseTool):
    name: str = "location_around_search"
    description: str = """Search for locations around a specific point based on coordinates and query string.
    This tool helps find nearby places matching the query within a specified distance."""

    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The keyword to search for nearby locations.",
            },
            "lng": {
                "type": "number",
                "description": "(required) Longitude of the center point for the search.",
            },
            "lat": {
                "type": "number",
                "description": "(required) Latitude of the center point for the search.",
            },
            "city_id": {
                "type": "string",
                "description": "(required) City ID for the search area.",
            },
            "max_distance": {
                "type": "number",
                "description": "(optional) Maximum distance in meters for the search radius. Default is 5000.",
            }
        },
        "required": ["query", "lng", "lat", "city_id"],
    }

    def __init__(self):
        super().__init__()
        poi_search_import = 'http://100.69.239.97:30970'

    def fmt_url_around(self, query, cityid, lng, lat, max_distance):
        """Format the URL for around location search"""
        base_url = '/poiservice/textsearch?access_key_id=1&acckey=HA1UC-TH0WZ-DXT1E-4CLUM-AJD4X-K8ESZ&along_route_geo_list=%5B%5D&api_version=1.0.4&appversion=7.0.8&assist=0&biz_strategy=&bus_search_type=&caller=map_default&caller_id=&canonical_country_code=CN&categories=&channel=102&city=&city_block_strategy_exp=1&city_desc=&cityid=13&county_id=370213&data_strategy=0&datatype=101&district_code=&dumpClickedPoiId=&dumpLoggedDisplayPoiIds=&dumpNegativePoiIds=&dump_mode=&extend=&extensions=&forbid_cross_city=0&from_lat=&from_lng=&high_relevance_filter=&if_version=1&imei=&is_around=0&is_debug=&is_district=&is_nation_search=&is_need_fold=0&is_need_tool_bar=0&is_res_polymerization=0&is_router_search=&is_search=&isnocache=&istest=&lang=zh-CN&lang_for_google=&lat=&limit=&lng=&mansearch=&maptype=soso&max_distance=0&need_category_code=0&need_distance=0&need_loading=&orderby=&ordertype=-1&passenger_id=&personal_switch_status=1&pid=116085726&plat=36.15044840494792&plng=120.4858412000868&productid=666&qtype=1&query=%E5%92%8C%E7%94%B0%E7%8E%89%E4%BA%A4%E6%98%93%E5%B8%82%E5%9C%BA&rankDebugFeature=&rankDebugFeatureValue=&rankDebugHowCanTheySwap=&rankDebugPoiid=&request_num=&risk_code=100000&route_end_lat=0&route_end_lng=0&route_id=&route_start_lat=0&route_start_lng=0&search_filter=&search_scene=&search_type=0&select_lat=36.15195148249511&select_lng=120.4331746314998&showRecallRes=&start_index=0&subpois=&token=3V4ruLD7PkZZ0KOkhNg0jAWteow1U0WPQzWvGM9GqsokzDmOwzAMQNG7_JowSEnUwnb6ucMsztIoQIJURu4e2Gk_Pt7GVIK86KII0wgTZiJMVVWYmbDmI1vuuY3qXZjlaJa81ZqE6QRf3wg_BAi_ROpWmutIbdTck_BPpCGsxMbj9rz_rYS-hNNulVy6HdaZwHqtVrx4d4TLx7zu-zsAAP__&token_flag=0&uid=281475092796382&user_id=116085726&version=&version_code='
        segs = base_url.split("&")
        new = []
        for s in segs:
            if 'query' in s:
                new.append(f'query={query}')
            elif 'cityid' in s:
                new.append(f'cityid={cityid}')
            elif 'lng' in s:
                pre, _ = s.split("=")
                new.append(f'{pre}={lng}')
            elif 'lat' in s:
                pre, _ = s.split('=')
                new.append(f'{pre}={lat}')
            elif 'max_distance' in s:
                pre, _ = s.split('=')
                new.append(f'{pre}={max_distance}')
            elif 'is_around' in s:
                new.append(f'is_around=1')
            else:
                new.append(s)
        return '&'.join(new)

    def fmt_sug_rsp(self, response):
        """Format the response from the POI search API"""
        try:
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return []

            data = response.json()
            if not data or 'status' not in data or data['status'] != 'OK':
                logger.error(f"Invalid API response: {data}")
                return []

            pois = data.get('pois', [])
            return_pois = []

            for poi in pois[:3]:  # Limit to top 3 results
                return_pois.append({
                    "name": poi.get("name", ""),
                    "address": poi.get("address", ""),
                    "lng": poi.get("lng", 0),
                    "lat": poi.get("lat", 0),
                    "city_id": poi.get("city_id", ""),
                    "city_name": poi.get("city_name", ""),
                    "poi_id": poi.get("id", ""),
                    "distance": poi.get("distance", 0)
                })

            return return_pois
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return []

    async def execute(self, query: str, lng: float, lat: float, city_id: str, max_distance: int = 5000) -> Dict:
        """
        Execute a location search around specified coordinates and return detailed information.

        Args:
            query (str): The keyword to search for nearby locations.
            lng (float): Longitude of the center point.
            lat (float): Latitude of the center point.
            city_id (str): City ID for the search.
            max_distance (int, optional): Maximum search radius in meters. Defaults to 5000.

        Returns:
            Dict: The nearby location search results with detailed information.
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            raise ValueError("Longitude and latitude must be numbers")

        if not city_id:
            raise ValueError("City ID must be provided")

        logger.info(f"Searching locations around coordinates ({lng}, {lat}) for query: {query}")

        try:
            result = await self._search_locations_around(query, city_id, lng, lat, max_distance)
            return {
                "status": "success",
                "data": result
            }
        except Exception as e:
            logger.error(f"Location around search failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to search for nearby locations: {str(e)}",
                "data": None
            }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO)
    )
    async def _search_locations_around(self, query: str, city_id: str, lng: float, lat: float, max_distance: int) -> List[Dict]:
        """
        Internal method to perform the around location search with retry capability.

        Args:
            query (str): The location query.
            city_id (str): City ID for the search.
            lng (float): Longitude of the center point.
            lat (float): Latitude of the center point.
            max_distance (int): Maximum search radius in meters.

        Returns:
            List[Dict]: List of nearby locations with details.
        """
        try:
            # Create the formatted URL for the around search
            poi_search_import = 'http://100.69.239.97:30970'
            formatted_url = self.fmt_url_around(query, city_id, lng, lat, max_distance)
            url = f'{poi_search_import}/{formatted_url}'
            print(url)

            logger.debug(f"Sending request to: {url}")

            # Use aiohttp for async requests
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise Exception(f"API request failed with status {response.status}: {text}")

                    data = await response.json()

                    #if not data or 'status' not in data or data['status'] != 'OK':
                    if data["errno"] != 0:
                        raise Exception(f"Invalid API response: {data}")


                    pois = data.get('result', [])
                    return_pois = []

                    for poi in pois:  # Limit to top 3 results
                        return_pois.append({
                            "name": poi.get("displayname", ""),
                            "address": poi.get("address", ""),
                            "lng": poi.get("lng", 0),
                            "lat": poi.get("lat", 0),
                            "city_name": poi.get("city", ""),
                            "poi_id": poi.get("id", ""),
                            "distance": poi.get("distance", 0),
                            "category": poi.get("category", "")
                        })

                    return return_pois

        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            raise Exception(f"Failed to get nearby location suggestions: {str(e)}")
