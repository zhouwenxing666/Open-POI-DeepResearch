import json
import pandas as pd

def process_hotel_data(json_data):
    """
    处理酒店信息JSON数据，转换为结构化的DataFrame
    
    Args:
        json_data (str or list): 酒店信息的JSON字符串或列表
    
    Returns:
        pandas.DataFrame: 处理后的酒店信息表格
    """
    # 如果输入是字符串，解析为Python对象
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    # 创建存储所有酒店信息的列表
    hotels = []
    
    # 遍历每个酒店记录
    for hotel in data:
        # 处理标签信息
        tags = []
        if "tag_info_list" in hotel and hotel["tag_info_list"]:
            tags = [tag["name"] for tag in hotel["tag_info_list"]]
        
        # 获取经纬度
        lng = hotel.get("lng", hotel.get("hotel_details", {}).get("lng", ""))
        lat = hotel.get("lat", hotel.get("hotel_details", {}).get("lat", ""))
        
        # 整理基本信息
        hotel_data = {
            "酒店ID": hotel.get("didi_hotel_id", ""),
            "酒店名称": hotel.get("hotel_name", ""),
            "城市": hotel.get("city_name", ""),
            "地址": hotel.get("hotel_address", ""),
            "酒店类型": hotel.get("level_name", ""),
            "星级": hotel.get("hotel_details", {}).get("hotel_star", ""),
            "平均价格": hotel.get("price_avg", 0),
            "评分": hotel.get("hotel_score", ""),
            "评分描述": hotel.get("score_desc", ""),
            "评价数量": hotel.get("score_num", 0),
            "评分级别": hotel.get("score_level_name", ""),
            "标签": ", ".join(tags),
            "距离": hotel.get("distance", ""),
            "经度": lng,
            "纬度": lat,
            "有库存": "是" if hotel.get("has_stock", 0) == 1 else "否",
            "显示价格": "是" if hotel.get("show_price", False) else "否",
            "图片URL": hotel.get("photo_url", "")
        }
        
        hotels.append(hotel_data)
    
    # 创建DataFrame
    df = pd.DataFrame(hotels)
    
    # 优化列的顺序
    columns_order = [
        "酒店ID", "酒店名称", "城市", "地址", "酒店类型", "星级", 
        "平均价格", "评分", "评分级别", "评价数量", "标签", 
        "距离", "有库存", "显示价格"
    ]
    
    # 确保所有列都存在
    for col in columns_order:
        if col not in df.columns:
            df[col] = None
    
    # 返回按指定顺序排列的列
    return df[columns_order]

def df_to_text(df, max_rows=None):
    """
    将DataFrame转换为格式化的文本
    
    Args:
        df (pandas.DataFrame): 要转换的DataFrame
        max_rows (int): 最大显示行数，None表示全部
    
    Returns:
        str: 格式化的文本表格
    """
    # 如果需要限制行数
    if max_rows is not None:
        df = df.head(max_rows)
    
    # 使用to_string()方法转换为文本
    text = df.to_string(index=False)
    
    return text

def sort_hotels(df, sort_by="平均价格", ascending=True):
    """
    对酒店数据进行排序
    
    Args:
        df (pandas.DataFrame): 酒店数据
        sort_by (str): 排序字段
        ascending (bool): 是否升序
    
    Returns:
        pandas.DataFrame: 排序后的数据
    """
    return df.sort_values(by=sort_by, ascending=ascending)

def filter_hotels(df, 
                 hotel_type=None,
                 min_price=None,
                 max_price=None,
                 min_rating=None,
                 has_stock=None):
    """
    根据条件筛选酒店
    
    Args:
        df (pandas.DataFrame): 酒店数据
        hotel_type (str): 酒店类型
        min_price (float): 最低价格
        max_price (float): 最高价格
        min_rating (float): 最低评分
        has_stock (bool): 是否有库存
    
    Returns:
        pandas.DataFrame: 筛选后的数据
    """
    filtered_df = df.copy()
    
    # 筛选酒店类型
    if hotel_type:
        filtered_df = filtered_df[filtered_df["酒店类型"] == hotel_type]
    
    # 筛选价格范围
    if min_price is not None:
        filtered_df = filtered_df[filtered_df["平均价格"] >= min_price]
    if max_price is not None:
        filtered_df = filtered_df[filtered_df["平均价格"] <= max_price]
    
    # 筛选评分
    if min_rating is not None:
        # 将评分转换为数值类型
        filtered_df["评分"] = pd.to_numeric(filtered_df["评分"], errors="coerce")
        filtered_df = filtered_df[filtered_df["评分"] >= min_rating]
    
    # 筛选库存状态
    if has_stock is not None:
        filtered_df = filtered_df[filtered_df["有库存"] == ("是" if has_stock else "否")]
    
    return filtered_df

# 使用示例
if __name__ == "__main__":
    # 示例JSON数据
    hotel_data = [
        {
            'didi_hotel_id': 31959, 
            'hotel_name': '建国铂萃酒店(北京中关村软件园国际会议中心店)', 
            'level_name': '高档型', 
            'level_id': 3, 
            'price_avg': 724, 
            'city_name': '北京', 
            'hotel_score': '4.8', 
            'score_desc': '5条点评', 
            'hotel_address': '上地产业园/西三旗', 
            'tag_info_list': [
                {'type': 6, 'name': '好打车'}, 
                {'type': 1, 'name': '立即确认'}, 
                {'type': 9, 'name': '优选'}, 
                {'type': 7, 'name': '会议设施'}
            ],
            'hotel_details': {
                'hotel_star': 4
            },
            'has_stock': 1,
            'distance': '距您直线908米'
        },
        {
            'didi_hotel_id': 3482999, 
            'hotel_name': '辉煌国际服务公寓(软件园四号路分店)', 
            'level_name': '经济型', 
            'level_id': 1, 
            'price_avg': 0, 
            'city_name': '北京', 
            'hotel_score': '4.7', 
            'score_desc': '', 
            'hotel_address': '软件园四号路辉煌国际广场甲骨文大厦快手总部旁', 
            'tag_info_list': [
                {'type': 9, 'name': '优选'}
            ],
            'hotel_details': {
                'hotel_star': 2
            },
            'has_stock': 0,
            'distance': '距您直线809米'
        }
    ]
    
    # 处理数据
    hotels_df = process_hotel_data(hotel_data)
    
    # 显示处理后的数据
    print("酒店信息表格：")
    print(df_to_text(hotels_df))
    
    # 按价格排序
    sorted_by_price = sort_hotels(hotels_df, "平均价格")
    print("\n按价格排序的酒店:")
    print(df_to_text(sorted_by_price))
