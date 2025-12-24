"""
测试LLM API连接
验证硅基流动API是否可用
"""
import sys
import io
import os
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("LLM API 测试")
print("=" * 60)

# 检查环境变量
openai_key = os.getenv('OPENAI_API_KEY')
openai_base = os.getenv('OPENAI_API_BASE', 'https://api.siliconflow.cn/v1')

print(f"\nAPI配置:")
print(f"  OPENAI_API_KEY: {'✅ 已配置 (' + openai_key[:20] + '...' + openai_key[-10:] + ')' if openai_key else '❌ 未配置'}")
print(f"  OPENAI_API_BASE: {openai_base}")

if not openai_key:
    print("\n❌ OPENAI_API_KEY未配置")
    sys.exit(1)

# 测试1: 使用OpenAI SDK直接调用
print("\n" + "=" * 60)
print("测试1: OpenAI SDK 直接调用")
print("=" * 60)

try:
    from openai import OpenAI

    client = OpenAI(
        api_key=openai_key,
        base_url=openai_base
    )

    print("\n发送测试请求...")
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-7B-Instruct",
        messages=[
            {"role": "user", "content": "你好，请用一句话介绍你自己。"}
        ],
        max_tokens=100,
        temperature=0.0
    )

    content = response.choices[0].message.content
    print(f"\n✅ OpenAI SDK调用成功！")
    print(f"模型: {response.model}")
    print(f"回复: {content}")
    print(f"耗时: ~{response.usage.total_tokens} tokens")

except Exception as e:
    print(f"\n❌ OpenAI SDK调用失败: {str(e)}")
    import traceback
    traceback.print_exc()


# 测试2: 使用LangChain调用
print("\n" + "=" * 60)
print("测试2: LangChain ChatOpenAI 调用")
print("=" * 60)

try:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model="Qwen/Qwen2.5-7B-Instruct",
        api_key=openai_key,
        base_url=openai_base,
        temperature=0.0,
        max_tokens=100,
        timeout=30.0
    )

    print("\n发送测试请求...")
    response = llm.invoke("请用一句话介绍Python编程语言。")

    print(f"\n✅ LangChain调用成功！")
    print(f"回复: {response.content}")

except Exception as e:
    print(f"\n❌ LangChain调用失败: {str(e)}")
    import traceback
    traceback.print_exc()


# 测试3: 使用项目配置调用
print("\n" + "=" * 60)
print("测试3: 项目配置调用 (config.py)")
print("=" * 60)

try:
    from config import get_config
    from utils.llm_utils import create_async_chat_llm
    import asyncio

    config = get_config()

    print(f"\n项目配置:")
    print(f"  模型: {config.llm.model}")
    print(f"  Base URL: {config.llm.base_url}")
    print(f"  Temperature: {config.llm.temperature}")
    print(f"  Max Tokens: {config.llm.max_tokens}")

    # 创建LLM实例
    llm = create_async_chat_llm(temperature=0.0, timeout=30.0)

    print("\n发送测试请求...")

    async def test_async_llm():
        response = await llm.ainvoke("请用一句话解释什么是云计算。")
        return response

    response = asyncio.run(test_async_llm())

    print(f"\n✅ 项目配置调用成功！")
    print(f"回复: {response.content}")

except Exception as e:
    print(f"\n❌ 项目配置调用失败: {str(e)}")
    import traceback
    traceback.print_exc()


# 测试4: 测试不同模型
print("\n" + "=" * 60)
print("测试4: 测试项目使用的模型")
print("=" * 60)

try:
    from openai import OpenAI
    from config import get_config

    config = get_config()
    model_name = config.llm.model

    print(f"\n项目配置的模型: {model_name}")

    client = OpenAI(
        api_key=openai_key,
        base_url=openai_base
    )

    print(f"发送测试请求到 {model_name}...")
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "1+1=?"}
        ],
        max_tokens=50,
        temperature=0.0
    )

    content = response.choices[0].message.content
    print(f"\n✅ 模型 {model_name} 调用成功！")
    print(f"回复: {content}")

except Exception as e:
    print(f"\n❌ 模型 {model_name} 调用失败: {str(e)}")

    # 尝试列出可用模型
    print("\n尝试获取可用模型列表...")
    try:
        models = client.models.list()
        print("\n可用的模型:")
        for model in models.data[:10]:  # 只显示前10个
            print(f"  - {model.id}")
    except Exception as e2:
        print(f"无法获取模型列表: {str(e2)}")


print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
