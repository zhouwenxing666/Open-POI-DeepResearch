import re
from pathlib import Path
from collections import defaultdict

def extract_raw_logs(log_file_path, query_file_path, output_file="raw_logs.txt"):
    """
    从日志文件中提取包含特定查询的原始日志行

    参数:
        log_file_path: 日志文件路径
        query_file_path: 查询文本文件路径(每行一个查询)
        output_file: 输出文件路径
    """
    # 加载查询列表
    with open(query_file_path, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]

    print(f"已加载 {len(queries)} 条查询条件")

    # 存储结果 {query: [log_lines]}
    query_results = defaultdict(list)

    # 编译正则表达式匹配train_data部分
    pattern = re.compile(r'train_data:(\[{.*?}\])', re.DOTALL)

    with open(log_file_path, 'r', encoding='utf-8') as log_file:
        for line in log_file:
            # 检查是否包含train_data
            if 'train_data' in line:
                # 提取train_data内容
                match = pattern.search(line)
                if match:
                    train_data_str = match.group(1)
                    # 检查每个查询是否在train_data中
                    if "你是OpenManus" in train_data_str:
                        for query in queries:
                            if query in train_data_str:
                                query_results[query].append(line)
                                break

    print(f"匹配到 {sum(len(v) for v in query_results.values())} 条日志记录")

    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as out_file:
        for query, log_lines in query_results.items():
            out_file.write(f"=== 查询: {query} ===\n")
            out_file.write(f"=== 匹配到 {len(log_lines)} 条记录 ===\n\n")
            # 只保留最长的记录
            longest_line = max(log_lines, key=len)
            out_file.write(longest_line)
            out_file.write("\n" + "="*80 + "\n\n")

    print(f"原始日志已保存到: {output_file}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='提取包含特定查询的原始日志行')
    parser.add_argument('log_file', help='日志文件路径')
    parser.add_argument('query_file', help='查询文本文件路径')
    parser.add_argument('-o', '--output', default="raw_logs_0707_gaode.txt", help='输出文件路径')

    args = parser.parse_args()

    extract_raw_logs(args.log_file, args.query_file, args.output)
