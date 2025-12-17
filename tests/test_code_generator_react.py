"""
测试CodeGeneratorAgent的ReAct模式
验证自主生成→测试→修正循环
"""
import asyncio
import sys
import os
import io

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.code_generator_agent import CodeGeneratorAgent


async def test_simple_function_generation():
    """测试1：简单函数生成（应该一次通过）"""
    print("\n=== 测试1：简单函数生成 ===")

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个斐波那契数列生成函数fibonacci(n)，返回第n个斐波那契数",
        "operation": "fibonacci",
        "cloud_provider": "general",
        "service": "math",
        "parameters": {"n": 10},
        "language": "python",
        "enable_auto_test": True
    })

    print(f"结果: {result.success}")
    print(f"迭代次数: {result.data.get('iterations') if result.data else 'N/A'}")

    if result.success:
        print(f"\n生成的代码:")
        print("=" * 50)
        print(result.data["code"][:500])
        print("=" * 50)
        print(f"\n✅ 测试1通过（{result.data['iterations']}次迭代）")
    else:
        error_msg = result.message or result.error or "Unknown error"
        print(f"❌ 测试1失败: {error_msg}")
        if result.data and result.data.get("react_history"):
            print("\nReAct历史:")
            for h in result.data["react_history"]:
                print(f"  迭代{h['iteration']}: {h['observation']['status']}")


async def test_simple_no_test():
    """测试2：禁用自动测试"""
    print("\n=== 测试2：禁用自动测试 ===")

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个判断质数的函数is_prime(n)",
        "operation": "is_prime",
        "cloud_provider": "general",
        "service": "math",
        "parameters": {"n": 17},
        "language": "python",
        "enable_auto_test": False  # 禁用自动测试
    })

    print(f"结果: {result.success}")
    print(f"迭代次数: {result.data.get('iterations') if result.data else 'N/A'}")

    if result.success:
        print(f"✅ 测试2通过（禁用自动测试，直接返回）")
    else:
        error_msg = result.message or result.error or "Unknown error"
        print(f"❌ 测试2失败: {error_msg}")


async def test_react_history():
    """测试3：检查ReAct历史记录"""
    print("\n=== 测试3：检查ReAct历史记录 ===")

    agent = CodeGeneratorAgent()

    result = await agent.process_with_react({
        "requirement": "实现一个计算两数最大公约数的函数gcd(a, b)",
        "operation": "gcd",
        "cloud_provider": "general",
        "service": "math",
        "parameters": {"a": 48, "b": 18},
        "language": "python",
        "enable_auto_test": True
    })

    if result.data and result.data.get("react_history"):
        print(f"ReAct历史记录（{len(result.data['react_history'])}次迭代）:")
        for h in result.data["react_history"]:
            print(f"\n  迭代{h['iteration']}:")
            print(f"    Thought: {h['thought'][:100]}...")
            print(f"    Action: 生成{h['action']['code_length']}字符代码")
            print(f"    Observation: {h['observation']['status']}")
        print("\n✅ 测试3通过")
    else:
        print("❌ 测试3失败：无ReAct历史")


async def main():
    """运行所有测试"""
    print("=" * 70)
    print("CodeGeneratorAgent ReAct模式测试")
    print("=" * 70)

    # 注意：这些测试需要调用LLM，需要配置API Key
    print("\n⚠️  提示：这些测试需要LLM API，请确保已配置config.yaml")
    print("⏳ 测试可能需要1-2分钟...")

    try:
        await test_simple_function_generation()
        await test_simple_no_test()
        await test_react_history()

        print("\n" + "=" * 70)
        print("✅ 所有测试完成")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
