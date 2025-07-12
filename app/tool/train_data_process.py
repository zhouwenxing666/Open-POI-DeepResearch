import json
import pandas as pd
from datetime import datetime
import re

def process_train_data(json_data):
    """
    处理火车信息JSON数据，转换为结构化的DataFrame
    
    Args:
        json_data (str or dict): 火车信息的JSON字符串或字典
    
    Returns:
        pandas.DataFrame: 处理后的火车信息表格
    """
    # 如果输入是字符串，解析为Python对象
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    # 提取出发和到达城市信息
    departure_city = data.get("DepartureCity", {}).get("CityName", "")
    arrival_city = data.get("ArriveCity", {}).get("CityName", "")
    
    # 处理出发日期
    departure_date = ""
    if "DepartureDate" in data:
        # 处理/Date(1742400000000+0800)/格式
        date_str = data["DepartureDate"]
        match = re.search(r'/Date\((\d+)([+-]\d{4})?\)/', date_str)
        if match:
            timestamp = int(match.group(1)) // 1000  # 毫秒转秒
            departure_date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
    
    # 创建存储所有火车信息的列表
    trains = []
    
    # 遍历每个火车记录
    for train in data.get("TrainItems", []):
        # 获取车票信息
        ticket_result = train.get("TicketResult", {})
        ticket_items = ticket_result.get("TicketItems", [])
        
        # 提取每种座位类型及价格
        seats_info = {}
        for ticket in ticket_items:
            seat_type = ticket.get("SeatTypeName", "")
            price = ticket.get("ShowPrice", 0)
            inventory = ticket.get("Inventory", 0)
            bookable = ticket.get("Bookable", False)
            
            # 添加到seats_info字典
            seats_info[seat_type] = {
                "价格": price,
                "余票": inventory,
                "可预订": "是" if bookable else "否"
            }
        
        # 计算行程时间
        use_time_minutes = train.get("UseTime", 0)
        hours = use_time_minutes // 60
        minutes = use_time_minutes % 60
        use_time = f"{hours}时{minutes}分"
        
        # 整理基本信息
        train_data = {
            "车次": train.get("TrainName", ""),
            "车型": train.get("TrainTypeShortName", ""),
            "出发城市": departure_city,
            "到达城市": arrival_city,
            "出发站": ticket_result.get("DepartureStationName", train.get("StartStationName", "")),
            "到达站": ticket_result.get("ArrivalStationName", train.get("EndStationName", "")),
            "出发日期": departure_date,
            "出发时间": ticket_result.get("DepartureTime", train.get("StartTime", "")),
            "到达时间": ticket_result.get("ArrivalTime", train.get("EndTime", "")),
            "历时": use_time,
            "是否始发站": "是" if train.get("IsStartStation", False) else "否",
            "是否终点站": "是" if train.get("IsEndStation", False) else "否",
            "可预订": "是" if train.get("Bookable", False) else "否",
            "支持刷卡": "是" if train.get("IsSupportCard", "") == "1" else "否"
        }
        
        # 添加不同座位类型的价格和余票信息
        seat_types = ["商务座", "一等座", "二等座"]
        for seat_type in seat_types:
            if seat_type in seats_info:
                train_data[f"{seat_type}价格"] = seats_info[seat_type]["价格"]
                train_data[f"{seat_type}余票"] = seats_info[seat_type]["余票"]
                train_data[f"{seat_type}可预订"] = seats_info[seat_type]["可预订"]
            else:
                train_data[f"{seat_type}价格"] = None
                train_data[f"{seat_type}余票"] = None
                train_data[f"{seat_type}可预订"] = "否"
        
        trains.append(train_data)
    
    # 创建DataFrame
    df = pd.DataFrame(trains)
    
    # 优化列的顺序
    columns_order = [
        "车次", "车型", "出发城市", "到达城市", "出发站", "到达站", 
        "出发日期", "出发时间", "到达时间", "历时", 
        "二等座价格", "二等座余票", "二等座可预订",
        "一等座价格", "一等座余票", "一等座可预订",
        "商务座价格", "商务座余票", "商务座可预订",
        "是否始发站", "是否终点站", "可预订"
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

def sort_trains(df, sort_by="出发时间", ascending=True):
    """
    对火车数据进行排序
    
    Args:
        df (pandas.DataFrame): 火车数据
        sort_by (str): 排序字段
        ascending (bool): 是否升序
    
    Returns:
        pandas.DataFrame: 排序后的数据
    """
    return df.sort_values(by=sort_by, ascending=ascending)

def filter_trains(df, 
                 train_type=None,
                 departure_time_start=None,
                 departure_time_end=None,
                 min_price=None,
                 max_price=None,
                 seat_type="二等座",
                 bookable=None):
    """
    根据条件筛选火车
    
    Args:
        df (pandas.DataFrame): 火车数据
        train_type (str): 车型
        departure_time_start (str): 最早出发时间 (HH:MM)
        departure_time_end (str): 最晚出发时间 (HH:MM)
        min_price (float): 最低价格
        max_price (float): 最高价格
        seat_type (str): 座位类型 ("商务座", "一等座", "二等座")
        bookable (bool): 是否可预订
    
    Returns:
        pandas.DataFrame: 筛选后的数据
    """
    filtered_df = df.copy()
    
    # 筛选车型
    if train_type:
        filtered_df = filtered_df[filtered_df["车型"] == train_type]
    
    # 筛选出发时间范围
    if departure_time_start or departure_time_end:
        # 提取时间部分
        filtered_df["出发时间对象"] = filtered_df["出发时间"].apply(
            lambda x: datetime.strptime(x, "%H:%M") if isinstance(x, str) else None
        )
        
        if departure_time_start:
            start_time = datetime.strptime(departure_time_start, "%H:%M")
            filtered_df = filtered_df[filtered_df["出发时间对象"] >= start_time]
        
        if departure_time_end:
            end_time = datetime.strptime(departure_time_end, "%H:%M")
            filtered_df = filtered_df[filtered_df["出发时间对象"] <= end_time]
        
        # 删除临时列
        filtered_df = filtered_df.drop("出发时间对象", axis=1)
    
    # 筛选价格
    price_col = f"{seat_type}价格"
    if price_col in filtered_df.columns:
        if min_price is not None:
            filtered_df = filtered_df[filtered_df[price_col] >= min_price]
        if max_price is not None:
            filtered_df = filtered_df[filtered_df[price_col] <= max_price]
    
    # 筛选是否可预订
    bookable_col = f"{seat_type}可预订"
    if bookable is not None and bookable_col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[bookable_col] == ("是" if bookable else "否")]
    
    return filtered_df

# 使用示例
if __name__ == "__main__":
    # 示例JSON数据（直接使用传入的数据）
    train_json= {}
    
    # 处理数据
    trains_df = process_train_data(train_json)
    
    # 显示处理后的数据
    print("火车信息表格：")
    print(df_to_text(trains_df))
    
    # 按出发时间排序
    sorted_by_time = sort_trains(trains_df, "出发时间")
    print("\n按出发时间排序的火车:")
    print(df_to_text(sorted_by_time))
    
    # 筛选二等座有票的车次
    available_trains = filter_trains(trains_df, seat_type="二等座", bookable=True)
    print("\n二等座有票的车次:")
    print(df_to_text(available_trains))
