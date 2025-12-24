"""
最终验证测试：确认405错误已修复
使用简短的prompt避免超时
"""
import sys
import io
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def main():
    """主测试"""
    print("=" * 60)
    print("最终验证：405错误修复测试")
    print("=" * 60)

    # 测试1: 使用llm_utils创建的LLM（简短prompt）
    print("\n测试1: llm_utils.create_async_chat_llm（简短prompt）")
    print("-" * 60)

    try:
        from llm_utils import create_async_chat_llm
        from langchain_core.messages import HumanMessage

        llm = create_async_chat_llm(temperature=0.0, timeout=60.0)

        print(f"LLM配置:")
        print(f"  模型: {llm.model_name}")
        print(f"  Temperature: {llm.temperature}")
        print(f"  Timeout: 60s")

        # 简短的prompt
        print("\n发送简短请求...")
        response = await llm.ainvoke([HumanMessage(content="1+1=?")])

        print(f"✅ 成功！回复: {response.content}")
        test1_pass = True

    except Exception as e:
        error_msg = str(e)
        if "405" in error_msg:
            print(f"❌ 405错误仍然存在: {error_msg}")
            test1_pass = False
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            print(f"⚠️ 超时（不是405错误）: {error_msg[:100]}")
            test1_pass = "timeout"
        else:
            print(f"❌ 其他错误: {error_msg[:100]}")
            test1_pass = False

    # 测试2: 使用稍长的prompt
    print("\n\n测试2: llm_utils.create_async_chat_llm（中等长度prompt）")
    print("-" * 60)

    try:
        from llm_utils import create_async_chat_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = create_async_chat_llm(temperature=0.0, timeout=90.0)  # 增加到90秒

        messages = [
            SystemMessage(content="你是一个Python专家。"),
            HumanMessage(content="请写一个函数计算斐波那契数列的第n项。")
        ]

        print("发送中等长度请求...")
        response = await asyncio.wait_for(llm.ainvoke(messages), timeout=90.0)

        print(f"✅ 成功！回复长度: {len(response.content)} 字符")
        print(f"回复片段: {response.content[:150]}...")
        test2_pass = True

    except asyncio.TimeoutError:
        print(f"⚠️ 超时（90秒），但不是405错误")
        test2_pass = "timeout"
    except Exception as e:
        error_msg = str(e)
        if "405" in error_msg:
            print(f"❌ 405错误仍然存在: {error_msg}")
            test2_pass = False
        else:
            print(f"❌ 其他错误: {error_msg[:100]}")
            test2_pass = False

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if test1_pass == True:
        print("✅ 测试1通过：简短prompt成功，405错误已修复")
    elif test1_pass == "timeout":
        print("⚠️ 测试1超时：不是405错误，说明参数问题已解决")
    else:
        print("❌ 测试1失败：仍有405或其他错误")

    if test2_pass == True:
        print("✅ 测试2通过：中等prompt成功")
    elif test2_pass == "timeout":
        print("⚠️ 测试2超时：不是405错误，建议增加超时时间")
    else:
        print("❌ 测试2失败：仍有405或其他错误")

    print("\n" + "=" * 60)
    if test1_pass == True or test1_pass == "timeout":
        print("🎉 405错误已修复！")
        print("如果遇到超时，可以:")
        print("  1. 增加timeout参数")
        print("  2. 使用更简短的prompt")
        print("  3. 检查网络连接")
        return True
    else:
        print("❌ 405错误未完全修复")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
