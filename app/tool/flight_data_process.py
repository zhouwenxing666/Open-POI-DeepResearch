import json
import pandas as pd
from datetime import datetime

def process_flight_data(json_data):
    """
    处理航班信息JSON数据，转换为结构化的DataFrame
    
    Args:
        json_data (str): 航班信息的JSON字符串
    
    Returns:
        pandas.DataFrame: 处理后的航班信息表格
    """
    # 如果输入是字符串，解析为Python对象
    if isinstance(json_data, str):
        data = json.loads(json_data)
    else:
        data = json_data
    
    # 创建存储所有航班信息的列表
    flights = []
    
    # 遍历每个航班记录
    for flight in data:
        # 获取航线信息（通常只有一个航段，取第一个）
        route = flight["flight_info"]["route_list"][0]
        departure_info = route["departure_info"]
        arrival_info = route["arrival_info"]
        airline_info = route["airline_info"]
        
        # 获取价格信息（取第一个价格）
        if "price_list" in flight and len(flight["price_list"]) > 0:
            price_info = flight["price_list"][0]["flight_route_price_list"][0]["adult_price_info"]
        else:
            price_info = {}
        
        # 整理基本信息
        flight_data = {
            "航班号": airline_info["flight_number"],
            "航空公司": airline_info["airline_simple_name"],
            "出发城市": departure_info["departure_city_name"],
            "到达城市": arrival_info["arrival_city_name"],
            "出发机场": f"{departure_info['departure_airport_simple_name']}{departure_info['departure_terminal'] if departure_info['departure_terminal'] else ''}",
            "到达机场": f"{arrival_info['arrival_airport_simple_name']}{arrival_info['arrival_terminal'] if arrival_info['arrival_terminal'] else ''}",
            "出发时间": departure_info["departure_datetime"],
            "到达时间": arrival_info["arrival_datetime"],
            "机型": airline_info["air_equip_type"],
            "是否共享": "是" if airline_info["is_share_flight"] == 1 else "否",
            "主航班号": airline_info["main_flight_number"] if airline_info["is_share_flight"] == 1 else "",
            "主航空公司": airline_info["main_airline_simple_name"] if airline_info["is_share_flight"] == 1 else "",
        }
        
        # 添加价格相关信息
        if price_info:
            # 将分转换为元
            sale_price_yuan = price_info.get("sale_price", 0) / 100
            
            flight_data.update({
                "舱位": f"{price_info.get('cabin_name', '')}{price_info.get('cabin_code', '')}",
                "价格(元)": round(sale_price_yuan, 2),
                "折扣": f"{price_info.get('discount', 0)}%",
                "基础价(元)": round(price_info.get("base_price", 0) / 100, 2),
                "燃油费(元)": round(price_info.get("fuel_cost", 0) / 100, 2),
                "建设费(元)": round(price_info.get("construction_cost", 0) / 100, 2),
                "可退": "是" if price_info.get("return_info", {}).get("returnable", 0) == 1 else "否",
                "可改签": "是" if price_info.get("change_info", {}).get("changeable", 0) == 1 else "否"
            })
        
        # 添加其他信息
        flight_data.update({
            "含餐食": "是" if airline_info.get("is_meal_included", 0) == 1 else "否",
            "经停": "是" if route["stop_info"]["is_stop"] == 1 else "否",
            "跨天": "是" if route.get("cross_day", 0) == 1 else "否",
            "飞行时长(分钟)": round(airline_info.get("flight_duration_seconds", 0) / 60),
            "飞行距离(公里)": airline_info.get("flight_distance_km", 0)
        })
        
        flights.append(flight_data)
    
    # 创建DataFrame
    df = pd.DataFrame(flights)
    
    # 处理共享航班的标注
    df["航空公司"] = df.apply(
        lambda row: f"{row['航空公司']}(共享)" if row["是否共享"] == "是" else row["航空公司"], 
        axis=1
    )
    
    # 优化列的顺序
    columns_order = [
        "航班号", "航空公司", "出发城市", "到达城市", "出发机场", "到达机场", 
        "出发时间", "到达时间", "机型", "舱位", "价格(元)", "折扣", 
        "基础价(元)", "燃油费(元)", "建设费(元)", "含餐食", "经停", "跨天", 
        "飞行时长(分钟)", "飞行距离(公里)", "可退", "可改签", 
        "是否共享", "主航班号", "主航空公司"
    ]
    
    # 确保所有列都存在
    for col in columns_order:
        if col not in df.columns:
            df[col] = None
    
    # 返回按指定顺序排列的列
    return df[columns_order]

def sort_flights(df, sort_by="价格(元)", ascending=True):
    """
    对航班数据进行排序
    
    Args:
        df (pandas.DataFrame): 航班数据
        sort_by (str): 排序字段
        ascending (bool): 是否升序
    
    Returns:
        pandas.DataFrame: 排序后的数据
    """
    return df.sort_values(by=sort_by, ascending=ascending)

def filter_flights(df, 
                  airline=None, 
                  departure_time_start=None, 
                  departure_time_end=None,
                  price_max=None,
                  airport=None):
    """
    根据条件筛选航班
    
    Args:
        df (pandas.DataFrame): 航班数据
        airline (str): 航空公司
        departure_time_start (str): 最早出发时间 (HH:MM)
        departure_time_end (str): 最晚出发时间 (HH:MM)
        price_max (float): 最高价格
        airport (str): 出发机场
    
    Returns:
        pandas.DataFrame: 筛选后的数据
    """
    filtered_df = df.copy()
    
    # 筛选航空公司
    if airline:
        filtered_df = filtered_df[filtered_df["航空公司"].str.contains(airline)]
    
    # 筛选出发时间范围
    if departure_time_start or departure_time_end:
        # 提取时间部分
        filtered_df["出发时间只有时分"] = filtered_df["出发时间"].apply(
            lambda x: datetime.strptime(x.split()[1], "%H:%M") if isinstance(x, str) else None
        )
        
        if departure_time_start:
            start_time = datetime.strptime(departure_time_start, "%H:%M")
            filtered_df = filtered_df[filtered_df["出发时间只有时分"] >= start_time]
        
        if departure_time_end:
            end_time = datetime.strptime(departure_time_end, "%H:%M")
            filtered_df = filtered_df[filtered_df["出发时间只有时分"] <= end_time]
        
        # 删除临时列
        filtered_df = filtered_df.drop("出发时间只有时分", axis=1)
    
    # 筛选价格
    if price_max is not None:
        filtered_df = filtered_df[filtered_df["价格(元)"] <= price_max]
    
    # 筛选机场
    if airport:
        filtered_df = filtered_df[filtered_df["出发机场"].str.contains(airport)]
    
    return filtered_df

def get_cheapest_flight(df, max_stops=0):
    """获取最便宜的航班"""
    if max_stops == 0:
        # 只看直飞航班
        direct_flights = df[df["经停"] == "否"]
        if not direct_flights.empty:
            return direct_flights.sort_values("价格(元)").iloc[0]
    
    # 考虑经停航班或直飞为空
    return df.sort_values("价格(元)").iloc[0]

def get_fastest_flight(df):
    """获取飞行时间最短的航班"""
    return df.sort_values("飞行时长(分钟)").iloc[0]

def get_latest_departure_earliest_arrival(df, date):
    """获取最晚出发最早到达的航班"""
    # 注意：这适用于特定日期的航班
    morning_arrivals = df[df["到达时间"].str.contains(f"{date} 1[0-2]:|{date} 0[0-9]:")]
    if not morning_arrivals.empty:
        return morning_arrivals.sort_values("出发时间", ascending=False).iloc[0]
    return None

def export_to_excel(df, filename):
    """导出到Excel文件"""
    df.to_excel(filename, index=False)
    print(f"数据已导出到 {filename}")

def export_to_csv(df, filename, encoding="utf-8"):
    """导出到CSV文件"""
    df.to_csv(filename, index=False, encoding=encoding)
    print(f"数据已导出到 {filename}")


def df_to_text(df, max_rows=None, max_cols=None):
    """
    将DataFrame转换为格式化的文本

    Args:
        df (pandas.DataFrame): 要转换的DataFrame
        max_rows (int): 最大显示行数，None表示全部
        max_cols (int): 最大显示列数，None表示全部

    Returns:
        str: 格式化的文本表格
    """
    # 如果需要限制行数
    if max_rows is not None:
        df = df.head(max_rows)

    # 如果需要限制列数
    if max_cols is not None and len(df.columns) > max_cols:
        df = df.iloc[:, :max_cols]

    # 方法1：使用to_string()方法
    text = df.to_string(index=False)

    return text

def df_to_markdown(df, max_rows=None):
    """
    将DataFrame转换为Markdown格式的表格文本

    Args:
        df (pandas.DataFrame): 要转换的DataFrame
        max_rows (int): 最大显示行数，None表示全部

    Returns:
        str: Markdown格式的文本表格
    """
    # 如果需要限制行数
    if max_rows is not None:
        df = df.head(max_rows)

    # 转换为Markdown格式
    markdown = df.to_markdown(index=False)

    return markdown

def df_to_csv_text(df, max_rows=None, sep=','):
    """
    将DataFrame转换为CSV格式的文本

    Args:
        df (pandas.DataFrame): 要转换的DataFrame
        max_rows (int): 最大显示行数，None表示全部
        sep (str): 分隔符

    Returns:
        str: CSV格式的文本
    """
    # 如果需要限制行数
    if max_rows is not None:
        df = df.head(max_rows)

    # 转换为CSV格式文本（不写入文件）
    import io
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=sep)
    text = buffer.getvalue()
    buffer.close()

    return text

# 使用示例
def format_for_display_as_text(df, num_flights=None):
    """
    格式化航班数据并返回文本格式

    Args:
        df (pandas.DataFrame): 航班数据
        num_flights (int): 要显示的航班数，None表示全部

    Returns:
        str: 格式化的文本表格
    """
    # 选择要显示的列
    display_columns = [
        "航班号", "航空公司", "出发城市", "到达城市", "出发机场", "到达机场",
        "出发时间", "到达时间", "机型", "舱位", "价格(元)", "折扣"
    ]

    # 确保所有列都存在
    display_df = df.copy()
    for col in display_columns:
        if col not in display_df.columns:
            display_df[col] = None

    display_df = display_df[display_columns]

    # 限制显示的航班数
    if num_flights is not None:
        display_df = display_df.head(num_flights)

    # 转换为文本
    return df_to_text(display_df)
# 使用示例
if __name__ == "__main__":
    # 从文件读取JSON数据
    with open("flight_data.json", "r", encoding="utf-8") as f:
        json_data = json.load(f)
    
    # 处理数据
    flights_df = process_flight_data(json_data)
    
    # 显示处理后的数据
    print("所有航班信息:")
    print(format_for_display(flights_df, 5))  # 显示前5个航班
    
    # 按价格排序
    sorted_by_price = sort_flights(flights_df, "价格(元)")
    print("\n按价格排序的航班:")
    print(format_for_display(sorted_by_price, 5))
    
    # 筛选航班
    filtered_flights = filter_flights(
        flights_df,
        airline="东方航空",
        departure_time_start="18:00",
        departure_time_end="22:00",
        price_max=1500
    )
    print("\n筛选后的航班:")
    print(format_for_display(filtered_flights))
    
    # 获取最便宜的航班
    cheapest = get_cheapest_flight(flights_df)
    print("\n最便宜的航班:")
    print(cheapest[["航班号", "航空公司", "出发时间", "到达时间", "价格(元)"]])
    
    # 导出到Excel
    # export_to_excel(flights_df, "flights.xlsx")
