import json
import asyncio
from typing import List, Optional, Union
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai import OpenAIError, AuthenticationError, RateLimitError, APIError
from app.llm import LLM  # 导入 LLM 类
from app.exceptions import TokenLimitExceeded
from app.logger import logger  # 假设已配置日志
from app.prompt.reward import SYSTEM_PROMPT, EVALUATION_CRITERIA, build_evaluation_prompt
from app.schema import (TOOL_CHOICE_TYPE, AgentState, Message, ToolCall,
                        ToolChoice)
from openai import (
    OpenAI,
    APIError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

REASONING_MODELS = ["o1", "o3-mini"]
MULTIMODAL_MODELS = [
    "gpt-4-vision-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]

class ContentValidator:
    def __init__(self):
        """
        初始化验证器类（需注入 LLM 实例）
        :param llm: LLM 实例，用于调用大语言模型接口
        """
        self.global_score = 0
        self.system_prompt = SYSTEM_PROMPT

    async def final_trajectory_score(
        self,
        user_query,
        messages
    ) -> int:
        """
        检验 manus 生成的最终方案并打分（调用 LLM 辅助评分）
        :return: 合理性得分
        """
        # 调用 LLM 获取评分响应
        llm_response = await self.ask_reward(query = user_query,
                    messages=messages,
                    system_msgs =
                    self.system_prompt
                    if self.system_prompt
                    else None
                )
        logger.info(f'👀👀 调用模型评估最终的输出: {llm_response}')
        total = json.loads(llm_response)["weighted_total"]

        if not llm_response:
            return 0  # 或根据需求处理异常情况

        # 假设 LLM 响应内容中包含评分字段
        # try:
        #     score = int(llm_response.choices)
        #     self.global_score += score
        #     return score
        # except (ValueError, IndexError):
        #     logger.error("LLM 响应格式错误，无法解析评分")
        return total

    async def ask_reward(
        self,
        query,
        messages,
        system_msgs,
        timeout: int = 300,
        temperature: int = 0,
        **kwargs,
    ) -> ChatCompletionMessage | None:
        """
        调用 LLM 给最终方案打分（整合后的方法）
        """

        # openai_api_key = "EMPTY"
        # openai_api_base = "http://10.66.180.89:30000/v1"
        # model = "/nfs/ofs-llab-cold/model/deepseek-ai/DeepSeek-R1-0528"

        openai_api_key = "9cb0a12b-dd0c-4a0f-a26c-47f799eab8ff"
        openai_api_base = "https://ark.cn-beijing.volces.com/api/v3"
        model = "deepseek-r1-250528"

        client = AsyncOpenAI(
            api_key=openai_api_key,
            base_url=openai_api_base,
        )

        try:
            # 格式化消息（通过注入的 llm 实例调用）
            final_msg = build_evaluation_prompt(messages, EVALUATION_CRITERIA)

            user_query = '用户需求: ' + query
            system_msgs = system_msgs + "\n" + user_query

            reward_messages = [
                # 系统消息（设定角色和任务）
                {"role": "system", "content": system_msgs},

                # 用户当前问题
                {"role": "user", "content": final_msg}
            ]

            # 构造请求参数
            response: ChatCompletion = await client.chat.completions.create(
            model=model,
            messages=reward_messages,
            temperature=temperature,
            timeout=timeout,
            response_format={"type": "json_object"}
            )

            # logger.info(f'👀👀 调用模型评估最终的输出: {response.choices[0].message.content}')
            # print(type(response.choices[0].message.content))
            # print(response.choices[0].message.content["weighted_total"])
            # 检查响应有效性
            # if not response.choices or not response.choices[0].message:
            #     logger.error("LLM 返回空响应")
            #     return None

            return response.choices[0].message.content

        except TokenLimitExceeded:
            raise  # 不记录日志，直接抛出
        except ValueError as ve:
            logger.error(f"ask_reward 验证错误: {ve}")
            raise
        except OpenAIError as oe:
            logger.error(f"OpenAI API 错误: {oe}")
            if isinstance(oe, AuthenticationError):
                logger.error("认证失败，请检查 API key")
            elif isinstance(oe, RateLimitError):
                logger.error("速率限制超限，尝试增加重试次数")
            elif isinstance(oe, APIError):
                logger.error(f"API 错误详情: {oe}")
            raise
        except Exception as e:
            logger.error(f"ask_reward 意外错误: {e}")
            raise

    # 其他辅助方法（保持原有逻辑）
    def _check_specific_condition(self, content):
        """
        检查特定条件
        :return: 布尔值，表示是否满足条件
        """
        pass


if __name__ == "__main__":
    from app.llm import LLM
    from app.config import LLMSettings, config
    from app.schema import Message

    # 初始化 LLM 实例
    llm_config = LLMSettings()  # 假设 LLMSettings 可以无参数初始化
    llm = LLM(config_name="default", llm_config=llm_config)

    # 初始化 ContentValidator 实例
    validator = ContentValidator(llm)

    # 模拟消息列表
    test_messages = [
        Message(user="user", content="这是一个测试消息")
    ]

    try:
        # 调用异步的 final_trajectory_score 方法
        import asyncio
        score = asyncio.run(validator.final_trajectory_score(test_messages))
        print(f"最终方案的合理性得分: {score}")
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
