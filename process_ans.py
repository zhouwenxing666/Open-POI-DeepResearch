import pandas as pd
import json
import re
import ast

def parse_tool_output(content_string: str):
    """
    Safely parses the content of a 'tool' message if it's a dictionary.
    Returns None if no dictionary is found.
    """
    match = re.search(r'\{.*\}', content_string, re.DOTALL)
    if not match:
        return None

    dict_str = match.group(0)
    try:
        return ast.literal_eval(dict_str)
    except (ValueError, SyntaxError):
        try:
            return json.loads(dict_str)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse tool output string: {dict_str}")
            return None

def format_reference_info(conversation: list) -> str:
    """
    Formats the '参考信息' column by aggregating details from all tool calls
    in a single conversation.
    """
    reference_parts = []

    # Create maps for both parsed and raw tool outputs
    id_to_parsed_output = {}
    id_to_raw_content = {}
    for msg in conversation:
        if msg.get('role') == 'tool' and 'tool_call_id' in msg:
            raw_content = msg.get('content', '')
            id_to_raw_content[msg['tool_call_id']] = raw_content
            id_to_parsed_output[msg['tool_call_id']] = parse_tool_output(raw_content)

    for msg in conversation:
        if msg.get('role') == 'assistant' and 'tool_calls' in msg:
            for call in msg['tool_calls']:
                func_info = call.get('function', {})
                func_name = func_info.get('name')

                if func_name == 'terminate':
                    continue

                try:
                    func_args = json.loads(func_info.get('arguments', '{}'))
                except json.JSONDecodeError:
                    func_args = {}

                part = f"函数: {func_name}\n参数: {json.dumps(func_args, ensure_ascii=False, indent=2)}\n"

                # --- MODIFIED LOGIC TO HANDLE DEEP_SEARCH SEPARATELY ---
                if func_name == 'deep_search':
                    raw_output = id_to_raw_content.get(call.get('id'), 'N/A')
                    # Clean the prefix for better readability
                    prefix_to_remove = "Observed output of cmd `deep_search` executed:\n"
                    cleaned_content = raw_output.replace(prefix_to_remove, "", 1).strip()
                    part += f"搜索结果:\n{cleaned_content}\n"
                else:
                    # Logic for all other tools
                    output = id_to_parsed_output.get(call.get('id'))
                    if output and output.get('status') == 'success':
                        part += "结果:\n"
                        data = output.get('data', {})

                        locations_to_process = []
                        if func_name in ['location_search', 'location_around_search']:
                            locations_to_process = data
                        elif func_name == 'route_along_search':
                            locations_to_process = data.get('pois', [])

                        if locations_to_process:
                            for loc in locations_to_process:
                                name = loc.get('name', 'N/A')
                                address = loc.get('address', 'N/A')
                                distance = loc.get('distance', 'N/A')
                                part += f"  - 名称: {name}, 地址: {address}, 距离: {distance}\n"
                        elif not locations_to_process and func_name in ['location_search', 'location_around_search', 'route_along_search']:
                             part += "  - 未找到任何位置信息。\n"

                        if func_name == 'route_planner':
                            routes = data.get('routes', [])
                            if not routes:
                                part += "  - 未找到任何路线信息。\n"
                            for route in routes:
                                label = route.get('路线标签', 'N/A')
                                dist = route.get('路线距离', 'N/A')
                                time = route.get('预估时间', 'N/A')
                                lights = route.get('红绿灯', '未提供')
                                part += f"  - 路线: 标签='{label}', 距离='{dist}', 时间='{time}', 红绿灯='{lights}'\n"
                    else:
                        part += "结果: 调用失败或无数据\n"

                reference_parts.append(part)

    return "\n---\n".join(reference_parts)

def process_single_conversation(conversation: list) -> dict:
    """
    Processes a SINGLE conversation to extract query, summary, and reference info.
    """
    query = next((msg['content'] for msg in conversation if msg.get('role') == 'user'), None)

    last_assistant_msg = next((msg for msg in reversed(conversation) if msg.get('role') == 'assistant'), None)
    summary = ""
    if last_assistant_msg and 'content' in last_assistant_msg:
        summary = re.sub(r'<think>.*?</think>', '', last_assistant_msg['content'], flags=re.DOTALL).strip()

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
    Main function to read log and query files, process data, sort it, and save to Excel.
    """
    # log_filename = "raw_logs.txt" #input("Enter the path to your log file (e.g., app.log): ")
    log_filename = "raw_logs_07010_morning.txt"
    query_filename = "/nfs/volume-1593-3/user/zhouwenxing/projects/OpenManus/assets/query.txt" #input("Enter the path to your query order file (e.g., queries.txt): ")

    log_entries = []
    try:
        with open(log_filename, 'r', encoding='utf-8') as f:
            #log_content_string = f.read()
            for line in f:
                log_entries.append((line.split("train_data:")[-1]).strip())

        #if not log_content_string.strip():
        #    print(f"❌ Error: The log file '{log_filename}' is empty.")
        #    return
        #
        with open(query_filename, 'r', encoding='utf-8') as f:
            ordered_queries = [line.strip() for line in f if line.strip()]
        #if not ordered_queries:
        #    print(f"❌ Error: The query file '{query_filename}' is empty or contains no valid queries.")
        #    return

    except FileNotFoundError as e:
        print(f"❌ Error: A file was not found: {e.filename}")
        return
    except Exception as e:
        print(f"❌ An unexpected error occurred while reading files: {e}")
        return

    #log_entries = re.split(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \| INFO     \| app\.llm:ask_tool:873 - train_data:', log_content_string)

    all_records = []
    for entry in log_entries:
        try:
            conversation = json.loads(entry)
            print("json.loads done")
            record = process_single_conversation(conversation)
            if record:
                all_records.append(record)
        except json.JSONDecodeError as e:
            print(f"⚠️ Warning: Skipping an entry due to a JSON parsing error: {e}")
            continue

    if not all_records:
        print("❌ No valid data was processed from the log file. Please check its format.")
        return

    df = pd.DataFrame(all_records)

    df['query'] = df['query'].astype(str)
    ordered_queries_set = set(ordered_queries)

    df_in_order = df[df['query'].isin(ordered_queries_set)].copy()
    df_not_in_order = df[~df['query'].isin(ordered_queries_set)].copy()

    df_in_order['query'] = pd.Categorical(df_in_order['query'], categories=ordered_queries, ordered=True)
    df_sorted = df_in_order.sort_values('query')

    if not df_not_in_order.empty:
        print(f"⚠️ Found {len(df_not_in_order)} records in the log file that were not in the query file. Appending them to the end.")
        final_df = pd.concat([df_sorted, df_not_in_order], ignore_index=True)
    else:
        final_df = df_sorted

    output_filename = "output_ordered_07010_morning.xlsx"
    final_df.to_excel(output_filename, index=False)

    print(f"✅ Successfully created sorted Excel file: '{output_filename}' with {len(final_df)} records.")

if __name__ == "__main__":
    main()
