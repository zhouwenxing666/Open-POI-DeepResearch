import argparse
import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

# 设置服务端地址
BASE_URL = "http://10.191.68.172:8100"


def request(data):
    prompt_data = {"prompt": data}
    # 发送 POST 请求到 /api/chat
    try:
        response = requests.post(f"{BASE_URL}/api/chat", json=prompt_data, timeout=6000)
        if response.status_code == 200:
            # 保存结果为 JSON 文件
            result = response.json()
            return result
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print(f"请求超时！请稍后再试: {data[:30]}...")
        return None
    except requests.exceptions.RequestException as e:
        print(f"请求失败：{e}")
        return None


def process_line(line, processed):
    line = line.strip()
    if line in processed:
        return None

    print(f"开始处理: {line[:30]}...")
    response = request(line)
    if response is None:
        print(f"响应为空: {line[:30]}...")
        return None

    output_json = {"problem": line, "response": response}
    return output_json


def main():
    parser = argparse.ArgumentParser(description="并发处理查询请求")
    parser.add_argument("--input_file", help="输入文件路径")
    parser.add_argument("--workers", type=int, default=5, help="并发工作线程数量")
    args = parser.parse_args()

    # 获取当前日期
    current_date = datetime.datetime.now().strftime("%Y%m%d")
    output_file = f"SFT_train_data_{current_date}.json"
    # output_file = "SFT_train_data_20250417.json"

    # 读取输入文件
    with open(args.input_file, "r") as f:
        all_lines = f.readlines()
        lines = []
        for line in all_lines:
            # line = json.loads(line)
            prompt = line.strip()
            if prompt == "":
                continue
            lines.append(prompt)

    # 读取已处理的数据
    processed = set()
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            for line in f:
                try:
                    processed.add(json.loads(line)["problem"])
                except json.JSONDecodeError:
                    continue

    # 使用线程池并发处理
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(process_line, line, processed) for line in lines]

        with open(output_file, "a+") as f:
            for future in futures:
                result = future.result()
                if result:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    f.flush()
                    processed.add(result["problem"])

    print(f"处理完成，结果已保存到 {output_file}")


if __name__ == "__main__":
    main()
