"""
LLM工具函数
统一的LLM初始化，自动处理代理配置
"""
import httpx
from langchain_openai import ChatOpenAI
from config import get_config
from typing import Optional


def create_chat_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: float = 60.0
) -> ChatOpenAI:
    """
    创建ChatOpenAI实例，自动禁用代理

    Args:
        model: 模型名称，默认使用配置中的模型
        api_key: API密钥，默认使用配置中的密钥
        base_url: API基础URL，默认使用配置中的URL
        temperature: 温度参数，默认使用配置中的值
        max_tokens: 最大token数，默认使用配置中的值
        timeout: 超时时间（秒）

    Returns:
        ChatOpenAI实例
    """
    config = get_config()
    llm_config = config.llm

    # 使用配置中的默认值
    model = model or llm_config.model
    api_key = api_key or llm_config.api_key
    base_url = base_url or llm_config.base_url
    temperature = temperature if temperature is not None else llm_config.temperature
    max_tokens = max_tokens or llm_config.max_tokens

    # 创建httpx客户端，明确禁用代理
    http_client = None
    if llm_config.disable_proxy:
        # 使用trust_env=False禁用环境变量中的代理设置
        http_client = httpx.Client(
            trust_env=False,  # 不使用环境变量中的代理
            timeout=timeout
        )

    # 创建ChatOpenAI实例
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        http_client=http_client
    )


def create_async_chat_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: float = 60.0
) -> ChatOpenAI:
    """
    创建异步ChatOpenAI实例，自动禁用代理

    Args:
        model: 模型名称，默认使用配置中的模型
        api_key: API密钥，默认使用配置中的密钥
        base_url: API基础URL，默认使用配置中的URL
        temperature: 温度参数，默认使用配置中的值
        max_tokens: 最大token数，默认使用配置中的值
        timeout: 超时时间（秒）

    Returns:
        ChatOpenAI实例（支持异步）
    """
    config = get_config()
    llm_config = config.llm

    # 使用配置中的默认值
    model = model or llm_config.model
    api_key = api_key or llm_config.api_key
    base_url = base_url or llm_config.base_url
    temperature = temperature if temperature is not None else llm_config.temperature
    max_tokens = max_tokens or llm_config.max_tokens

    # 创建异步httpx客户端，明确禁用代理
    async_http_client = None
    if llm_config.disable_proxy:
        # 使用trust_env=False禁用环境变量中的代理设置
        async_http_client = httpx.AsyncClient(
            trust_env=False,  # 不使用环境变量中的代理
            timeout=timeout
        )

    # 创建ChatOpenAI实例
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        http_async_client=async_http_client
    )
