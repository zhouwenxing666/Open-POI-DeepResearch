import pandas as pd
import json
import re

def format_reference_info(conversation: list) -> str:
    """
    [新] 提取并格式化所有工具调用及其结果。

    提取每个 "assistant" 消息中的 "tool_calls" (函数名和参数)
    以及每个 "tool" 消息中的 "content" (结果)，并进行配对。
    """
    # 步骤 1: 创建一个从 tool_call_id 到其结果内容的映射
    tool_results = {}
    for msg in conversation:
        if msg.get('role') == 'tool' and 'tool_call_id' in msg:
            content = msg.get('content', '')
            # 应用内容截断规则
            if len(content) > 300:
                content = content[:300] + '...'
            tool_results[msg['tool_call_id']] = content

    # 步骤 2: 遍历对话，格式化每个工具调用及其对应的结果
    reference_parts = []
    for msg in conversation:
        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
            for call in msg['tool_calls']:
                # 使用 .get() 安全地访问嵌套字典
                func_info = call.get('function', {})
                func_name = func_info.get('name', 'N/A')

                # arguments 已经是 JSON 字符串，直接使用
                func_args_str = func_info.get('arguments', '{}')

                # 从映射中查找对应的结果
                result_content = tool_results.get(call.get('id'), '结果未找到')

                # 构建每个工具调用的文本块
                part = (
                    f"函数: {func_name}\n"
                    f"参数: {func_args_str}\n"
                    f"结果: {result_content}"
                )
                reference_parts.append(part)

    # 使用分隔符连接所有文本块
    return "\n---\n".join(reference_parts)


def process_single_conversation(conversation: list) -> dict:
    """
    处理单个对话，提取query, summary, 和 reference_info。
    (此函数基本保持不变，仅调用新的 format_reference_info)
    """
    # 提取第一个用户消息作为 query
    query = next((msg['content'] for msg in conversation if msg.get('role') == 'user'), None)

    # 提取最后一个助手的回复作为 summary，并移除<think>标签
    last_assistant_msg = next((msg for msg in reversed(conversation) if msg.get('role') == 'assistant' and msg.get('content')), None)
    summary = ""
    if last_assistant_msg:
        summary = re.sub(r'<think>.*?</think>', '', last_assistant_msg['content'], flags=re.DOTALL).strip()

    # 调用新的格式化函数
    reference_info = format_reference_info(conversation)

    if query:
        return {
            'query': query,
            'summary': summary,
            '参考信息': reference_info
        }
    return None

def main():
    """
    主函数：读取日志和查询文件，处理数据，排序并保存到Excel。
    (此函数基本保持不变)
    """


    # log_filename = "/nfs/volume-1593-3/user/zhouwenxing/projects/OpenManus/raw_logs_07010_night_heixiong.txt"
    # log_filename = "raw_logs_07010_night_shenyang.txt"
    log_filename = "/nfs/volume-1593-3/user/zhouwenxing/projects/OpenManus/raw_logs_0707_gaode.txt"


    # log_filename = "raw_logs_07010_night_gugong.txt"
    query_filename = "/nfs/volume-1593-3/user/zhouwenxing/projects/OpenManus/assets/query.txt"

    log_entries = []
    try:
        with open(log_filename, 'r', encoding='utf-8') as f:
            for line in f:
                # 检查行是否包含有效的分隔符
                if "train_data:" in line:
                    json_str = line.split("train_data:")[-1].strip()
                    if json_str: # 确保分割后有内容
                        log_entries.append(json_str)

        if not log_entries:
            print(f"❌ Error: No valid 'train_data:' entries found in '{log_filename}'.")
            return

        with open(query_filename, 'r', encoding='utf-8') as f:
            ordered_queries = [line.strip() for line in f if line.strip()]
        if not ordered_queries:
            print(f"⚠️ Warning: The query file '{query_filename}' is empty. Output will not be sorted.")

    except FileNotFoundError as e:
        print(f"❌ Error: A file was not found: {e.filename}")
        return
    except Exception as e:
        print(f"❌ An unexpected error occurred while reading files: {e}")
        return

    all_records = []
    for i, entry in enumerate(log_entries):
        try:
            conversation = json.loads(entry)
            record = process_single_conversation(conversation)
            if record:
                all_records.append(record)
        except json.JSONDecodeError as e:
            print(f"⚠️ Warning: Skipping entry #{i+1} due to a JSON parsing error: {e}")
            # 为了调试，可以打印出出错的行
            # print(f"Problematic JSON string: {entry[:200]}...")
            continue
        except Exception as e:
            print(f"An unexpected error occurred processing entry #{i+1}: {e}")
            continue


    if not all_records:
        print("❌ No valid data was processed from the log file. Please check its format.")
        return

    df = pd.DataFrame(all_records)

    # 排序逻辑保持不变
    df['query'] = df['query'].astype(str)
    ordered_queries_set = set(ordered_queries)

    df_in_order = df[df['query'].isin(ordered_queries_set)].copy()
    df_not_in_order = df[~df['query'].isin(ordered_queries_set)].copy()

    if ordered_queries:
        df_in_order['query'] = pd.Categorical(df_in_order['query'], categories=ordered_queries, ordered=True)
        df_sorted = df_in_order.sort_values('query')
    else:
        df_sorted = df_in_order # 如果没有排序文件，则不排序

    if not df_not_in_order.empty:
        print(f"⚠️ Found {len(df_not_in_order)} records in the log file that were not in the query file. Appending them to the end.")
        final_df = pd.concat([df_sorted, df_not_in_order], ignore_index=True)
    else:
        final_df = df_sorted

    output_filename = "output_ordered_0707_gaode.xlsx"
    final_df.to_excel(output_filename, index=False)

    print(f"✅ Successfully created sorted Excel file: '{output_filename}' with {len(final_df)} records.")

if __name__ == "__main__":
    main()
