"""
测试Manager Agent ReAct模式 - 简单验证
"""
import asyncio
import sys
import io

# 设置stdout编码为utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.manager_agent import ManagerAgent


async def test_manager_agent_simple():
    """测试Manager Agent基础ReAct功能"""
    print("\n" + "=" * 70)
    print("测试Manager Agent ReAct模式")
    print("=" * 70)

    manager = ManagerAgent()

    # 简单请求：让Manager Agent调用CodeGeneratorAgent生成一段简单代码
    result = await manager.process_with_react({
        "user_request": "生成一个简单的Python函数，计算两个数的和"
    })

    print(f"\n结果: {'✅ 成功' if result.success else '❌ 失败'}")

    if result.data:
        print(f"迭代次数: {result.data.get('iterations')}")
        print(f"\n最终报告:")
        print("-" * 70)
        print(result.data.get('result', 'N/A'))
        print("-" * 70)

        if result.data.get('react_history'):
            print(f"\nReAct历史 ({len(result.data['react_history'])} 次迭代):")
            for step in result.data['react_history']:
                print(f"  迭代{step['iteration']}:")
                print(f"    Thought: {step['thought'][:100]}...")
                print(f"    Action: {step['action']['type']}")
                print(f"    Status: {step['observation'].get('status')}")

    if not result.success:
        print(f"错误: {result.error}")

    print("\n" + "=" * 70)
    return result.success


async def main():
    """运行测试"""
    print("\n⚡ Manager Agent 快速测试")
    print("⚠️  需要LLM API，可能需要1-2分钟\n")

    try:
        success = await test_manager_agent_simple()

        if success:
            print("🎉 测试通过！Manager Agent ReAct模式工作正常")
        else:
            print("⚠️  测试未完全通过，但可能是API问题")

    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
