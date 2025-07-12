import pandas as pd
import json
import re
import ast

def parse_tool_output(content_string: str):
    """
    Safely parses the content of a 'tool' message if it's a dictionary.
    Returns None if no dictionary is found.
    """
    # The new log format is clean JSON, so we can simplify this.
    # The old regex was to find a dict-like string within a larger string.
    # The new format's 'content' is often a pure JSON string after the prefix.
    content_string = content_string.strip()
    if content_string.startswith("Observed output of cmd"):
         # Find the start of the JSON/dict
        json_start_index = content_string.find('{')
        if json_start_index != -1:
            dict_str = content_string[json_start_index:]
            try:
                # Prioritize json.loads as it's the standard format
                return json.loads(dict_str)
            except json.JSONDecodeError:
                try:
                    # Fallback for dict-like strings that aren't valid JSON
                    return ast.literal_eval(dict_str)
                except (ValueError, SyntaxError):
                    print(f"Warning: Could not parse tool output string: {dict_str}")
                    return None
    return None # Return None if not a tool output format we recognize

def format_reference_info(conversation: list) -> str:
    """
    Formats the '参考信息' column by aggregating details from all tool calls
    in a single conversation, adapted for the new log format.
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

    # --- DEFINE NEW TOOL GROUPS FOR EASIER HANDLING ---
    LOCATION_TOOLS = ['maps_text_search', 'maps_around_search', 'maps_geo', 'maps_search_detail']
    ROUTE_TOOLS = ['maps_direction_driving', 'maps_direction_walking', 'maps_direction_bicycling', 'maps_direction_transit_integrated']
    DISTANCE_TOOL = 'maps_distance'

    for msg in conversation:
        if msg.get('role') == 'assistant' and 'tool_calls' in msg:
            for call in msg['tool_calls']:
                func_info = call.get('function', {})
                func_name = func_info.get('name')

                if func_name == 'terminate':
                    continue

                try:
                    # Arguments can be a stringified JSON
                    func_args = json.loads(func_info.get('arguments', '{}'))
                except (json.JSONDecodeError, TypeError):
                    # Or already a dict
                    func_args = func_info.get('arguments', {})


                part = f"函数: {func_name}\n参数: {json.dumps(func_args, ensure_ascii=False, indent=2)}\n"

                if func_name == 'deep_search':
                    raw_output = id_to_raw_content.get(call.get('id'), 'N/A')
                    prefix_to_remove = "Observed output of cmd `deep_search` executed:\n"
                    cleaned_content = raw_output.replace(prefix_to_remove, "", 1).strip()
                    part += f"搜索结果:\n{cleaned_content}\n"
                else:
                    output = id_to_parsed_output.get(call.get('id'))
                    if output:
                        part += "结果:\n"

                        # --- MODIFIED LOGIC FOR NEW TOOL NAMES AND STRUCTURES ---
                        if func_name in LOCATION_TOOLS:
                            locations_to_process = output.get('pois')
                            # For maps_geo, the data is in 'results'
                            if not locations_to_process:
                                locations_to_process = output.get('results')

                            if locations_to_process:
                                for loc in locations_to_process:
                                    name = loc.get('name', 'N/A')
                                    address = loc.get('address', 'N/A')
                                    location_str = loc.get('location', 'N/A')
                                    part += f"  - 名称: {name}, 地址: {address}, 坐标: {location_str}\n"
                            else:
                                 part += "  - 未找到任何位置信息。\n"

                        elif func_name in ROUTE_TOOLS:
                            routes = output.get('paths', []) # New field is 'paths'
                            if not routes:
                                part += "  - 未找到任何路线信息。\n"
                            else:
                                for i, route in enumerate(routes):
                                    # New fields: distance in meters, duration in seconds
                                    dist_m = int(route.get('distance', 0))
                                    dura_s = int(route.get('duration', 0))
                                    dist_km = f"{dist_m / 1000:.2f}公里"
                                    dura_min = f"{dura_s / 60:.2f}分钟"
                                    part += f"  - 路线 {i+1}: 距离='{dist_km}', 时间='{dura_min}'\n"

                        elif func_name == DISTANCE_TOOL:
                            results = output.get('results', [])
                            if not results:
                                 part += "  - 未能测量距离。\n"
                            else:
                                for res in results:
                                    dist_m = int(res.get('distance', 0))
                                    dura_s = int(res.get('duration', 0))
                                    dist_km = f"{dist_m / 1000:.2f}公里" if dist_m > 0 else "N/A"
                                    dura_min = f"{dura_s / 60:.2f}分钟" if dura_s > 0 else "N/A"
                                    part += f"  - 测量结果: 距离='{dist_km}', 时间='{dura_min}'\n"
                        else:
                            # Fallback for any other tools
                            part += f"  {json.dumps(output, ensure_ascii=False, indent=4)}\n"
                    else:
                        part += "结果: 调用失败或无数据\n"

                reference_parts.append(part)

    return "\n---\n".join(reference_parts)


def process_single_conversation(conversation: list) -> dict:
    """
    Processes a SINGLE conversation to extract query, summary, and reference info.
    (This function's logic remains the same as it is generic)
    """
    query = next((msg['content'] for msg in conversation if msg.get('role') == 'user'), None)

    last_assistant_msg = next((msg for msg in reversed(conversation) if msg.get('role') == 'assistant' and msg.get('content')), None)
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
    # --- UPDATED FILENAMES ---
    log_filename = "raw_logs_07010_morning.txt"
    # Assuming the query file is the same or has a similar path
    query_filename = "/nfs/volume-1593-3/user/zhouwenxing/projects/OpenManus/assets/query.txt"

    log_entries = []
    try:
        with open(log_filename, 'r', encoding='utf-8') as f:
            for line in f:
                # The splitting logic remains the same as the log format is consistent
                # It looks for "train_data:" and takes the content after it
                if "train_data:" in line:
                    log_entries.append(line.split("train_data:")[-1].strip())

        if not log_entries:
           print(f"❌ Error: The log file '{log_filename}' is empty or has no 'train_data:' entries.")
           return

        with open(query_filename, 'r', encoding='utf-8') as f:
            ordered_queries = [line.strip() for line in f if line.strip()]
        if not ordered_queries:
            print(f"❌ Error: The query file '{query_filename}' is empty or contains no valid queries.")
            return

    except FileNotFoundError as e:
        print(f"❌ Error: A file was not found: {e.filename}")
        return
    except Exception as e:
        print(f"❌ An unexpected error occurred while reading files: {e}")
        return

    all_records = []
    for entry in log_entries:
        try:
            # The core data is still a JSON list of conversation turns
            conversation = json.loads(entry)
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

    # The sorting logic remains the same
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

    # --- UPDATED OUTPUT FILENAME ---
    output_filename = "output_ordered_07010_morning.xlsx"
    final_df.to_excel(output_filename, index=False)

    print(f"✅ Successfully created sorted Excel file: '{output_filename}' with {len(final_df)} records.")

if __name__ == "__main__":
    main()
